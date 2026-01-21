from django.utils import timezone
from datetime import timedelta
from .models import BankOTP
import random

def send_bank_otp(atmcard_instance, mobile, reason):
    # Invalidate old OTPs
    BankOTP.objects.filter(
        card=atmcard_instance,
        reason=reason,
        verified=False
    ).update(verified=True)

    otp = str(random.randint(100000, 999999))
    BankOTP.objects.create(
        card=atmcard_instance,
        otp=otp,
        reason=reason,
        mobile=mobile,
        expiry=timezone.now() + timedelta(minutes=2)
    )
    print("Bank OTP:", otp)
    return True, "OTP sent successfully"

def verify_bank_otp(atmcard_instance, mobile, reason, otp):
    try:
        record = BankOTP.objects.filter(
            card=atmcard_instance,
            mobile=mobile,
            reason=reason,
            verified=False
        ).latest('created_at')
    except BankOTP.DoesNotExist:
        return False, "OTP not found"

    if record.is_expired():
        return False, "OTP expired"

    if record.otp != otp:
        return False, "Invalid OTP"

    record.verified = True
    record.save()
    return True, "OTP verified"
