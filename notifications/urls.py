from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import NotificationViewSet

# Create a router and register our viewset with it
router = SimpleRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
]