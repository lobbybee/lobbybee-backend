from django.urls import path

from .views import (
    ConversationListView,
    ConversationDetailView,
    CreateConversationView,
    CloseConversationView,
    GuestConversationTypeView,
    MarkMessagesReadView,
    ChatMediaUploadView,
    TemplateMediaUploadView,
    send_typing_indicator,
    MessageTemplateListCreateView,
    MessageTemplateDetailView,
    CustomMessageTemplateListCreateView,
    CustomMessageTemplateDetailView,
    template_types_view,
    render_template_preview,
    template_variables_view,
)

app_name = 'chat'

urlpatterns = [
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
    path('upload-template-media/', TemplateMediaUploadView.as_view(), name='upload-template-media'),

    # Message Template management
    path('templates/', MessageTemplateListCreateView.as_view(), name='message-template-list'),
    path('templates/<int:pk>/', MessageTemplateDetailView.as_view(), name='message-template-detail'),
    path('templates/types/', template_types_view, name='template-types'),
    path('templates/<int:template_id>/preview/', render_template_preview, name='template-preview'),
    path('templates/variables/', template_variables_view, name='template-variables'),

    # Custom Message Template management
    path('custom-templates/', CustomMessageTemplateListCreateView.as_view(), name='custom-template-list'),
    path('custom-templates/<int:pk>/', CustomMessageTemplateDetailView.as_view(), name='custom-template-detail'),
]
