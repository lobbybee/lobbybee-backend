from django.urls import path
from .views import (
    HotelRegistrationView, 
    HotelStaffRegistrationView, 
    VerifyOTPView, 
    UsernameSuggestionView, 
    ResendOTPView,
    CustomTokenObtainPairView,
    LogoutView
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('hotel/register/', HotelRegistrationView.as_view(), name='hotel-registration'),
    path('hotel/staff/create/', HotelStaffRegistrationView.as_view(), name='hotel-staff-creation'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('username-suggestions/', UsernameSuggestionView.as_view(), name='username-suggestions'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
]