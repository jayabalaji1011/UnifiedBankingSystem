from django.utils import timezone
from datetime import timedelta
from .models import AadharOTP
import random

def send_aadhar_otp(aadhar_instance, mobile, reason):
    # Invalidate old OTPs
    AadharOTP.objects.filter(
        aadhar=aadhar_instance,
        reason=reason,
        verified=False
    ).update(verified=True)

    otp = str(random.randint(100000, 999999))
    AadharOTP.objects.create(
        aadhar=aadhar_instance,
        otp=otp,
        reason=reason,
        mobile=mobile,
        expiry=timezone.now() + timedelta(minutes=2)
    )
    print("Aadhar OTP:", otp)
    return True, "OTP sent successfully"

def verify_aadhar_otp(aadhar_instance, mobile, reason, otp):
    try:
        record = AadharOTP.objects.filter(
            aadhar=aadhar_instance,
            mobile=mobile,
            reason=reason,
            verified=False
        ).latest('created_at')
    except AadharOTP.DoesNotExist:
        return False, "OTP not found"

    if record.is_expired():
        return False, "OTP expired"

    if record.otp != otp:
        return False, "Invalid OTP"

    record.verified = True
    record.save()
    return True, "OTP verified"
