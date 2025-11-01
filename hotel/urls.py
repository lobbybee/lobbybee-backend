from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HotelViewSet,
    UpdateProfileView,
    HotelDocumentUploadView,
    HotelDocumentUpdateView,
    RoomCategoryViewSet,
    RoomViewSet,
    AdminHotelViewSet,
    PaymentQRCodeViewSet,
    WiFiCredentialViewSet,
)

router = DefaultRouter()
router.register(r'hotels', HotelViewSet, basename='hotel')
router.register(r'room-categories', RoomCategoryViewSet, basename='room-category')
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'payment-qr-codes', PaymentQRCodeViewSet, basename='payment-qr-code')
router.register(r'wifi-credentials', WiFiCredentialViewSet, basename='wifi-credential')


admin_router = DefaultRouter()
admin_router.register(r'hotels', AdminHotelViewSet, basename='admin-hotel')

urlpatterns = [
    path('', include(router.urls)),
    path('admin/', include(admin_router.urls)),
    path('profile/update/', UpdateProfileView.as_view(), name='hotel-profile-update'),
    path('documents/upload/', HotelDocumentUploadView.as_view(), name='hotel-document-upload'),
    path('documents/<uuid:pk>/update/', HotelDocumentUpdateView.as_view(), name='hotel-document-update'),
]
