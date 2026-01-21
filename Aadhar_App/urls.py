from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='aadhar_home'),
    path('create/', views.aadhar_create, name='aadhar_create'),
    path('<int:pk>/', views.aadhar_detail, name='aadhar_detail'),
    path('<int:pk>/edit/', views.aadhar_edit, name='aadhar_edit'),
    path('api/send-otp/', views.send_otp_for_verification, name='aadhar_send_otp'),
    path('api/verify-otp/', views.verify_otp, name='aadhar_verify_otp'),
]
