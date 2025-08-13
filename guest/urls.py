from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GuestViewSet, GuestIdentityDocumentViewSet, StayViewSet

router = DefaultRouter()
router.register(r'guests', GuestViewSet, basename='guest')
router.register(r'identity-documents', GuestIdentityDocumentViewSet, basename='identity-document')
router.register(r'stays', StayViewSet, basename='stay')

urlpatterns = [
    path('', include(router.urls)),
]
