from django.urls import path
from .views import HotelRegistrationView, HotelStaffRegistrationView, VerifyOTPView, UsernameSuggestionView, ResendOTPView

urlpatterns = [
    path('hotel/register/', HotelRegistrationView.as_view(), name='hotel-registration'),
    path('hotel/staff/create/', HotelStaffRegistrationView.as_view(), name='hotel-staff-creation'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('username-suggestions/', UsernameSuggestionView.as_view(), name='username-suggestions'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
]