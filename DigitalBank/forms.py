from django import forms
from .models import Customer, Transaction, Bank
from django.forms import DateInput
import datetime
from django.core.exceptions import ValidationError

class StaffLoginForm(forms.Form):
    username = forms.CharField(max_length=15, 
    label="Username",
    widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Username'})                         )
    password = forms.CharField(
    label='Password',        
    widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Password'})
    )


class CustomerCreateStartForm(forms.Form):
    aadhar_no = forms.CharField(max_length=19, label='Aadhar No (XXXX XXXX XXXX XXXX)')
    mobile = forms.CharField(max_length=10, label='Mobile')

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['bank','account_type','name','father_name','mobile','dob','gender','address','balance']
        widgets = {
            'dob': DateInput(attrs={'type':'date'}),
        }

class CustomerEditForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'father_name', 'mobile', 'address', 'photo']

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter name'
            }),
            'father_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter father name'
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter mobile number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,          # 🔥 Reduced height
                'placeholder': 'Enter address'
            }),
            'photo': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
        }



class TransactionForm(forms.ModelForm):

    transaction_type = forms.ChoiceField(
        choices=[
            ('DEPOSIT', 'Deposit'),
            ('WITHDRAW', 'Withdraw'),
            ('TRANSFER', 'Transfer'),
        ]
    )

    class Meta:
        model = Transaction
        fields = ['transaction_type','amount','receiver_account','note']
        widgets = {
            'amount': forms.NumberInput(attrs={'min': '1'}),
            'receiver_account': forms.TextInput(attrs={'placeholder': 'Enter Receiver Account'}),
            'note': forms.Textarea(attrs={'rows':1})
        }


class ATMCardVerifyForm(forms.Form):
    card_no = forms.CharField(
        max_length=16,
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder':'ATM Card Number'
        })
    )

    expiry_date = forms.CharField(
    max_length=5,
    widget=forms.TextInput(attrs={
        'class':'form-control',
        'id':'expiry',
        'autocomplete':'off'
    })
)



    def clean_expiry_date(self):
        data = self.cleaned_data['expiry_date']

        try:
            mm, yy = data.split('/')
            mm = int(mm)
            yy = int(yy)
            year = 2000 + yy

            # convert to real date → 2026-01-01
            expiry = datetime.date(year, mm, 1)

            # expired check
            if expiry < datetime.date.today().replace(day=1):
                raise ValidationError("Card is expired")

        except:
            raise ValidationError("Enter expiry as MM/YY (Eg: 01/26)")

        return expiry   # 🔥 this is now a DATE, not string


class ATMMobileForm(forms.Form):
    mobile = forms.CharField(max_length=15, widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Enter Mobile Number'}))


class ATMPinForm(forms.Form):
    pin1 = forms.CharField(max_length=4, widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Enter 4-digit PIN'}))
    pin2 = forms.CharField(max_length=4, widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Re-enter PIN'}))

class ATMOTPForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Enter OTP'})
    )

