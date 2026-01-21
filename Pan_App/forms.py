from django import forms
from .models import Pan
from django.core.files.base import ContentFile
import base64
import random
from datetime import date

class PanCreateForm(forms.ModelForm):
    # hidden field to carry base64 image from camera capture
    photo_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Pan
        # aadhar is hidden/prefilled via view, address and mobile editable
        fields = ['aadhar', 'address', 'mobile']
        widgets = {
            'aadhar': forms.HiddenInput(),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Pull required fields from linked Aadhar
        a = instance.aadhar
        instance.name = a.name
        instance.father_name = a.father_name
        instance.dob = a.dob
        instance.gender = a.gender
        # default photo from aadhar if no new photo
        if not instance.photo and getattr(a, 'photo', None):
            # copy aadhar photo path as default (Django will store path to same file)
            instance.photo = a.photo

        # generate unique PAN if not already assigned
        if not getattr(instance, 'pan_no', None):
            instance.pan_no = self.generate_unique_pan()

        # handle camera-captured photo (base64)
        photo_data = self.cleaned_data.get('photo_data')
        if photo_data:
            fmt, imgstr = photo_data.split(';base64,')
            ext = fmt.split('/')[-1]
            filename = f"{instance.name}_{instance.pan_no}.{ext}"
            instance.photo.save(filename, ContentFile(base64.b64decode(imgstr)), save=False)

        if commit:
            instance.save()
        return instance

    def generate_unique_pan(self):
        # As per earlier spec: first 4 characters = 'ABCD', last 6 digits random unique
        for _ in range(1000):
            last6 = ''.join(str(random.randint(0, 9)) for _ in range(6))
            pan = 'ABCD' + last6
            if not Pan.objects.filter(pan_no=pan).exists():
                return pan
        raise RuntimeError("Unable to generate unique PAN")

class PanEditForm(forms.ModelForm):
    class Meta:
        model = Pan
        fields = ['name', 'father_name', 'gender', 'address', 'mobile', 'photo']
