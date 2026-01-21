from django.urls import path
from . import views

urlpatterns = [
    path('', views.pan_home, name='pan_home'),
    path('create/start/', views.pan_create_start, name='pan_create_start'),   # mobile + aadhar -> send otp
    path('create/verify-otp/', views.pan_verify_otp, name='pan_verify_otp'), # verify OTP
    path('create/form/', views.pan_create_form, name='pan_create_form'),     # creation form (autofill)
    path('<int:pk>/', views.pan_detail, name='pan_detail'),
    path('<int:pk>/edit/', views.pan_edit, name='pan_edit'),
    path('pan/resend-otp/',views.pan_resend_otp, name='pan_resend_otp'),

]
