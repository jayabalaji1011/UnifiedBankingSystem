from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Customer Login / Logout
    path("login/", views.upay_login, name="upay_login"),
    path("verify/", views.upay_verify, name="upay_verify"),
    path("resend/", views.upay_resend, name="upay_resend"),
    path("customer/logout/", views.logout_customer, name="logout_customer"),

    # Bank selection / linking
    path("add-bank/", views.add_bank, name="add_bank"),
     path('add_bank_processing/', views.add_bank_processing, name='add_bank_processing'),
    path('add_bank_processing_check/', views.add_bank_processing_check, name='add_bank_processing_check'),
    path("customer/unlink-bank/", views.unlink_bank, name="unlink_bank"),

    # Home / Dashboard / Balance
    path("home/", views.home, name="home"),
    path("customer/dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("my_transaction/", views.my_transaction, name="my_transaction"),
    path("customer/<int:customer_id>/transactions/pdf/", views.customer_transactions_pdf, name="customer_transactions_pdf"),

    # PIN / Balance
    path("pin/", views.set_or_change_pin, name="set_or_change_pin"),
    path("check-balance/", views.check_balance, name="check_balance"),

    # Send Money Flow
    path("send-money/", views.send_money, name="send_money"),              # Step 1
    path("send-money/select-receiver/", views.select_receiver, name="select_receiver"), # Step 1b
    path("send-money/pin/<int:customer_id>/", views.send_money_pin, name="send_money_pin"), # Step 2
    path("send-money/success/", views.send_money_success, name="send_money_success"), # Step 3


    path("link-method/", views.link_method, name="link_method"),  # NEW PAGE to select Aadhar or Debit card
    path("link-bank-verify/", views.link_bank_verify, name="link_bank_verify"),  # verify last digits, request OTP
    path("verify-bank-otp/", views.verify_bank_otp_logic, name="verify_bank_otp_logic"),
    path('bank-pin-verify/', views.bank_pin_verify, name='bank_pin_verify'),

    path("upay/processing/", views.upay_processing_page, name="upay_processing_page"),
    path("upay/processing/check/", views.upay_processing_check, name="upay_processing_check"),
    path("send-failed/", views.send_money_failed, name="send_money_failed"),



]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
