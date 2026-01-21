from django.db import models

# Create your models here.
class UPayUser(models.Model):
    mobile = models.CharField(max_length=10, unique=True)
    bank_app = models.CharField(max_length=20, blank=True, null=True)   # DigitalBank / YourBank
    customer_id = models.IntegerField(blank=True, null=True)          # Bank customer_id
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.mobile


class UPayOTP(models.Model):
    mobile = models.CharField(max_length=10)
    otp = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20)  # LOGIN / BANK_LINK
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

