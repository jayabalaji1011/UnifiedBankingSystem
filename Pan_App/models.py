import os
from django.db import models
from django.utils import timezone
# adjust import path to match your aadhar app name
from Aadhar_App.models import Aadhar

def pan_photo_path(instance, filename):
    # store inside project media in PanApp/media/pan_photos/
    return os.path.join('PanApp', 'media', 'pan_photos', filename)

class Pan(models.Model):
    GENDER_CHOICES = (
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other'),
)
    # PAN linked to Aadhar
    aadhar = models.OneToOneField(Aadhar, on_delete=models.CASCADE, related_name='pan')
    pan_no = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100)
    dob = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    mobile = models.CharField(max_length=10)
    address = models.TextField()
    photo = models.ImageField(upload_to=pan_photo_path, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pan_no} - {self.name}"
