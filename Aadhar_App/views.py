from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from .models import Aadhar, AadharOTP
from .forms import AadharCreateForm, AadharEditForm
from datetime import timedelta
import random
import base64
from django.core.files.base import ContentFile
import uuid

#BankModels
from DigitalBank.models import Customer as DigitalCustomer
from YourBank.models import Customer as YourCustomer


# Home page with search
def home(request):
    aadhar = None
    query = request.GET.get('aadhar_no')
    if query:
        try:
            aadhar = Aadhar.objects.get(aadhar_no=query)
        except Aadhar.DoesNotExist:
            aadhar = 'not_found'
    return render(request, 'aadhar_app/home.html', {'aadhar': aadhar})

# Create Aadhar
def aadhar_create(request):
    if request.method == 'POST':
        form = AadharCreateForm(request.POST)
        if form.is_valid():
            a = form.save()
            return redirect('aadhar_detail', pk=a.pk)
    else:
        form = AadharCreateForm()
    return render(request, 'aadhar_app/aadhar_create.html', {'form': form})

# View Aadhar detail
def aadhar_detail(request, pk):
    a = get_object_or_404(Aadhar, pk=pk)
    return render(request, 'aadhar_app/aadhar_detail.html', {'a': a})


def aadhar_edit(request, pk):
    a = get_object_or_404(Aadhar, pk=pk)

    if request.method == 'POST':
        form = AadharEditForm(request.POST, request.FILES, instance=a)

        if form.is_valid():
            a = form.save(commit=False)

            # 📸 AADHAR PHOTO (ONLY HERE)
            photo_data = request.POST.get('photo_data')
            if photo_data:
                fmt, imgstr = photo_data.split(';base64,')
                ext = fmt.split('/')[-1]
                a.photo.save(
                    f"aadhar_{uuid.uuid4()}.{ext}",
                    ContentFile(base64.b64decode(imgstr)),
                    save=False
                )

            a.save()

            # 🔁 SYNC PAN (ALL FIELDS EXCEPT PHOTO)
            if hasattr(a, 'pan'):
                pan = a.pan
                pan.name = a.name
                pan.father_name = a.father_name
                pan.address = a.address
                pan.mobile = a.mobile
                pan.gender = a.gender
                pan.save()

            # 🏦 BANK UPDATE → MATCH BY AADHAR NUMBER
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

            return redirect('aadhar_detail', pk=a.pk)

    else:
        form = AadharEditForm(instance=a)

    return render(request, 'aadhar_app/aadhar_edit.html', {
        'form': form,
        'a': a
    })




# Send OTP
def send_otp_for_verification(request):
    if request.method != 'POST':
        return JsonResponse({'error':'POST required'}, status=400)
    mobile = request.POST.get('mobile')
    aadhar_no = request.POST.get('aadhar_no')
    try:
        a = Aadhar.objects.get(aadhar_no=aadhar_no, mobile=mobile)
    except Aadhar.DoesNotExist:
        return JsonResponse({'status':'not_found'})
    otp = ''.join(str(random.randint(0,9)) for _ in range(6))
    expires = timezone.now() + timedelta(seconds=30)
    AadharOTP.objects.create(aadhar=a, mobile=mobile, otp=otp, expires_at=expires)
    return JsonResponse({'status':'sent', 'otp': otp, 'expires_at': expires.isoformat()})

# Verify OTP
def verify_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error':'POST required'}, status=400)
    mobile = request.POST.get('mobile')
    aadhar_no = request.POST.get('aadhar_no')
    otp = request.POST.get('otp')
    try:
        a = Aadhar.objects.get(aadhar_no=aadhar_no, mobile=mobile)
    except Aadhar.DoesNotExist:
        return JsonResponse({'status':'not_found'})
    try:
        entry = AadharOTP.objects.filter(aadhar=a, mobile=mobile, otp=otp, used=False).latest('created_at')
    except AadharOTP.DoesNotExist:
        return JsonResponse({'status':'invalid'})
    if entry.is_expired():
        return JsonResponse({'status':'expired'})
    entry.used = True
    entry.save()
    data = {
        'name': a.name,
        'father_name': a.father_name,
        'mobile': a.mobile,
        'dob': a.dob.isoformat(),
        'gender': a.gender,
        'address': a.address,
        'aadhar_no': a.aadhar_no,
        'photo_url': a.photo.url if a.photo else None,
    }
    return JsonResponse({'status':'verified', 'data': data})
