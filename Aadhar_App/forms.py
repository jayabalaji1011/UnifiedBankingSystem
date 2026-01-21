from django import forms
from .models import Aadhar
from django.core.files.base import ContentFile
import base64
import random
from django.db import IntegrityError

class AadharCreateForm(forms.ModelForm):
    photo_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Aadhar
        fields = ['name','father_name','gender','dob','address','mobile']
        widgets = {
            'dob': forms.DateInput(attrs={'type':'date'}),
        }

    def generate_unique_aadhar(self):
        for _ in range(100):
            num = ''.join([str(random.randint(0,9)) for _ in range(16)])
            formatted = ' '.join([num[i:i+4] for i in range(0,16,4)])
            if not Aadhar.objects.filter(aadhar_no=formatted).exists():
                return formatted
        raise IntegrityError('Could not generate unique Aadhar')

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Generate unique Aadhar if not provided
        if not getattr(instance, 'aadhar_no', None):
            instance.aadhar_no = self.generate_unique_aadhar()
        # Photo handling
        photo_data = self.cleaned_data.get('photo_data')
        if photo_data:
            format, imgstr = photo_data.split(';base64,')
            ext = format.split('/')[-1]
            instance.photo.save(f"{instance.name}.{ext}", ContentFile(base64.b64decode(imgstr)), save=False)
        if commit:
            instance.save()
        return instance

class AadharEditForm(forms.ModelForm):
    class Meta:
        model = Aadhar
        fields = ['name', 'father_name', 'gender', 'address', 'mobile', 'photo']

