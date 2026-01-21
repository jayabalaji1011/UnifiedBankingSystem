from django.contrib import admin
from .models import Bank, Staff, Customer, Transaction, BankTransaction, ATMCard, BankOTP

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('name', 'ifsc', 'branch', 'state', 'balance')
    search_fields = ('name', 'ifsc', 'branch')

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('username', 'bank')
    search_fields = ('username',)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'account_no', 'name', 'mobile', 'bank', 'balance', 'is_active', 'created_at'
    )
    list_filter = ('bank', 'account_type', 'is_active')
    search_fields = ('account_no', 'name', 'mobile', 'aadhar__aadhar_no', 'pan__pan_no')
    readonly_fields = ('account_no', 'created_at')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'customer', 'transaction_type', 'amount',
        'sender_account', 'receiver_account',
        'sender_mobile', 'receiver_mobile', 'date'
    )
    list_filter = ('transaction_type', 'date')
    search_fields = ('customer__account_no', 'sender_account', 'receiver_account')


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'bank', 'customer', 'transaction_type', 'amount',
        'sender_account', 'receiver_account',
        'sender_mobile', 'receiver_mobile', 'date'
    )
    list_filter = ('bank', 'transaction_type', 'date')
    search_fields = ('customer__account_no', 'sender_account', 'receiver_account')



from django.contrib import admin
from .models import *

@admin.register(ATMCard)
class ATMCardAdmin(admin.ModelAdmin):
    list_display = (
        'card_no', 'customer', 'is_active', 'otp_attempts', 'expiry_date', 'created_at'
    )
    list_filter = ('is_active', 'expiry_date')
    search_fields = ('card_no', 'customer__name', 'customer__account_no')
    readonly_fields = ('created_at',)

    actions = ['block_cards', 'unblock_cards', 'reset_otp']

    def block_cards(self, request, queryset):
        queryset.update(is_active=False)
    block_cards.short_description = "Block selected ATM cards"

    def unblock_cards(self, request, queryset):
        queryset.update(is_active=True, otp_attempts=0)
    unblock_cards.short_description = "Unblock & Reset OTP attempts"

    def reset_otp(self, request, queryset):
        queryset.update(otp_attempts=0)
    reset_otp.short_description = "Reset OTP attempts"



@admin.register(BankOTP)
class BankOTPAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'card',
        'mobile',
        'otp',
        'reason',
        'verified',
        'created_at',
        'expiry',
        'is_expired_status'
    )

    list_filter = ('reason', 'verified', 'created_at')
    search_fields = ('mobile', 'otp', 'card__card_no')

    readonly_fields = (
        'otp',
        'created_at',
        'expiry'
    )

    ordering = ('-created_at',)

    def is_expired_status(self, obj):
        return obj.is_expired()
    is_expired_status.boolean = True
    is_expired_status.short_description = "Expired"

    def has_add_permission(self, request):
        # OTPs should ONLY be created by system, not admin
        return False
