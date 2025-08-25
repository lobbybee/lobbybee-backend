from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HotelViewSet,
    UpdateProfileView,
    HotelDocumentUploadView,
    RoomCategoryViewSet,
    RoomViewSet,
    DepartmentViewSet,
    AdminHotelViewSet,
)

router = DefaultRouter()
router.register(r'hotels', HotelViewSet, basename='hotel')
router.register(r'room-categories', RoomCategoryViewSet, basename='room-category')
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'departments', DepartmentViewSet, basename='department')

admin_router = DefaultRouter()
admin_router.register(r'hotels', AdminHotelViewSet, basename='admin-hotel')

urlpatterns = [
    path('', include(router.urls)),
    path('admin/', include(admin_router.urls)),
    path('profile/update/', UpdateProfileView.as_view(), name='hotel-profile-update'),
    path('documents/upload/', HotelDocumentUploadView.as_view(), name='hotel-document-upload'),
]
