from django.contrib import admin
from django.urls import path
from .import views
from django.conf import settings
from django.conf.urls.static import static



app_name='yourbank'

urlpatterns = [
    path("", views.staff_login, name="staff_login"),
    path("staff/dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path('logout_staff/',views.logout_staff,name='logout_staff'),
    path('staff_account/',views.staff_account,name='staff_account'),
    path('bank_dashboard/',views.bank_dashboard,name='bank_dashboard'),
    path('staff/create/start/', views.create_customer_start, name='create_customer_start'),
    path('staff/create/verify-otp/', views.customer_verify_otp, name='customer_verify_otp'),
    path('staff/create/form/', views.customer_create_form, name='customer_create_form'),
    path('yb/staff/customer/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customer/<int:customer_id>/transaction/', views.create_transaction, name='create_transaction'),
    path(
    'staff/customer/<int:pk>/<str:bank_name>/edit/',
    views.customer_edit,
    name='customer_edit'
),
    path('staff/customer/<int:pk>/toggle-active/', views.customer_toggle_active, name='customer_toggle_active'),
    path('staff/customer/<int:customer_id>/transactions/pdf/', views.download_transactions_pdf, name='download_transactions_pdf'),

    #ATM
    path("atm/create/<int:pk>/", views.create_atm, name="create_atm"),
    path("atm/block/<int:pk>/", views.block_atm, name="block_atm"),
    path("atm/enable/<int:pk>/", views.enable_atm, name="enable_atm"),
    path("atm/renew/<int:pk>/", views.renew_atm, name="renew_atm"),

    path("atm/process/<int:pk>/<str:action>/", views.atm_process_page, name="atm_process"),
    path("atm/api/<int:pk>/<str:action>/", views.atm_api, name="atm_api"),


    path('atm', views.atm_home, name='atm_home'),
    path('pin-option/', views.pin_option, name='pin_option'),
    path('request-otp/', views.atm_request_otp, name='atm_request_otp'),
    path('enter-otp/', views.atm_enter_otp, name='atm_enter_otp'),
    path("atm/resend-otp/", views.atm_resend_otp, name="atm_resend_otp"),
    path('set-pin/', views.atm_set_pin, name='atm_set_pin'),
    path("atm/pin/result/", views.atm_pin_result, name="atm_pin_result"),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
