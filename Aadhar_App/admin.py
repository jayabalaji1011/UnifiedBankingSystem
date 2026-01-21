from django.contrib import admin
from .models import Aadhar, AadharOTP

@admin.register(Aadhar)
class AadharAdmin(admin.ModelAdmin):
    list_display = ['name', 'father_name', 'mobile', 'aadhar_no']

@admin.register(AadharOTP)
class AadharOTPAdmin(admin.ModelAdmin):
    list_display = ('id', 'mobile', 'otp', 'verified', 'expiry', 'reason', 'aadhar')
    list_filter = ('verified', 'reason')
    search_fields = ('mobile', 'otp', 'aadhar__aadhar_no')