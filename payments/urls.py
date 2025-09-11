from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubscriptionPlanViewSet, TransactionViewSet, HotelSubscriptionViewSet

app_name = 'payments'

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'subscriptions', HotelSubscriptionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]