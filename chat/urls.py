from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Guest webhook endpoint
    path('guest-webhook/', views.GuestWebhookView.as_view(), name='guest-webhook'),
    
    # Conversation management
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path('conversations/create/', views.CreateConversationView.as_view(), name='conversation-create'),
    path('conversations/<int:conversation_id>/', views.ConversationDetailView.as_view(), name='conversation-detail'),
    
    # Message actions
    path('messages/mark-read/', views.MarkMessagesReadView.as_view(), name='mark-messages-read'),
    path('messages/typing/', views.send_typing_indicator, name='send-typing-indicator'),
    
    # Conversation actions
    path('conversations/close/', views.CloseConversationView.as_view(), name='close-conversation'),
    
    # Guest conversation type lookup
    path('guest/conversation-type/', views.GuestConversationTypeView.as_view(), name='guest-conversation-type'),
]