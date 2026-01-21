from django import forms
from django.contrib.auth.forms import AuthenticationForm
from DigitalBank.models import *




class UPayLoginForm(forms.Form):
    mobile = forms.CharField(
        label="Mobile Number",   # ← ADD THIS
        max_length=10,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter Mobile Number"
        })
    )



class OTPForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        widget=forms.PasswordInput(attrs={
            "class":"form-control",
            "placeholder":"Enter OTP"
        })
    )





class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['bank', 'name', 'mobile', 'aadhar', 'dob', 'address', 'account_type', 'balance']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'aadhar': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,  
                'style': 'resize:none;'  
            }),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'balance': forms.NumberInput(attrs={'class': 'form-control',}),
            'bank': forms.Select(attrs={'class': 'form-control'}),
        }



class PinForm(forms.Form):
    old_pin = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Old PIN'})
    )
    new_pin = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New PIN'})
    )


# -------------------------- BANK SELECTION --------------------------
class SelectBankForm(forms.Form):
    bank = forms.ChoiceField(
        choices=[('DigitalBank', 'DigitalBank'), ('YourBank', 'YourBank')],
        widget=forms.RadioSelect
    )
    customer_id = forms.IntegerField(widget=forms.HiddenInput)  # Hidden, set per customer selection


# -------------------------- RECEIVER SELECTION --------------------------
class SelectReceiverForm(forms.Form):
    bank = forms.ChoiceField(
        choices=[('DigitalBank', 'DigitalBank'), ('YourBank', 'YourBank')],
        widget=forms.RadioSelect
    )
    customer_id = forms.IntegerField(widget=forms.HiddenInput)  # Hidden, set per customer selection



class BankVerifyForm(forms.Form):
    def __init__(self, method, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.method = method

        if method == "AADHAAR":
            self.fields['last_digits'] = forms.CharField(
                label="Aadhaar Last 6 Digits",
                max_length=6,
                min_length=6,
                widget=forms.TextInput(attrs={
                    "class": "form-control form-control-lg text-monospace",
                    "placeholder": "__ __ __",
                    "autocomplete": "off",
                    "inputmode": "numeric",
                    "pattern": "\d{6}",
                })
            )
        elif method == "DEBIT":
            self.fields['last6'] = forms.CharField(
                label="Debit Card Last 6 Digits",
                max_length=6,
                min_length=6,
                widget=forms.TextInput(attrs={
                    "class": "form-control form-control-lg text-monospace",
                    "placeholder": "__ ____",
                    "autocomplete": "off",
                    "inputmode": "numeric",
                    "pattern": "\d{6}",
                })
            )
            self.fields['expiry'] = forms.CharField(
                label="Expiry Date (MM/YY)",
                max_length=5,
                widget=forms.TextInput(attrs={
                    "class": "form-control form-control-lg text-center",
                    "placeholder": "MM/YY",
                    "autocomplete": "off",
                    "pattern": "(0[1-9]|1[0-2])\/\d{2}"
                })
            )


