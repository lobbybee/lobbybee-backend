from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HotelViewSet, UpdateProfileView, HotelDocumentUploadView

router = DefaultRouter()
router.register(r'hotels', HotelViewSet, basename='hotel')

urlpatterns = [
    path('', include(router.urls)),
    path('profile/update/', UpdateProfileView.as_view(), name='hotel-profile-update'),
    path('documents/upload/', HotelDocumentUploadView.as_view(), name='hotel-document-upload'),
]
