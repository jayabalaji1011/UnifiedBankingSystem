from django.db import models
from django.utils import timezone
import os

def aadhar_photo_path(instance, filename):
    # App-specific media folder
    return os.path.join('AadharApp', 'media', 'aadhar_photos', filename)

GENDER_CHOICES = (
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other'),
)

class Aadhar(models.Model):
    name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    dob = models.DateField()
    address = models.TextField()
    mobile = models.CharField(max_length=10)
    aadhar_no = models.CharField(max_length=19, unique=True)  # 4-4-4-4 format
    photo = models.ImageField(upload_to='aadhar_photo_path')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.aadhar_no}"


class AadharOTP(models.Model):
    aadhar = models.ForeignKey(Aadhar, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    reason = models.CharField(max_length=50, default='Aadhar_Verifiation')
    mobile = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    expiry = models.DateTimeField()
    verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.expiry

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))