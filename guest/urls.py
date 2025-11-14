from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GuestManagementViewSet, StayManagementViewSet

router = DefaultRouter()
router.register(r'guest-management', GuestManagementViewSet, basename='guest-management')
router.register(r'stay-management', StayManagementViewSet, basename='stay-management')

urlpatterns = [
    path('', include(router.urls)),
]

# URL Structure:
# POST /api/guest/guest-management/create-guest/
# GET  /api/guest/guest-management/guests/
# GET  /api/guest/guest-management/bookings/
# POST /api/guest/stay-management/checkin-offline/
# PATCH /api/guest/stay-management/{id}/verify-checkin/
# GET  /api/guest/stay-management/pending-stays/
# GET  /api/guest/stay-management/checked-in-users/
# POST /api/guest/stay-management/{id}/checkout/