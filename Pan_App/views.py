from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse, HttpResponseBadRequest
from .models import Pan
from .forms import PanCreateForm, PanEditForm
from Aadhar_App.models import Aadhar, AadharOTP  # ensure this import matches your aadhar app
from datetime import timedelta, date
import random
import base64
from django.core.files.base import ContentFile
import uuid

#BankModels
from DigitalBank.models import Customer as DigitalCustomer
from YourBank.models import Customer as YourCustomer

# Home / search by PAN number
def pan_home(request):
    pan = None
    query = request.GET.get('pan_no')
    if query:
        try:
            pan = Pan.objects.get(pan_no=query.strip())
        except Pan.DoesNotExist:
            pan = 'not_found'
    return render(request, 'pan_app/home.html', {'pan': pan})

# Step 1: start create — accept mobile + aadhar_no, check aadhar exists and age >=18 and then generate OTP
def pan_create_start(request):
    if request.method == 'POST':
        aadhar_no = request.POST.get('aadhar_no', '').strip()
        mobile = request.POST.get('mobile', '').strip()

        # Basic validation
        if not aadhar_no or not mobile:
            return render(request, 'pan_app/pan_create_start.html',
                          {'error': 'Provide Aadhar number and mobile.'})

        # (A) FIND AADHAR → must match BOTH number & mobile
        try:
            person = Aadhar.objects.get(aadhar_no=aadhar_no, mobile=mobile)
        except Aadhar.DoesNotExist:
            return render(request, 'pan_app/pan_create_start.html',
                          {'error': 'Aadhar and mobile not found / mismatch.'})

        # (B) AGE CHECK
        today = date.today()
        age = today.year - person.dob.year - (
                (today.month, today.day) < (person.dob.month, person.dob.day)
        )

        if age < 18:
            return render(request, 'pan_app/pan_create_start.html',
                          {'error': 'Age must be at least 18 to apply for PAN.'})

        # (C) CHECK IF PAN ALREADY EXISTS FOR THIS PERSON
        if Pan.objects.filter(aadhar=person).exists():
            return render(request, 'pan_app/pan_create_start.html',
                          {'error': 'PAN already created for this Aadhar.'})

        # (D) GENERATE OTP using AadharOTP MODEL (from Aadhar verification app)
        otp = ''.join(str(random.randint(0, 9)) for _ in range(6))
        expires = timezone.now() + timedelta(seconds=30)

        AadharOTP.objects.create(
            aadhar=person,
            mobile=mobile,
            otp=otp,
            expires_at=expires
        )

        # (E) STORE TEMPORARY SESSION VALUES FOR NEXT STEP
        request.session['pan_pending_aadhar_id'] = person.id
        request.session['pan_pending_mobile'] = mobile

        # (F) FOR DEVELOPMENT ONLY → SHOW OTP
        return render(request, 'pan_app/pan_verify_otp.html',
                      {'aadhar': person, 'otp': otp})

    # GET request → just show empty form
    return render(request, 'pan_app/pan_create_start.html')

# Step 2: verify OTP. If ok, redirect to pan_create_form
def pan_verify_otp(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("POST required")
    mobile = request.POST.get('mobile', '').strip()
    aadhar_no = request.POST.get('aadhar_no', '').strip()
    otp = request.POST.get('otp', '').strip()
    # find aadhar
    try:
        a = Aadhar.objects.get(aadhar_no=aadhar_no, mobile=mobile)
    except Aadhar.DoesNotExist:
        return render(request, 'pan_app/pan_verify_otp.html', {'error': 'Aadhar not found.'})
    try:
        entry = AadharOTP.objects.filter(aadhar=a, mobile=mobile, otp=otp, used=False).latest('created_at')
    except AadharOTP.DoesNotExist:
        return render(request, 'pan_app/pan_verify_otp.html', {'aadhar': a, 'error': 'Invalid OTP'})
    if entry.is_expired():
        return render(request, 'pan_app/pan_verify_otp.html', {'aadhar': a, 'error': 'OTP expired'})
    # mark used
    entry.used = True
    entry.save()
    # mark session verified
    request.session['pan_verified_aadhar_id'] = a.pk
    # redirect to pan creation form (prefilled)
    return redirect('pan_create_form')

def pan_resend_otp(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("POST required")

    aadhar_no = request.POST.get('aadhar_no')
    mobile = request.POST.get('mobile')

    try:
        a = Aadhar.objects.get(aadhar_no=aadhar_no, mobile=mobile)
    except Aadhar.DoesNotExist:
        return render(request, 'pan_app/pan_verify_otp.html', {
            'error': 'Aadhar not found.'
        })

    # Generate NEW OTP
    otp = ''.join(str(random.randint(0, 9)) for _ in range(6))
    expires = timezone.now() + timedelta(seconds=30)

    AadharOTP.objects.create(
        aadhar=a,
        mobile=mobile,
        otp=otp,
        expires_at=expires
    )

    return render(request, 'pan_app/pan_verify_otp.html', {
        'aadhar': a,
        'msg': 'OTP resent successfully.'
    })


# Step 3: show creation form autofilled from Aadhar (only when verified)
def pan_create_form(request):
    verified_id = request.session.get('pan_verified_aadhar_id')
    if not verified_id:
        return redirect('pan_create_start')
    a = get_object_or_404(Aadhar, pk=verified_id)
    if request.method == 'POST':
        # include aadhar id in POST so form can save
        post_data = request.POST.copy()
        post_data['aadhar'] = str(a.pk)
        form = PanCreateForm(post_data)
        # handle photo_data (hidden field) — PanCreateForm will save it
        if form.is_valid():
            pan = form.save()
            # cleanup session keys
            request.session.pop('pan_verified_aadhar_id', None)
            request.session.pop('pan_pending_aadhar_id', None)
            request.session.pop('pan_pending_mobile', None)
            return redirect('pan_detail', pk=pan.pk)
    else:
        # initial form with aadhar prefilled
        form = PanCreateForm(initial={'aadhar': a.pk, 'mobile': a.mobile, 'address': a.address})
    return render(request, 'pan_app/pan_create_form.html', {'form': form, 'aadhar': a})

# PAN detail & edit
def pan_detail(request, pk):
    pan = get_object_or_404(Pan, pk=pk)
    return render(request, 'pan_app/pan_detail.html', {'pan': pan})


def pan_edit(request, pk):
    pan = get_object_or_404(Pan, pk=pk)

    if request.method == 'POST':
        form = PanEditForm(request.POST, request.FILES, instance=pan)

        if form.is_valid():
            pan = form.save(commit=False)

            # 📸 PAN PHOTO (ONLY HERE)
            photo_data = request.POST.get('photo_data')
            if photo_data:
                fmt, imgstr = photo_data.split(';base64,')
                ext = fmt.split('/')[-1]
                pan.photo.save(
                    f"pan_{uuid.uuid4()}.{ext}",
                    ContentFile(base64.b64decode(imgstr)),
                    save=False
                )

            pan.save()

            # 🔁 SYNC AADHAR (ALL FIELDS EXCEPT PHOTO)
            a = pan.aadhar
            a.name = pan.name
            a.father_name = pan.father_name
            a.address = pan.address
            a.mobile = pan.mobile
            a.gender = pan.gender
            a.save()

            # 🏦 BANK UPDATE → MATCH BY PAN NUMBER
            # sync BANK only
            DigitalCustomer.objects.filter(
                aadhar__aadhar_no=a.aadhar_no
            ).update(
                mobile=a.mobile,
                gender=a.gender
            )

            YourCustomer.objects.filter(
                aadhar__aadhar_no=a.aadhar_no
            ).update(
                mobile=a.mobile,
                gender=a.gender
            )


            return redirect('pan_detail', pk=pan.pk)

    else:
        form = PanEditForm(instance=pan)

    return render(request, 'pan_app/pan_edit.html', {
        'form': form,
        'pan': pan
    })
