from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib import messages
from django.db import transaction as db_transaction
from .models import Bank, Customer, Transaction, BankTransaction, Staff, ATMCard, BankOTP
from .forms import *
from Aadhar_App.models import Aadhar, AadharOTP
from Pan_App.models import Pan
from datetime import date, timedelta
from django.utils import timezone
import random
import io
import time
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from django.http import JsonResponse
import base64
import uuid
from django.core.files.base import ContentFile
from Aadhar_App.models import Aadhar as AadharCustomer
from Pan_App.models import Pan as PanCustomer
import requests # to call bank backend API




# ----------- STAFF LOGIN & DASHBOARD -----------

def staff_login(request):
    form = StaffLoginForm()
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        try:
            staff = Staff.objects.get(username=username, password=password)
            request.session['staff_id'] = staff.id
            request.session['staff_username'] = staff.username
            return redirect('yourbank:staff_dashboard')
        except Staff.DoesNotExist:
            messages.error(request, "User not found!")
    return render(request, "yourbank/staff_login.html", {'form': form})





def logout_staff(request):
    request.session.flush()
    messages.success(request, 'Logged Out Successfully!')
    return redirect('yourbank:staff_login')

def staff_account(request): 
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "Please Login!")
        return redirect('yourbank:staff_login')

    staff = Staff.objects.get(id=staff_id)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        staff.username = username
        staff.password = password
        staff.save()
        messages.success(request, "Updated successfully!")
        return redirect('yourbank:staff_account')

    return render(request, 'yourbank/staff_account.html', {'staff': staff})

def get_display_type(txn):
    if txn.transaction_type == "CREDIT":
        return "Credit/UPI"
    elif txn.transaction_type == "DEBIT":
        return "Debit/UPI"
    return txn.get_transaction_type_display()


def staff_dashboard(request):
    if 'staff_id' not in request.session:
        return redirect('yourbank:staff_login')

    query = request.GET.get('q', '').strip()
    if query:
        try:
            customer = Customer.objects.get(account_no=query)
            return redirect('yourbank:customer_detail', pk=customer.customer_id)
        except Customer.DoesNotExist:
            messages.error(request, "No customer found with that account number.")
            return redirect('yourbank:staff_dashboard')

    recent_transactions = Transaction.objects.select_related("customer").order_by("-date")[:10]
    for txn in recent_transactions:
        txn.display_type = get_display_type(txn)

    return render(
        request,
        "yourbank/staff_dashboard.html",
        {"transactions": recent_transactions})


def get_display_type(txn):
    if txn.transaction_type == "CREDIT":
        return "Credit/UPI"
    elif txn.transaction_type == "DEBIT":
        return "Debit/UPI"
    return txn.get_transaction_type_display()

def bank_dashboard(request):
    if 'staff_id' not in request.session:
        return redirect('yourbank:staff_login')
    bank = Bank.objects.first()
    # Recent 10 transactions
    transactions = BankTransaction.objects.all().order_by('-date')[:10]
    for txn in transactions:
        txn.display_type = get_display_type(txn)

    customer_count = bank.customer_set.count() if bank else 0
    context = {
        'bank': bank,
        'transactions': transactions,
        'customer_count': customer_count
    }
    return render(request, 'yourbank/bank.html', context)


def create_customer_start(request):
    """
    Staff enters aadhar_no + mobile to verify person via Aadhar app (OTP).
    """
    if request.method == 'POST':
        form = CustomerCreateStartForm(request.POST)
        if form.is_valid():
            aadhar_no = form.cleaned_data['aadhar_no'].strip()
            mobile = form.cleaned_data['mobile'].strip()
            # find aadhar
            try:
                a = Aadhar.objects.get(aadhar_no=aadhar_no, mobile=mobile)
            except Aadhar.DoesNotExist:
                return render(request, 'yourbank/create_start.html', {'form': form, 'error': 'Aadhar+mobile mismatch or not found.'})
            # check PAN exists? business rule: bank requires PAN — if not, show notice but allow create with pan NULL? We'll show warning.
            pan_exists = Pan.objects.filter(aadhar=a).exists()
            # create OTP record in AadharOTP
            otp = ''.join(str(random.randint(0,9)) for _ in range(6))
            expires = timezone.now() + timedelta(seconds=30)
            AadharOTP.objects.create(aadhar=a, mobile=mobile, otp=otp, expires_at=expires)
            # session store
            request.session['yourbank:customer_pending_aadhar_id'] = a.pk
            request.session['yourbank:customer_pending_mobile'] = mobile
            # Dev show OTP
            return render(request, 'yourbank/verify_otp.html', {'aadhar': a, 'otp': otp, 'pan_exists': pan_exists})
    else:
        form = CustomerCreateStartForm()
    return render(request, 'yourbank/create_start.html', {'form': form})

def customer_verify_otp(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("POST required")
    aadhar_no = request.POST.get('aadhar_no','').strip()
    mobile = request.POST.get('mobile','').strip()
    otp = request.POST.get('otp','').strip()
    try:
        a = Aadhar.objects.get(aadhar_no=aadhar_no, mobile=mobile)
    except Aadhar.DoesNotExist:
        return render(request, 'yourbank/verify_otp.html', {'error':'Aadhar not found.'})
    try:
        entry = AadharOTP.objects.filter(aadhar=a, mobile=mobile, otp=otp, used=False).latest('created_at')
    except AadharOTP.DoesNotExist:
        return render(request, 'yourbank/verify_otp.html', {'aadhar': a, 'error':'Invalid OTP.'})
    if entry.is_expired():
        return render(request, 'yourbank/verify_otp.html', {'aadhar': a, 'error':'OTP expired.'})
    entry.used = True
    entry.save()
    request.session['customer_verified_aadhar_id'] = a.pk
    return redirect('yourbank:customer_create_form')

def customer_create_form(request):
    verified_id = request.session.get('customer_verified_aadhar_id')
    if not verified_id:
        return redirect('yourbank:create_customer_start')
    
    a = get_object_or_404(Aadhar, pk=verified_id)

    if request.method == 'POST':
        post = request.POST.copy()
        form = CustomerForm(post, request.FILES)  # include files for photo
        if form.is_valid():
            with db_transaction.atomic():
                cust = form.save(commit=False)
                cust.aadhar = a
                cust.name = a.name
                cust.father_name = a.father_name
                cust.dob = a.dob
                cust.gender = a.gender
                cust.mobile = a.mobile

# PAN link
                try:
                    cust.pan = Pan.objects.get(aadhar=a)
                except Pan.DoesNotExist:
                    cust.pan = None

# CAMERA PHOTO
                # CAMERA PHOTO (highest priority)
                photo_data = post.get('photo_data')
                if photo_data:
                    format, imgstr = photo_data.split(';base64,')
                    ext = format.split('/')[-1]
                    cust.photo.save(                
                        f"cust_{uuid.uuid4()}.{ext}",
                        ContentFile(base64.b64decode(imgstr)),
                        save=False
                    )

# ✅ FALLBACK → COPY PHOTO FROM AADHAR
                elif a.photo:
                    cust.photo = a.photo


                cust.save()


                # Create initial deposit transaction if balance > 0
                if cust.balance and cust.balance > 0:
                    Transaction.objects.create(
                        customer=cust,
                        transaction_type='DEPOSIT',
                        amount=cust.balance,
                        balance_before=0,
                        balance_after=cust.balance,
                        receiver_account=cust.account_no
                    )
                    BankTransaction.objects.create(
                        bank=cust.bank,
                        customer=cust,
                        transaction_type='DEPOSIT',
                        amount=cust.balance,
                        balance_before=cust.bank.balance,
                        balance_after=cust.bank.balance + cust.balance,
                        receiver_account=cust.account_no
                    )
                    cust.bank.balance += cust.balance
                    cust.bank.save()

            # Cleanup session
            for k in ('customer_verified_aadhar_id','customer_pending_aadhar_id','customer_pending_mobile'):
                request.session.pop(k, None)
            
            messages.success(request, "Customer created successfully!")
            return redirect('yourbank:customer_detail', pk=cust.customer_id)
    else:
        # Prefill all fields from Aadhar
        form = CustomerForm(initial={
            'bank': None,  # staff can select bank in form
            'account_type': None,
            'name': a.name,
            'father_name': a.father_name,
            'mobile': a.mobile,
            'dob': a.dob,
            'gender': a.gender,
            'address': a.address,
            'balance': 0
        })

    return render(request, 'yourbank/create_form.html', {'form': form, 'aadhar': a})


#ATM

def generate_atm_number(customer):
    prefix = customer.bank.bank_prefix     # example 1011
    dob = customer.dob.strftime("%d%m")    # ex 1406
    rand = str(random.randint(1000,9999))
    return f"{prefix}{dob}{rand}"

def create_atm(request, pk):
    cust = get_object_or_404(Customer, pk=pk)

    if not cust.is_active:
        messages.error(request, "Customer account is deactivated")
        return redirect("yourbank:customer_detail", pk=pk)

    if hasattr(cust, "atmcard"):
        messages.error(request, "ATM already exists")
        return redirect("yourbank:customer_detail", pk=pk)

    card_no = generate_atm_number(cust)

    ATMCard.objects.create(
        customer=cust,
        card_no=card_no,
        cvv=str(random.randint(100,999)),
        expiry_date=timezone.now().date() + timedelta(days=365*5)
    )

    messages.success(request, "ATM card generated")
    return redirect("yourbank:customer_detail", pk=pk)

def block_atm(request, pk):
    atm = get_object_or_404(ATMCard, customer_id=pk)
    atm.is_active = False
    atm.save()
    messages.warning(request, "ATM card blocked")
    return redirect("yourbank:customer_detail", pk=pk)

def enable_atm(request, pk):
    atm = get_object_or_404(ATMCard, customer_id=pk)
    atm.is_active = True
    atm.save()
    messages.success(request, "ATM card enabled")
    return redirect("yourbank:customer_detail", pk=pk)

def renew_atm(request, pk):
    atm = get_object_or_404(ATMCard, customer_id=pk)
    cust = atm.customer

    # Block only when card is active AND not expired
    if not atm.can_renew():
        messages.error(request, "Active card cannot be renewed")
        return redirect("yourbank:customer_detail", pk=pk)

    atm.card_no = generate_atm_number(cust)
    atm.cvv = str(random.randint(100,999))
    atm.expiry_date = timezone.now().date() + timedelta(days=365*5)
    atm.is_active = True
    atm.save()

    messages.success(request, "ATM card renewed successfully")
    return redirect("yourbank:customer_detail", pk=pk)



def atm_process_page(request, pk, action):
    cust = get_object_or_404(Customer, pk=pk)
    return render(request, "yourbank/atm_processing.html", {
        "customer": cust,
        "action": action
    })



def atm_api(request, pk, action):
    cust = get_object_or_404(Customer, pk=pk)

    # Random server delay (5–10 sec)
    delay = random.randint(5, 10)
    time.sleep(delay)

    # 15% chance of failure (like network issue)
    if random.randint(1, 100) <= 15:
        return JsonResponse({
            "status": "failed",
            "message": "Network or Bank Server not responding"
        })

    # CREATE
    if action == "create":
        if hasattr(cust, "atmcard"):
            return JsonResponse({"status":"failed","message":"ATM already exists"})

        ATMCard.objects.create(
            customer=cust,
            card_no=generate_atm_number(cust),
            cvv=str(random.randint(100,999)),
            expiry_date=timezone.now().date() + timedelta(days=365*5)
        )

    # RENEW
    elif action == "renew":
        atm = cust.atmcard
        atm.card_no = generate_atm_number(cust)
        atm.cvv = str(random.randint(100,999))
        atm.expiry_date = timezone.now().date() + timedelta(days=365*5)
        atm.is_active = True
        atm.save()

    return JsonResponse({"status":"success"})



def customer_toggle_active(request, pk):
    if request.method != 'POST':
        return redirect('yourbank:customer_detail', pk=pk)
    cust = get_object_or_404(Customer, pk=pk)
    value = request.POST.get('is_active')
    if value == 'True':
        cust.is_active = True
        messages.success(request, "Customer activated successfully.")
    elif value == 'False':
        cust.is_active = False
        messages.success(request, "Customer deactivated successfully.")

         # 🔒 Block ATM automatically
        if hasattr(cust, "atmcard"):
            cust.atmcard.is_active = False
            cust.atmcard.save()
    cust.save()
    return redirect('yourbank:customer_detail', pk=pk)


# Customer detail and edit
def customer_detail(request, pk):
    bank = Bank.objects.get(name="YourBank")

    cust = get_object_or_404(Customer, pk=pk, bank=bank)

    transactions = cust.transactions.all().order_by('-date')
    for txn in transactions:
        txn.display_type = get_display_type(txn)

    form = TransactionForm()

    # ---------------- ATM LOGIC ----------------
    atm = None
    show_renew = False

    if hasattr(cust, "atmcard"):
        atm = cust.atmcard
        if atm.can_renew():   # expired OR blocked
            show_renew = True
    # -------------------------------------------

    return render(request, 'yourbank/customer_detail.html', {
        'customer': cust,
        'transactions': transactions,
        'form': form,

        # 🔥 ATM data to template
        'atm': atm,
        'show_renew': show_renew
    })


def customer_edit(request, pk, bank_name):
    bank = get_object_or_404(Bank, name=bank_name)
    cust = get_object_or_404(Customer, pk=pk, bank=bank)

    if not cust.is_active:
        messages.error(request, "Customer account is deactivated")
        return redirect("yourbank:customer_detail", pk=pk)

    if request.method == "POST":
        form = CustomerEditForm(request.POST, request.FILES, instance=cust)

        if form.is_valid():
            updated = form.save(commit=False)

            # 📸 Camera image
            photo_data = request.POST.get("photo_data")
            if photo_data:
                fmt, imgstr = photo_data.split(";base64,")
                ext = fmt.split("/")[-1]
                updated.photo.save(
                    f"cust_{uuid.uuid4()}.{ext}",
                    ContentFile(base64.b64decode(imgstr)),
                    save=False
                )

            updated.save()

            # 🔄 Sync Mobile to Aadhaar
            aadhar_no = cust.aadhar.aadhar_no   # get linked Aadhaar number

            AadharCustomer.objects.filter(
                aadhar_no=aadhar_no
                ).update(
                mobile=cust.mobile
                )

            PanCustomer.objects.filter(
                aadhar__aadhar_no=aadhar_no
                ).update(
                mobile=cust.mobile
                )


            messages.success(request, "Customer updated successfully.")
            return redirect("yourbank:customer_detail", pk=updated.pk)

        else:
            print(form.errors)   # 👈 THIS shows error in terminal

    else:
        form = CustomerEditForm(instance=cust)

    return render(request, "yourbank/customer_edit.html", {
        "form": form,
        "customer": cust
    })



# Create transaction for a customer
def create_transaction(request, customer_id):
    cust = get_object_or_404(Customer, pk=customer_id)
    
    if not cust.is_active:
        messages.error(request, "Customer account is deactivated")
        return redirect("yourbank:customer_detail", pk=pk)

    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.customer = cust
            txn.balance_before = cust.balance
            bank = cust.bank

            # DEPOSIT
            if txn.transaction_type == 'DEPOSIT':
                cust.balance += txn.amount
                bank.balance += txn.amount
                txn.balance_after = cust.balance
                txn.receiver_account = cust.account_no
                txn.sender_account = None
                txn.save()
                BankTransaction.objects.create(
                    bank=bank,
                    customer=cust,
                    transaction_type='DEPOSIT',
                    amount=txn.amount,
                    balance_before=bank.balance - txn.amount,
                    balance_after=bank.balance,
                    receiver_account=cust.account_no
                )

            # WITHDRAW
            elif txn.transaction_type == 'WITHDRAW':
                if cust.balance < txn.amount:
                    messages.error(request, "Insufficient balance")
                    return redirect('yourbank:customer_detail', pk=customer_id)
                cust.balance -= txn.amount
                bank.balance -= txn.amount
                txn.balance_after = cust.balance
                txn.sender_account = cust.account_no
                txn.receiver_account = None
                txn.save()
                BankTransaction.objects.create(
                    bank=bank,
                    customer=cust,
                    transaction_type='WITHDRAW',
                    amount=txn.amount,
                    balance_before=bank.balance + txn.amount,
                    balance_after=bank.balance,
                    sender_account=cust.account_no
                )

            # TRANSFER
            elif txn.transaction_type == 'TRANSFER':
                receiver_acc = txn.receiver_account.strip() if txn.receiver_account else ''
                if not receiver_acc:
                    messages.error(request, "Receiver account required")
                    return redirect('yourbank:customer_detail', pk=customer_id)
                try:
                    receiver = Customer.objects.get(account_no=receiver_acc)
                except Customer.DoesNotExist:
                    messages.error(request, "Receiver account not found")
                    return redirect('yourbank:customer_detail', pk=customer_id)
                if cust.balance < txn.amount:
                    messages.error(request, "Insufficient balance")
                    return redirect('yourbank:customer_detail', pk=customer_id)

                # debit sender
                cust.balance -= txn.amount
                txn.balance_after = cust.balance
                txn.sender_account = cust.account_no
                txn.receiver_account = receiver.account_no
                txn.save()
                BankTransaction.objects.create(
                    bank=bank,
                    customer=cust,
                    transaction_type='TRANSFER',
                    amount=txn.amount,
                    balance_before=bank.balance,
                    balance_after=bank.balance - txn.amount,
                    sender_account=cust.account_no,
                    receiver_account=receiver.account_no
                )
                bank.balance -= txn.amount
                bank.save()
                
                # credit receiver (any bank)
                receiver.balance += txn.amount
                Transaction.objects.create(
                    customer=receiver,
                    transaction_type='TRANSFER',
                    amount=txn.amount,
                    balance_before=receiver.balance - txn.amount,
                    balance_after=receiver.balance,
                    sender_account=cust.account_no,
                    receiver_account=receiver.account_no
                )
                BankTransaction.objects.create(
                    bank=receiver.bank,
                    customer=receiver,
                    transaction_type='TRANSFER',
                    amount=txn.amount,
                    balance_before=receiver.bank.balance,
                    balance_after=receiver.bank.balance + txn.amount,
                    sender_account=cust.account_no,
                    receiver_account=receiver.account_no
                )
                receiver.bank.balance += txn.amount
                receiver.bank.save()
                receiver.save()

            cust.save()
            bank.save()
            messages.success(request, "Transaction completed successfully!")
            return redirect('yourbank:customer_detail', pk=customer_id)
    else:
        form = TransactionForm()
    
    return render(request, 'yourbank/create_transaction.html', {'form': form, 'customer': cust})

# Download transactions PDF for a customer (staff)
def download_transactions_pdf(request, customer_id):
    cust = get_object_or_404(Customer, pk=customer_id)
    txns = cust.transactions.all().order_by('-date')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Transaction Report (Staff View)", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Name:</b> {cust.name}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Account:</b> {cust.account_no}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    data = [["Date", "Sender", "Receiver", "Type", "Amount", "Before", "After"]]

    for t in txns:
        # Sender column
        if cust.account_no == t.sender_account:
            sender_display = t.sender_account
            receiver_display = f"{t.receiver_bank} | {t.receiver_account}" if t.receiver_bank else t.receiver_account
        else:
            sender_display = f"{t.sender_bank} | {t.sender_account}" if t.sender_bank else t.sender_account
            receiver_display = t.receiver_account

        data.append([
            t.date.strftime("%d-%m-%Y %H:%M"),
            sender_display,
            receiver_display,
            t.get_transaction_type_display(),
            f"₹ {t.amount}",
            f"₹ {t.balance_before}",
            f"₹ {t.balance_after}",
        ])

    table = Table(data, hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return HttpResponse(
        buffer,
        content_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=transactions_{cust.account_no}.pdf"}
    )



# yourbank/views_atm.py

def clear_atm_session(request):
    for key in ["atm_card_id", "atm_mobile", "atm_verified"]:
        request.session.pop(key, None)


def atm_guard(card):
    if not card.customer.is_active:
        return False, "Customer account is deactivated"

    if not card.is_active:
        return False, "ATM card is blocked"

    if card.is_expired():
        return False, "ATM card expired"

    return True, ""



# Step 1: Verify ATM card
def atm_home(request):
    form = ATMCardVerifyForm()

    if request.method == "POST":
        form = ATMCardVerifyForm(request.POST)

        if form.is_valid():
            card_no = form.cleaned_data['card_no']
            expiry = form.cleaned_data['expiry_date']

            try:
                card = ATMCard.objects.get(
                card_no=card_no,
                expiry_date__year=expiry.year,
                expiry_date__month=expiry.month
                )
            except ATMCard.DoesNotExist:
                messages.error(request, "Invalid card details")
                return render(request, "yourbank/atm_home.html", {'form': form})

            ok, msg = atm_guard(card)
            if not ok:
                messages.error(request, msg)
                return render(request, "yourbank/atm_home.html", {'form': form})

            request.session["atm_card_id"] = card.id
            return redirect("yourbank:pin_option")

    return render(request, "yourbank/atm_home.html", {'form': form})




# Step 2: PIN set/change options
def pin_option(request):
    card = get_object_or_404(ATMCard, id=request.session.get("atm_card_id"))

    ok, msg = atm_guard(card)
    if not ok:
        messages.error(request, msg)
        return redirect("yourbank:atm_home")

    return render(request, "yourbank/atm_options.html", {"card": card})



# Step 3: Ask mobile for OTP
from .bank_otp_service import send_bank_otp

def atm_request_otp(request):
    card = get_object_or_404(ATMCard, id=request.session.get("atm_card_id"))

    ok, msg = atm_guard(card)
    if not ok:
        messages.error(request, msg)
        return redirect("yourbank:atm_home")

    form = ATMMobileForm()

    if request.method == "POST":
        form = ATMMobileForm(request.POST)

        if form.is_valid():
            mobile = form.cleaned_data['mobile']

            if mobile != card.customer.mobile:
                messages.error(request, "Mobile number does not match bank records")
                return redirect("yourbank:atm_request_otp")

            BankOTP.objects.filter(card=card, verified=False).delete()

            otp = BankOTP.generate_otp()
            BankOTP.objects.create(
                card=card,
                otp=otp,
                mobile=mobile,
                reason="ATM_PIN",
                expiry=timezone.now() + timedelta(seconds=30)
            )

            print("OTP:", otp)

            request.session["atm_mobile"] = mobile
            return redirect("yourbank:atm_enter_otp")

    return render(request, "yourbank/atm_mobile.html", {"form": form})




# Step 4: Enter OTP
from .bank_otp_service import verify_bank_otp_yb

def atm_resend_otp(request):
    card = get_object_or_404(ATMCard, id=request.session.get("atm_card_id"))

    ok, msg = atm_guard(card)
    if not ok:
        messages.error(request, msg)
        return redirect("yourbank:atm_home")

    mobile = request.session.get("atm_mobile")

    BankOTP.objects.filter(card=card, verified=False).delete()

    otp = BankOTP.generate_otp()
    BankOTP.objects.create(
        card=card,
        otp=otp,
        mobile=mobile,
        reason="ATM_PIN",
        expiry=timezone.now() + timedelta(seconds=30)
    )

    print("OTP (Resent):", otp)

    return redirect("yourbank:atm_enter_otp")




from .bank_otp_service import send_bank_otp

def atm_enter_otp(request):
    card = get_object_or_404(ATMCard, id=request.session.get("atm_card_id"))

    ok, msg = atm_guard(card)
    if not ok:
        messages.error(request, msg)
        return redirect("yourbank:atm_home")

    form = ATMOTPForm()

    if request.method == "POST":
        form = ATMOTPForm(request.POST)

        if form.is_valid():
            otp = form.cleaned_data['otp']

            try:
                bankotp = BankOTP.objects.get(card=card, otp=otp, verified=False)
            except BankOTP.DoesNotExist:
                card.otp_attempts += 1
                card.save()

                # 🔒 Lock card after 3 wrong OTP
                if card.otp_attempts >= 3:
                    card.is_active = False
                    card.save()
                    clear_atm_session(request)
                    messages.error(request, "ATM Card blocked due to 3 wrong OTP attempts")
                    return redirect("yourbank:atm_home")

                remaining = 3 - card.otp_attempts
                messages.error(request, f"Invalid OTP. {remaining} attempts left")
                return render(request, "yourbank/atm_otp.html", {"form": form})


            if bankotp.is_expired():
                messages.error(request, "OTP expired")
                return render(request, "yourbank/atm_otp.html", {"form": form})

            bankotp.verified = True
            bankotp.save()

            card.otp_attempts = 0
            card.save()

            request.session["atm_verified"] = True
            return redirect("yourbank:atm_set_pin")

    return render(request, "yourbank/atm_otp.html", {"form": form})


# Step 5: Set new PIN

def atm_set_pin(request):
    card = get_object_or_404(ATMCard, id=request.session.get("atm_card_id"))

    ok, msg = atm_guard(card)
    if not ok:
        messages.error(request, msg)
        return redirect("yourbank:atm_home")

    if not request.session.get("atm_verified"):
        return redirect("yourbank:atm_home")

    form = ATMPinForm()

    if request.method == "POST":
        form = ATMPinForm(request.POST)

        if form.is_valid():
            p1 = form.cleaned_data['pin1']
            p2 = form.cleaned_data['pin2']

            if p1 != p2 or not p1.isdigit() or len(p1) != 4:
                messages.error(request, "PIN must be 4 digits and match")
                return redirect("yourbank:atm_set_pin")

            # ❗ Prevent using same current PIN
            # ❗ Prevent using same current PIN
            if card.pin and card.check_pin(p1):
                messages.error(request, "New PIN cannot be same as current PIN")
                return redirect("yourbank:atm_set_pin")

            # Save hashed PIN
            card.set_pin(p1)
            card.save()


            clear_atm_session(request)
            request.session["atm_pin_status"] = "success"
            return redirect("yourbank:atm_pin_result")


    return render(request, "yourbank/atm_set_pin.html", {"form": form})

def atm_pin_result(request):
    status = request.session.pop("atm_pin_status", None)

    if status == "success":
        return render(request, "yourbank/atm_pin_success.html")
    else:
        return render(request, "yourbank/atm_pin_failed.html")
