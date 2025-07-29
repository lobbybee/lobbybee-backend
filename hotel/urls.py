from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HotelViewSet, HotelOnboardingView

router = DefaultRouter()
router.register(r'hotels', HotelViewSet, basename='hotel')

urlpatterns = [
    path('', include(router.urls)),
    path('onboarding/', HotelOnboardingView.as_view(), name='hotel-onboarding'),
]
