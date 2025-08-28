from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GuestViewSet, GuestIdentityDocumentViewSet, StayViewSet, GuestIdentityDocumentUploadView, BookingViewSet

router = DefaultRouter()
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'guests', GuestViewSet, basename='guest')
router.register(r'identity-documents', GuestIdentityDocumentViewSet, basename='identity-document')
router.register(r'stays', StayViewSet, basename='stay')

urlpatterns = [
    path('', include(router.urls)),
    path('identity-document-upload/', GuestIdentityDocumentUploadView.as_view(), name='identity-document-upload'),
]
