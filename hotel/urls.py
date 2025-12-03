from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HotelViewSet,
    UpdateProfileView,
    HotelDocumentUploadView,
    HotelDocumentUpdateView,
    AdminHotelDocumentViewSet,
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

admin_documents_router = DefaultRouter()
admin_documents_router.register(r'documents', AdminHotelDocumentViewSet, basename='admin-hotel-documents')

urlpatterns = [
    path('', include(router.urls)),
    path('admin/', include(admin_router.urls)),
    path('admin/hotels/<uuid:hotel_pk>/', include(admin_documents_router.urls)),
    path('admin/hotels/<uuid:hotel_pk>/documents/update-by-type/', AdminHotelDocumentViewSet.as_view({'patch': 'update_by_type'}), name='admin-hotel-document-update-by-type'),
    path('profile/update/', UpdateProfileView.as_view(), name='hotel-profile-update'),
    path('documents/upload/', HotelDocumentUploadView.as_view(), name='hotel-document-upload'),
    path('documents/<uuid:pk>/update/', HotelDocumentUpdateView.as_view(), name='hotel-document-update'),
]
