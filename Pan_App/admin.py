from django.contrib import admin
from .models import Pan

@admin.register(Pan)
class PanAdmin(admin.ModelAdmin):
    list_display = ('pan_no', 'name', 'aadhar', 'mobile', 'created_at')
    readonly_fields = ('pan_no', 'created_at')
