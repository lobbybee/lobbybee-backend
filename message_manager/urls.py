from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.webhook import WhatsAppWebhookView
from .views.conversation import ConversationViewSet, TestView
from .views.conversation_debugging import ConversationDebugViewSet

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'conversations', ConversationDebugViewSet, basename='conversation')

urlpatterns = [
    path('webhook/whatsapp/', WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
    path('test/', TestView.as_view(), name='test'),
    path('test_conversation/', ConversationDebugViewSet.as_view({'get': 'list'}), name='test_conversation'),
    path('', include(router.urls)),
]
