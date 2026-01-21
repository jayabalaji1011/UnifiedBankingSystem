from django.contrib import admin
from .models import UPayUser, UPayOTP


@admin.register(UPayUser)
class UPayUserAdmin(admin.ModelAdmin):
    list_display = ("mobile", "bank_app", "customer_id", "created_at")
    list_filter = ("bank_app", "created_at")
    search_fields = ("mobile", "customer_id")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("User Info", {
            "fields": ("mobile",)
        }),
        ("Linked Bank", {
            "fields": ("bank_app", "customer_id")
        }),
        ("System", {
            "fields": ("created_at",)
        }),
    )


@admin.register(UPayOTP)
class UPayOTPAdmin(admin.ModelAdmin):
    list_display = ("mobile", "otp", "purpose", "is_used", "created_at")
    list_filter = ("purpose", "is_used", "created_at")
    search_fields = ("mobile", "otp")
    readonly_fields = ("created_at",)
