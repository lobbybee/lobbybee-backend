from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HotelStatsViewSet,
    HotelUserStatsViewSet,
    PlatformStatsViewSet,
    HotelComparisonView,
)

# For superusers - need hotel_id in URL
admin_router = DefaultRouter()
admin_router.register(r'hotels', HotelStatsViewSet, basename='admin-hotel-stat')
admin_router.register(r'platform', PlatformStatsViewSet, basename='platform-stat')

# For hotel users - hotel extracted from user model
router = DefaultRouter()
router.register(r'', HotelUserStatsViewSet, basename='hotel-user-stat')

urlpatterns = [
    # Hotel user endpoints (no hotel_id needed - extracted from user)
    path('', include(router.urls)),
    
    # Superuser/admin endpoints (require hotel_id)
    path('admin/', include(admin_router.urls)),
    
    # Hotel comparison (for authorized users)
    path('compare/', HotelComparisonView.as_view(), name='hotel-stat-comparison'),
]