from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HotelRegistrationView, 
    HotelStaffRegistrationView, 
    VerifyOTPView, 
    UsernameSuggestionView, 
    CheckUserExistsView,
    ResendOTPView,
    CustomTokenObtainPairView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
    UserViewSet, # New import
    PlatformUserViewSet,
    PlatformCreateHotelView,
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user') # For hotel staff

admin_router = DefaultRouter()
admin_router.register(r'users', PlatformUserViewSet, basename='platform-user')

urlpatterns = [
    path('hotel/register/', HotelRegistrationView.as_view(), name='hotel-registration'),
    path('hotel/staff/create/', HotelStaffRegistrationView.as_view(), name='hotel-staff-creation'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('username-suggestions/', UsernameSuggestionView.as_view(), name='username-suggestions'),
    path('check-user-exists/', CheckUserExistsView.as_view(), name='check-user-exists'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('admin/create-hotel/', PlatformCreateHotelView.as_view(), name='platform-create-hotel'),
    path('admin/', include(admin_router.urls)),
    path('', include(router.urls)), # Include router URLs
]
