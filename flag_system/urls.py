from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GuestFlagViewSet, search_guests

router = DefaultRouter()
router.register(r'flags', GuestFlagViewSet, basename='guest-flag')

urlpatterns = [
    path('', include(router.urls)),
    path('search-guests/', search_guests, name='search-guests'),
]