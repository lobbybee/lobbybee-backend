from django.urls import path

# Import new modular webhook views
from .views import GuestWebhookView, FlowWebhookView

from .views import (
    ConversationListView,
    ConversationDetailView,
    CreateConversationView,
    CloseConversationView,
    GuestConversationTypeView,
    MarkMessagesReadView,
    ChatMediaUploadView,
    send_typing_indicator,
)

app_name = 'chat'

urlpatterns = [
    # Guest webhook endpoint (new modular)
    path('guest-webhook/', GuestWebhookView.as_view(), name='guest-webhook'),

    # Flow webhook endpoint for non-service messages (new modular)
    path('flow-webhook/', FlowWebhookView.as_view(), name='flow-webhook'),

    # Conversation management (original views)
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/create/', CreateConversationView.as_view(), name='conversation-create'),
    path('conversations/<int:conversation_id>/', ConversationDetailView.as_view(), name='conversation-detail'),

    # Message actions (original views)
    path('messages/mark-read/', MarkMessagesReadView.as_view(), name='mark-messages-read'),
    path('messages/typing/', send_typing_indicator, name='send-typing-indicator'),

    # Conversation actions (original views)
    path('conversations/close/', CloseConversationView.as_view(), name='close-conversation'),

    # Guest conversation type lookup (original views)
    path('guest/conversation-type/', GuestConversationTypeView.as_view(), name='guest-conversation-type'),

    # Media upload (original views)
    path('upload-media/', ChatMediaUploadView.as_view(), name='upload-media'),
]
