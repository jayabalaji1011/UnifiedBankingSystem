from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction as db_transaction
from django.http import HttpResponse
from django.contrib.auth.hashers import check_password, make_password
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

# Bank models
from DigitalBank.models import Customer as DBCustomer, Transaction as DBTransaction, BankTransaction as DBBankTransaction
from YourBank.models import Customer as YBCustomer, Transaction as YBTransaction, BankTransaction as YBBankTransaction
from Aadhar_App.models import Aadhar, AadharOTP

from .forms import *
from .models import UPayUser, UPayOTP

from Aadhar_App.aadhar_otp_service import send_aadhar_otp, verify_aadhar_otp
from YourBank.bank_otp_service import send_bank_otp, verify_bank_otp_yb
from DigitalBank.bank_otp_service import send_bank_otp as send_digitalbank_otp, verify_bank_otp as verify_digitalbank_otp


import time
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.urls import reverse


def generate_otp():
    return str(random.randint(100000, 999999))


# -------------------------- CUSTOMER LOGIN / LOGOUT --------------------------

def upay_login(request):
    if request.method == "POST":
        form = UPayLoginForm(request.POST)
        if form.is_valid():
            mobile = form.cleaned_data["mobile"]

            # Kill all old OTPs for safety
            UPayOTP.objects.filter(
                mobile=mobile,
                purpose="LOGIN"
            ).update(is_used=True)

            otp = generate_otp()

            UPayOTP.objects.create(
                mobile=mobile,
                otp=otp,
                purpose="LOGIN",
                is_used=False
            )

            print("UPay OTP:", otp)

            request.session["upay_mobile"] = mobile
            return redirect("upay_verify")
    else:
        form = UPayLoginForm()

    return render(request, "upay/customer_login.html", {"form": form})


def upay_verify(request):
    mobile = request.session.get("upay_mobile")

    if not mobile:
        return redirect("upay_login")

    if request.method == "POST":
        entered = request.POST.get("otp")

        try:
            # Always get latest unused OTP
            otp_obj = UPayOTP.objects.filter(
                mobile=mobile,
                purpose="LOGIN",
                is_used=False
            ).latest("created_at")
        except UPayOTP.DoesNotExist:
            messages.error(request, "OTP expired. Click resend.")
            return redirect("upay_verify")

        if otp_obj.otp != entered:
            messages.error(request, "Invalid OTP")
            return redirect("upay_verify")

        # Mark OTP used
        otp_obj.is_used = True
        otp_obj.save()

        # Create or get UPay user
        user, _ = UPayUser.objects.get_or_create(mobile=mobile)

        request.session["upay_user_id"] = user.id
        request.session.pop("upay_mobile", None)

        return redirect("home")

    return render(request, "upay/login_otp.html", {"mobile": mobile})




def upay_resend(request):
    mobile = request.session.get("upay_mobile")

    if not mobile:
        return redirect("upay_login")

    # Kill old OTPs
    UPayOTP.objects.filter(
        mobile=mobile,
        purpose="LOGIN"
    ).update(is_used=True)

    otp = generate_otp()

    UPayOTP.objects.create(
        mobile=mobile,
        otp=otp,
        purpose="LOGIN",
        is_used=False
    )

    print("Resent OTP:", otp)

    return redirect("upay_verify")

def customer_dashboard(request):
    customer = get_current_customer(request)
    if not customer:
        return redirect('upay_login')

    bank_app = request.session.get("bank_app")
    customer_id = request.session.get("customer_id")

    bank_name = None
    bank_customer = None
    bank_linked = False

    if bank_app and customer_id:
        bank_linked = True

        if bank_app == "DigitalBank":
            bank_name = "Digital Bank"
            bank_customer = DBCustomer.objects.filter(customer_id=customer_id).first()
            tx_model = DBTransaction
        else:
            bank_name = "Your Bank"
            bank_customer = YBCustomer.objects.filter(customer_id=customer_id).first()
            tx_model = YBTransaction
    else:
        tx_model = None

    transactions = []
    if bank_customer:
        transactions = tx_model.objects.filter(customer=bank_customer).order_by('-date')[:3]

    return render(request, 'upay/customer_dashboard.html', {
        'customer': customer,               # UPay user
        'bank_name': bank_name,             # Digital Bank / Your Bank
        'bank_customer': bank_customer,     # Real bank account
        'bank_linked': bank_linked,
        'transactions': transactions,
        'show_navbar': True
    })



def unlink_bank(request):
    if request.session.get('bank_app'):
        request.session.pop('bank_app', None)
        request.session.pop('customer_id', None)
        messages.success(request, "Bank unlinked successfully!")
    else:
        messages.info(request, "No bank linked")

    return redirect('home')



# -------------------- LOGOUT UPay (unlink bank automatically) --------------------
def logout_customer(request):
    # flush session clears bank info and UPay login
    request.session.flush()
    messages.success(request, "Logged out successfully!")
    return redirect("upay_login")


# -------------------------- HOME / DASHBOARD / BALANCE --------------------------

def get_current_customer(request):
    cid = request.session.get("customer_id")
    bank_app = request.session.get("bank_app")

    if not cid or not bank_app:
        return None

    if bank_app == "DigitalBank":
        return get_object_or_404(DBCustomer, customer_id=cid)
    else:
        return get_object_or_404(YBCustomer, customer_id=cid)




def home(request):
def home(request):
    user_id = request.session.get("upay_user_id")
    if not user_id:
        return redirect("upay_login")

    user = get_object_or_404(UPayUser, id=user_id)

    bank_app = request.session.get("bank_app")
    customer_id = request.session.get("customer_id")  # ✅ fixed
    balance = request.session.pop("balance_check_result", None)

    # Determine bank name
    bank_name = None
    if bank_app == "DigitalBank":
        bank_name = "Digital Bank"
    elif bank_app == "YourBank":
        bank_name = "Your Bank"

    bank_linked = True if bank_app and customer_id else False

    bank_customer = None
    if bank_linked:
        if bank_app == "DigitalBank":
            bank_customer = DBCustomer.objects.filter(customer_id=customer_id).first()
        else:
            bank_customer = YBCustomer.objects.filter(customer_id=customer_id).first()

    return render(request, "upay/customer_home.html", {
        "user": user,
        "bank_name": bank_name,
        "bank_linked": bank_linked,
        "bank_customer": bank_customer,
        "balance": balance,
        "check_pin_popup": False,
        "show_balance_popup": True if balance else False,
        "show_navbar": True,
    })




# List of available banks
AVAILABLE_BANKS = ["DigitalBank", "YourBank"]


# -------------------- ADD BANK --------------------
def add_bank(request):
    user = get_object_or_404(UPayUser, id=request.session.get("upay_user_id"))

    if request.method == "POST":
        bank = request.POST.get("bank")

        if bank == "DigitalBank":
            customer = DBCustomer.objects.filter(mobile=user.mobile).first()
        else:
            customer = YBCustomer.objects.filter(mobile=user.mobile).first()

        if not customer:
            messages.error(request, "Mobile No Doesn't Match Selected Bank!")
            return redirect("add_bank")

        # store bank + customer
        request.session["link_bank"] = bank
        request.session["link_customer_id"] = customer.customer_id

        # redirect to new processing page
        return redirect("add_bank_processing")

    return render(request, "upay/add_bank.html", {"banks": AVAILABLE_BANKS})


def add_bank_processing(request):
    user_id = request.session.get("upay_user_id")
    if not user_id:
        return redirect("upay_login")

    # Safety check
    if "link_bank" not in request.session or "link_customer_id" not in request.session:
        return redirect("add_bank")

    return render(request, "upay/add_bank_processing.html", {"show_navbar": False})



def add_bank_processing_check(request):
    user_id = request.session.get("upay_user_id")
    if not user_id:
        return JsonResponse({"status": "ERROR", "redirect": reverse("upay_login")})

    bank = request.session.get("link_bank")
    user = get_object_or_404(UPayUser, id=user_id)

    if not bank:
        return JsonResponse({"status": "FAILED", "redirect": reverse("add_bank")})

    # Fetch all accounts of this user for the selected bank
    if bank == "DigitalBank":
        accounts = list(DBCustomer.objects.filter(mobile=user.mobile))
    else:
        accounts = list(YBCustomer.objects.filter(mobile=user.mobile))

    if not accounts:
        # No accounts found
        return JsonResponse({"status": "FAILED", "redirect": reverse("add_bank")})

    # Save all accounts in session for verification
    request.session["multi_bank_accounts"] = [
        {"id": c.customer_id, "name": c.name} for c in accounts
    ]
    request.session.modified = True

    # Redirect to verification method selection
    return JsonResponse({"status": "SUCCESS", "redirect": reverse("link_method")})



def link_method(request):
    user_id = request.session.get("upay_user_id")
    if not user_id:
        return redirect("upay_login")

    if request.method == "POST":
        method = request.POST.get("method")
        if method not in ["AADHAAR", "DEBIT"]:
            messages.error(request, "Invalid method selected")
            return redirect("link_method")
        
        # Save in session
        request.session["link_method"] = method
        request.session.modified = True  # ⚡ Ensure session is saved
        return redirect("link_bank_verify")

    return render(request, "upay/select_verify_method.html", {"methods": ["AADHAAR", "DEBIT"]})

def link_bank_verify(request):
    user_id = request.session.get("upay_user_id")
    if not user_id:
        return redirect("upay_login")

    upay_user = get_object_or_404(UPayUser, id=user_id)
    mobile = upay_user.mobile
    bank = request.session.get("link_bank")
    method = request.session.get("link_method")
    multi_accounts = request.session.get("multi_bank_accounts", [])

    if not bank or not method or not multi_accounts:
        return redirect("add_bank")

    if request.method == "POST":
        form = BankVerifyForm(method, request.POST)
        if form.is_valid():
            selected_account = None

            if method == "AADHAAR":
                last_digits = form.cleaned_data['last_digits']

                for acct_data in multi_accounts:
                    acct_id = acct_data["id"]
                    customer = get_object_or_404(DBCustomer if bank=="DigitalBank" else YBCustomer, customer_id=acct_id)
                    if customer.aadhar:
                        stored = customer.aadhar.aadhar_no.replace(" ", "")  # remove spaces

                        if len(stored) == 16 and stored[-6:] == last_digits:
                            selected_account = customer
                            break


                if not selected_account:
                    messages.error(request, "Aadhaar last 6 digits mismatch!")
                    return redirect("'link_bank_verify")

                send_aadhar_otp(selected_account.aadhar, mobile, "BANK_LINK")
                request.session["bank_verify_type"] = "AADHAAR"
                request.session["selected_customer_id"] = selected_account.customer_id
                return redirect("verify_bank_otp_logic")

            elif method == "DEBIT":
                last6 = form.cleaned_data['last6']
                expiry = form.cleaned_data['expiry']

                for acct_data in multi_accounts:
                    acct_id = acct_data["id"]
                    customer = get_object_or_404(DBCustomer if bank=="DigitalBank" else YBCustomer, customer_id=acct_id)
                    atmcard = getattr(customer, "atmcard", None)
                    if atmcard and atmcard.card_no[-6:] == last6 and atmcard.expiry_date.strftime("%m/%y") == expiry:
                        selected_account = customer
                        break

                if not selected_account:
                    messages.error(request, "Debit card details mismatch!")
                    return redirect("link_bank_verify")

                # Send bank OTP
                atmcard = selected_account.atmcard
                if bank == "DigitalBank":
                    send_digitalbank_otp(atmcard, mobile, "BANK_LINK")
                else:
                    send_bank_otp(atmcard, mobile, "BANK_LINK")

                request.session["bank_verify_type"] = "DEBIT"
                request.session["selected_customer_id"] = selected_account.customer_id
                return redirect("verify_bank_otp_logic")
    else:
        form = BankVerifyForm(method)

    # For display, pick first account temporarily
    first_account = get_object_or_404(DBCustomer if bank=="DigitalBank" else YBCustomer, customer_id=multi_accounts[0]["id"])
    atmcard = getattr(first_account, "atmcard", None)

    first_part = ""
    last_placeholder = ""
    if method == "AADHAAR" and first_account.aadhar:
        full = first_account.aadhar.aadhar_no.replace(" ", "")  # remove spaces

        if len(full) != 16:
            messages.error(request, "Invalid Aadhaar stored in bank")
            return redirect("add_bank")

        first_part = full[:10]
        last_placeholder = "______"


    elif method == "DEBIT" and atmcard:
        full = atmcard.card_no

        if len(full) != 12:
            messages.error(request, "Invalid Debit Card stored in bank")
            return redirect("add_bank")

        first_part = full[:6]   # first 6 hidden
        last_placeholder = "______"


    return render(request, "upay/link_bank_verify.html", {
        "form": form,
        "method": method,
        "customer": first_account,
        "atmcard": atmcard,
        "first_part": first_part,
        "last_placeholder": last_placeholder
    })



def verify_bank_otp_logic(request):
    user_id = request.session.get("upay_user_id")
    if not user_id:
        return redirect("upay_login")

    upay_user = get_object_or_404(UPayUser, id=user_id)
    mobile = upay_user.mobile
    bank = request.session.get("link_bank")
    method = request.session.get("bank_verify_type")
    customer_id = request.session.get("selected_customer_id")

    if not bank or not method or not customer_id:
        return redirect("add_bank")

    customer = get_object_or_404(DBCustomer if bank=="DigitalBank" else YBCustomer, customer_id=customer_id)
    atmcard = getattr(customer, "atmcard", None)

    # 🔁 RESEND OTP
    if request.method == "POST" and "resend_otp" in request.POST:
        if method == "AADHAAR":
            send_aadhar_otp(customer.aadhar, mobile, "BANK_LINK")
        else:
            if bank == "DigitalBank":
                send_digitalbank_otp(atmcard, mobile, "BANK_LINK")
            else:
                send_bank_otp(atmcard, mobile, "BANK_LINK")

        messages.success(request, "OTP resent successfully")
        return redirect("verify_bank_otp_logic")

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        if method == "AADHAAR":
            ok, msg = verify_aadhar_otp(customer.aadhar, mobile, "BANK_LINK", entered_otp)
        else:  # DEBIT
            if bank == "DigitalBank":
                ok, msg = verify_digitalbank_otp(atmcard, mobile, "BANK_LINK", entered_otp)
            else:
                ok, msg = verify_bank_otp_yb(atmcard, mobile, "BANK_LINK", entered_otp)


        if not ok:
            messages.error(request, msg)
            return redirect("verify_bank_otp_logic")

        # OTP verified → link bank
        request.session["bank_app"] = bank
        request.session["customer_id"] = customer.customer_id
        request.session["customer_name"] = customer.name

        # Cleanup temp session variables
        for key in ["link_bank", "multi_bank_accounts", "selected_customer_id", "bank_verify_type", "link_method"]:
            request.session.pop(key, None)

        if method == "DEBIT":
            return redirect("bank_pin_verify")
        else:
            messages.success(request, "Bank linked successfully!")
            return redirect("set_or_change_pin")

    return render(request, "upay/bank_otp.html", {
        "method": method,
        "customer": customer,
        "mobile": mobile
    })



def bank_pin_verify(request):
    # 1️⃣ Ensure UPay user is logged in
    user_id = request.session.get("upay_user_id")
    if not user_id:
        return redirect("upay_login")

    # 2️⃣ Ensure bank is linked in session
    bank = request.session.get("bank_app")
    customer_id = request.session.get("customer_id")  # this should already be the verified customer

    if not bank or not customer_id:
        messages.error(request, "No bank selected for verification.")
        return redirect("add_bank")

    # 3️⃣ Get the bank customer (the one actually linked)
    customer = get_object_or_404(DBCustomer if bank == "DigitalBank" else YBCustomer, customer_id=customer_id)

    # 4️⃣ Ensure customer has an ATM card
    atmcard = getattr(customer, "atmcard", None)
    if not atmcard:
        messages.error(request, "No ATM card linked with this account.")
        return redirect("add_bank")

    if request.method == "POST":
        atm_pin = request.POST.get("atm_pin", "").strip()

        # Validate PIN format
        if not atm_pin or len(atm_pin) != 4 or not atm_pin.isdigit():
            messages.error(request, "ATM PIN must be exactly 4 digits.")
            return redirect("bank_pin_verify")

        # Check PIN against existing ATM card
        if not atmcard.check_pin(atm_pin):
            atmcard.otp_attempts += 1  # track failed attempts
            atmcard.save()
            messages.error(
                request,
                f"Incorrect ATM PIN! Attempt {atmcard.otp_attempts}."
            )
            return redirect("bank_pin_verify")

        # ✅ PIN correct → bank successfully linked
        messages.success(request, "Bank linked successfully!")
        return redirect("set_or_change_pin")

    # GET → render PIN entry page
    return render(request, "upay/atm_pin_verify.html", {
        "customer": customer,
        "show_navbar": True
    })






# -------------------------- SEND MONEY --------------------------
def send_money(request):
    customer = get_current_customer(request)
    if not customer:
        return redirect("upay_login")

    if request.method == "POST":
        recipient_input = request.POST.get("recipient", "").strip()
        amount_input = request.POST.get("amount", "").strip()

        if not recipient_input or not amount_input:
            messages.error(request, "Enter recipient and amount")
            return redirect("home")

        # Validate amount
        try:
            amount = Decimal(amount_input)
            if amount <= 0:
                messages.error(request, "Invalid amount!")
                return redirect("home")
        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid amount!")
            return redirect("home")

        receiver = None

        # ------------------- Lookup by account number -------------------
        if recipient_input.isdigit() and len(recipient_input) == 12:
            receiver = DBCustomer.objects.filter(account_no=recipient_input).first() or \
                       YBCustomer.objects.filter(account_no=recipient_input).first()
            if not receiver:
                messages.error(request, "Account not found! Please check recipient details.")
                return redirect("home")

        # ------------------- Lookup by mobile number -------------------
        elif recipient_input.isdigit() and len(recipient_input) == 10:
            db_list = list(DBCustomer.objects.filter(mobile=recipient_input))
            yb_list = list(YBCustomer.objects.filter(mobile=recipient_input))
            total_matches = db_list + yb_list

            if len(total_matches) == 0:
                messages.error(request, "Mobile number not found! Please check recipient details.")
                return redirect("home")
            elif len(total_matches) == 1:
                receiver = total_matches[0]
            else:
                # Multiple matches → select bank
                request.session['multi_receiver_candidates'] = [
                    {'bank': 'DigitalBank', 'id': c.customer_id, 'name': c.name} for c in db_list
                ] + [
                    {'bank': 'YourBank', 'id': c.customer_id, 'name': c.name} for c in yb_list
                ]
                request.session['send_money_amount'] = str(amount)
                request.session['recipient_input'] = recipient_input
                return redirect('select_receiver')
        else:
            messages.error(request, "Invalid Number")
            return redirect("home")

        # Prevent sending to self
        if receiver.customer_id == getattr(customer, "customer_id", None) and receiver._meta.app_label == request.session.get('bank_app'):
            messages.error(request, "You cannot send money to yourself!")
            return redirect("home")


        # Insufficient balance
        if customer.balance < amount:
            messages.error(request, "Insufficient balance!")
            return redirect("home")

        # Store transaction data in session
        request.session['send_money_data'] = {
            'receiver_id': receiver.customer_id,
            'amount': str(amount),
            'recipient_input': recipient_input,
            'receiver_bank': receiver._meta.app_label
        }

        return redirect("send_money_pin", customer_id=customer.customer_id)

    # GET request → show send money form
    return redirect("home")



def select_receiver(request):
    candidates = request.session.get('multi_receiver_candidates')
    if not candidates:
        return redirect('send_money')

    if request.method == "POST":
        selected = request.POST.get('selected')
        if not selected:
            messages.error(request, "Please select a receiver.")
            return redirect('select_receiver')

        bank, customer_id = selected.split('|')
        customer_id = int(customer_id)

        if bank == 'DigitalBank':
            receiver = get_object_or_404(DBCustomer, customer_id=customer_id)
        else:
            receiver = get_object_or_404(YBCustomer, customer_id=customer_id)

        amount = Decimal(request.session.get('send_money_amount'))
        recipient_input = request.session.get('recipient_input')

        request.session['send_money_data'] = {
            'receiver_id': receiver.customer_id,
            'amount': str(amount),
            'recipient_input': recipient_input,
            'receiver_bank': bank
        }

        request.session.pop('multi_receiver_candidates', None)
        request.session.pop('send_money_amount', None)
        request.session.pop('recipient_input', None)

        customer = get_current_customer(request)
        return redirect("send_money_pin", customer_id=customer.customer_id)

    # ✅ FINAL FIX HERE
    grouped = {'DigitalBank': [], 'YourBank': []}

    for item in candidates:
        bank = item.get('bank')
        customer_id = item.get('customer_id') or item.get('id')

        if not bank or not customer_id:
            continue  # safety

        if bank == 'DigitalBank':
            cust = DBCustomer.objects.get(customer_id=customer_id)
        else:
            cust = YBCustomer.objects.get(customer_id=customer_id)

        grouped[bank].append(cust)

    return render(request, "upay/select_receiver.html", {
        'candidates': grouped,
        'show_navbar': True
    })




# -------------------------- SEND MONEY PIN / PROCESS --------------------------

def send_money_pin(request, customer_id):
    customer = get_current_customer(request)
    if not customer:
        return redirect("upay_login")

    send_data = request.session.get("send_money_data")
    if not send_data:
        messages.error(request, "Session expired. Re-enter recipient and amount.")
        return redirect("send_money")

    receiver_id = send_data.get("receiver_id")
    receiver_bank = send_data.get("receiver_bank")
    receiver_model = DBCustomer if receiver_bank == 'DigitalBank' else YBCustomer
    receiver = get_object_or_404(receiver_model, customer_id=receiver_id)

    # ------------------ UPay display / storage logic ------------------

# check how user sent money (account or mobile)
    sent_by_mobile = (
    send_data.get("recipient_input").isdigit() and
    len(send_data.get("recipient_input")) == 10
)

# check same bank or other bank
    is_cross_bank = receiver._meta.app_label != request.session['bank_app']

# ALWAYS store pure account numbers (never bank/account mixed)
    sender_account = customer.account_no
    receiver_account = receiver.account_no


    try:
        amount = Decimal(send_data.get("amount") or "0")
    except:
        messages.error(request, "Invalid amount in session.")
        return redirect("send_money")


    if request.method == "GET":
        return render(request, "upay/send_money_pin.html", {
            "customer": customer,
            "receiver": receiver,
            "amount": amount,
            "recipient_input": send_data.get("recipient_input"),
            "show_navbar": True,
        })

    # POST → process
    pin = request.POST.get("pin", "").strip()
    if not customer.transaction_pin:
        messages.error(request, "No transaction PIN set. Please set PIN first.")
        return redirect("set_or_change_pin")

    if not check_password(pin, customer.transaction_pin):
        messages.error(request, "Incorrect PIN!")
        return redirect("send_money_pin", customer_id=customer_id)

    if receiver.customer_id == customer.customer_id and receiver._meta.app_label == request.session['bank_app']:
        messages.error(request, "Cannot send money to yourself!")
        return redirect("send_money")

    if amount <= 0 or customer.balance < amount:
        messages.error(request, "Invalid or insufficient balance!")
        return redirect("send_money")

    # -------------------- Process transaction --------------------
    with db_transaction.atomic():
        # Sender
        sender_before = customer.balance
        customer.balance -= amount
        customer.save()
        sender_after = customer.balance

        tx_model = DBTransaction if request.session['bank_app'] == 'DigitalBank' else YBTransaction
        bank_model = DBBankTransaction if request.session['bank_app'] == 'DigitalBank' else YBBankTransaction
        bank_instance = customer.bank

        tx_model.objects.create(
    customer=customer,
    transaction_type="DEBIT",
    amount=amount,
    balance_before=sender_before,
    balance_after=sender_after,

    sender_account=customer.account_no,
    receiver_account=receiver.account_no,

    sender_bank=request.session['bank_app'] if is_cross_bank else None,
    receiver_bank=receiver._meta.app_label if is_cross_bank else None,

    sender_mobile=customer.mobile,
    receiver_mobile=receiver.mobile if sent_by_mobile else '',
)



        if bank_instance:
            bank_before = bank_instance.balance
            bank_instance.balance -= amount
            bank_instance.save()
            bank_model.objects.create(
    bank=bank_instance,
    customer=customer,
    transaction_type="DEBIT",
    amount=amount,
    balance_before=bank_before,
    balance_after=bank_instance.balance,

    sender_account=customer.account_no,
    receiver_account=receiver.account_no,

    sender_bank=request.session['bank_app'] if is_cross_bank else None,
    receiver_bank=receiver._meta.app_label if is_cross_bank else None,

    sender_mobile=customer.mobile,
    receiver_mobile=receiver.mobile if sent_by_mobile else '',
)



        # Receiver
        receiver_before = receiver.balance
        receiver.balance += amount
        receiver.save()
        r_tx_model = DBTransaction if receiver._meta.app_label == 'DigitalBank' else YBTransaction
        r_bank_model = DBBankTransaction if receiver._meta.app_label == 'DigitalBank' else YBBankTransaction
        r_bank_instance = receiver.bank

        r_tx_model.objects.create(
    customer=receiver,
    transaction_type="CREDIT",
    amount=amount,
    balance_before=receiver_before,
    balance_after=receiver.balance,

    sender_account=customer.account_no,
    receiver_account=receiver.account_no,

    sender_bank=request.session['bank_app'] if is_cross_bank else None,
    receiver_bank=receiver._meta.app_label if is_cross_bank else None,

    sender_mobile=customer.mobile,
    receiver_mobile=receiver.mobile if sent_by_mobile else '',
)



        if r_bank_instance:
            bank_before = r_bank_instance.balance
            r_bank_instance.balance += amount
            r_bank_instance.save()
            r_bank_model.objects.create(
    bank=r_bank_instance,
    customer=receiver,
    transaction_type="CREDIT",
    amount=amount,
    balance_before=bank_before,
    balance_after=r_bank_instance.balance,

    sender_account=customer.account_no,
    receiver_account=receiver.account_no,

    sender_bank=request.session['bank_app'] if is_cross_bank else None,
    receiver_bank=receiver._meta.app_label if is_cross_bank else None,

    sender_mobile=customer.mobile,
    receiver_mobile=receiver.mobile if sent_by_mobile else '',
)

    # store finish time instead of using thread
    request.session["txn_status"] = "PENDING"
    request.session["txn_finish_at"] = (timezone.now() + timedelta(seconds=random.randint(3, 8))).timestamp()


    return redirect("upay_processing_page")





def upay_processing_page(request):
    return render(request, "upay/upay_processing.html", {"show_navbar": False})


def upay_processing_check(request):
    status = request.session.get("txn_status", "PENDING")
    finish_at = request.session.get("txn_finish_at")

    if status == "PENDING" and finish_at:
        if timezone.now().timestamp() >= finish_at:
            request.session["txn_status"] = "SUCCESS"
            request.session.pop("txn_finish_at", None)
            status = "SUCCESS"

    return JsonResponse({"status": status})



# -------------------------- SEND MONEY SUCCESS --------------------------

def send_money_success(request):
    customer = get_current_customer(request)
    if not customer:
        return redirect("upay_login")

    send_data = request.session.pop("send_money_data", {})  # ✅ POP here
    receiver_id = send_data.get("receiver_id")
    receiver_bank = send_data.get("receiver_bank")

    receiver = None
    if receiver_id and receiver_bank:
        receiver_model = DBCustomer if receiver_bank == 'DigitalBank' else YBCustomer
        receiver = receiver_model.objects.filter(customer_id=receiver_id).first()

    return render(request, "upay/send_money_success.html", {
        "customer": customer,
        "receiver": receiver,
        "recipient_input": send_data.get("recipient_input"),
        "amount": send_data.get("amount"),
        "show_navbar": True
    })


def send_money_failed(request):
    customer = get_current_customer(request)
    if not customer:
        return redirect("upay_login")

    send_data = request.session.pop("send_money_data", {})  # ✅ POP here

    receiver_id = send_data.get("receiver_id")
    receiver_bank = send_data.get("receiver_bank")

    receiver = None
    if receiver_id and receiver_bank:
        receiver_model = DBCustomer if receiver_bank == 'DigitalBank' else YBCustomer
        receiver = receiver_model.objects.filter(customer_id=receiver_id).first()

    return render(request, "upay/send_money_failed.html", {
        "customer": customer,
        "receiver": receiver,
        "recipient_input": send_data.get("recipient_input"),
        "amount": send_data.get("amount"),
        "show_navbar": True
    })



# -------------------------- BALANCE --------------------------

def check_balance(request):
    customer = get_current_customer(request)
    if not customer:
        return redirect("upay_login")

    if request.method == "POST":
        pin = request.POST.get("pin")

        if not check_password(pin, customer.transaction_pin):
            messages.error(request, "Incorrect PIN!")
            return redirect("home")

        # ✅ store balance in session
        request.session["balance_check_result"] = str(customer.balance)
        messages.success(request, "Balance fetched successfully")
        return redirect("home")

    return redirect("home")


# -------------------------- SET / CHANGE PIN --------------------------

def set_or_change_pin(request):
    customer = get_current_customer(request)
    if not customer:
        return redirect("upay_login")

    if request.method == "POST":
        old_pin = request.POST.get("old_pin", "").strip()
        new_pin = request.POST.get("new_pin", "").strip()

        if customer.transaction_pin and not check_password(old_pin, customer.transaction_pin):
            messages.error(request, "Old PIN is incorrect.")
            return redirect("set_or_change_pin")

        if not new_pin.isdigit() or len(new_pin) != 6:
            messages.error(request, "New PIN must be exactly 6 digits!")
            return redirect("set_or_change_pin")

        customer.transaction_pin = make_password(new_pin)
        customer.save()
        messages.success(request, "PIN updated successfully!")
        return redirect("home")

    return render(request, "upay/customer_upipin.html", {"customer": customer, "show_navbar": True})


# -------------------------- DASHBOARD + TRANSACTIONS --------------------------



def my_transaction(request):
    customer = get_current_customer(request)
    if not customer:
        return redirect('upay_login')

    tx_model = DBTransaction if request.session['bank_app'] == 'DigitalBank' else YBTransaction
    transactions = tx_model.objects.filter(customer=customer).order_by('-date')

    for txn in transactions:
        if txn.transaction_type == "CREDIT":
            txn.display_type = "Credit/UPI"
        elif txn.transaction_type == "DEBIT":
            txn.display_type = "Debit/UPI"
        else:
            txn.display_type = txn.get_transaction_type_display()

    return render(request, 'upay/my_transaction.html', {
        'customer': customer,
        'transactions': transactions,
        'show_navbar': True
    })


# -------------------------- PDF EXPORT --------------------------

def customer_transactions_pdf(request, customer_id):
    customer = get_current_customer(request)
    if not customer:
        return redirect('upay_login')

    tx_model = DBTransaction if request.session.get('bank_app') == 'DigitalBank' else YBTransaction
    transactions = tx_model.objects.filter(customer=customer).order_by('-date')

    masked_acc = f"******{customer.account_no[-4:]}"
    masked_mobile = f"{customer.mobile[:5]}{'*'*5}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Transaction Report", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Name:</b> {customer.name}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Account No:</b> {masked_acc}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Mobile:</b> {masked_mobile}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    data = [["Date", "Sender", "Receiver", "Type", "Amount", "Previous Balance", "Current Balance"]]

    for txn in transactions:
        # Transaction type display
        if txn.transaction_type == "CREDIT":
            display_type = "Credit/UPI"
        elif txn.transaction_type == "DEBIT":
            display_type = "Debit/UPI"
        else:
            display_type = txn.get_transaction_type_display()

        # Safe account masking
        sender_acc = txn.sender_account
        receiver_acc = txn.receiver_account

        sender_display = f"******{sender_acc[-4:]}" if sender_acc else "-"
        receiver_display = f"******{receiver_acc[-4:]}" if receiver_acc else "-"

        # Include bank if different from customer's bank
        if txn.sender_bank and txn.sender_bank != customer.bank.name:
            sender_display = f"{txn.sender_bank} | {sender_display}"
        if txn.receiver_bank and txn.receiver_bank != customer.bank.name:
            receiver_display = f"{txn.receiver_bank} | {receiver_display}"

        data.append([
            txn.date.strftime("%d-%m-%Y %H:%M"),
            sender_display,
            receiver_display,
            display_type,
            f"₹ {txn.amount}",
            f"₹ {txn.balance_before}",
            f"₹ {txn.balance_after}",
        ])

    table = Table(data, hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightblue),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return HttpResponse(
        buffer,
        content_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=transactions.pdf"}
    )

