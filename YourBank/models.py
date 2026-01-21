from django.db import models
from django.utils import timezone
from Aadhar_App.models import Aadhar
from Pan_App.models import Pan
import random
from datetime import timedelta
from django.contrib.auth.hashers import make_password, check_password



# ----------------- Bank -----------------
class Bank(models.Model):
    name = models.CharField(max_length=200)
    ifsc = models.CharField(max_length=20, unique=True)
    branch = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    state = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bank_prefix = models.CharField(max_length=4, default='2022')  # YourBank prefix

    def __str__(self):
        return f"{self.name} - {self.branch}"


# ----------------- Staff -----------------
class Staff(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.username



class ATMCard(models.Model):
    customer = models.OneToOneField("Customer", on_delete=models.CASCADE, related_name="atmcard")

    card_no = models.CharField(max_length=16, unique=True)
    expiry_date = models.DateField()
    cvv = models.CharField(max_length=3)

    pin = models.CharField(max_length=4, blank=True, null=True)   # 🔐 hashed
    is_active = models.BooleanField(default=True)
    otp_attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return self.expiry_date < timezone.now().date()

    def can_renew(self):
        return self.is_expired() or not self.is_active   # ✔ expired OR blocked

    def set_pin(self, raw_pin):
        self.pin = make_password(raw_pin)

    def check_pin(self, raw_pin):
        return check_password(raw_pin, self.pin)

    def __str__(self):
        return self.card_no




class BankOTP(models.Model):
    card = models.ForeignKey('ATMCard', on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    reason = models.CharField(max_length=50)  # e.g., 'ATM_PIN_SET'
    mobile = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    expiry = models.DateTimeField()
    verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.expiry

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))


# ----------------- Customer -----------------
class Customer(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('SAVINGS', 'Savings'),
        ('CURRENT', 'Current'),
    ]

    GENDER_CHOICES = (
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    )

    customer_id = models.AutoField(primary_key=True)
    bank = models.ForeignKey(Bank, on_delete=models.SET_NULL, null=True, blank=True)
    aadhar = models.ForeignKey(Aadhar, on_delete=models.PROTECT, related_name='yourbank_aadhar_customers')
    pan = models.ForeignKey(Pan, on_delete=models.PROTECT, related_name='yourbank_pan_customers', null=True, blank=True)

    name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)
    mobile = models.CharField(max_length=10)   # not unique across banks
    dob = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    address = models.TextField(max_length=300, blank=True)

    account_no = models.CharField(max_length=12, unique=True, editable=False)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    password = models.CharField(max_length=128, blank=True)
    transaction_pin = models.CharField(max_length=128, null=True, blank=True)
    photo = models.ImageField(upload_to='yourbank_photos/', blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_account_no(self):
        prefix = self.bank.bank_prefix if self.bank else '0000'
        for _ in range(1000):
            tail = str(random.randint(10**7, 10**8 - 1)).zfill(8)
            acc = f"{prefix}{tail}"
            if not Customer.objects.filter(account_no=acc).exists():
                return acc
        raise RuntimeError("Unable to generate unique account number")

    def save(self, *args, **kwargs):
        if not self.account_no:
            self.account_no = self.generate_account_no()
        if not self.password:
            dob_str = self.dob.strftime("%d%m%y")
            self.password = f"{self.mobile[-6:]}{dob_str}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_no} - {self.name}"


# ----------------- Transaction -----------------
class Transaction(models.Model):
    TRANSACTION_TYPE = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAW', 'Withdraw'),
        ('TRANSFER', 'Transfer'),
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    sender_account = models.CharField(max_length=30, null=True, blank=True)
    receiver_account = models.CharField(max_length=30, null=True, blank=True)
    
    sender_bank = models.CharField(max_length=50, null=True, blank=True)
    receiver_bank = models.CharField(max_length=50, null=True, blank=True)  # New field for cross-bank transfers

    sender_mobile = models.CharField(max_length=10, blank=True, default='')
    receiver_mobile = models.CharField(max_length=10, blank=True, default='')


    note = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.customer.account_no} - {self.transaction_type} {self.amount}"


# ----------------- Bank Transaction -----------------
class BankTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = Transaction.TRANSACTION_TYPE

    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name="bank_transactions")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="bank_transactions")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    balance_before = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)

    sender_account = models.CharField(max_length=30, null=True, blank=True)
    receiver_account = models.CharField(max_length=30, null=True, blank=True)
    
    sender_bank = models.CharField(max_length=50, null=True, blank=True)
    receiver_bank = models.CharField(max_length=50, null=True, blank=True)  # New field for cross-bank transfers

    sender_mobile = models.CharField(max_length=10, blank=True, default='')
    receiver_mobile = models.CharField(max_length=10, blank=True, default='')


    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} by {self.customer.name}"


