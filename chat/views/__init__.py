"""
Chat views module - Split into logical components for better maintainability.
"""

# Import conversation-related views
from .conversations import (
    ConversationListView,
    ConversationDetailView,
    CreateConversationView,
    CloseConversationView,
    GuestConversationTypeView,
)

# Import message-related views
from .messages import MarkMessagesReadView

# Import media upload views
from .media import ChatMediaUploadView, TemplateMediaUploadView

# Import utility functions
from .utils import send_typing_indicator

# Import template management views
from .templates import (
    MessageTemplateListCreateView,
    MessageTemplateDetailView,
    CustomMessageTemplateListCreateView,
    CustomMessageTemplateDetailView,
    template_types_view,
    render_template_preview,
    template_variables_view,
)

# Export all views
__all__ = [
    # Conversation views
    'ConversationListView',
    'ConversationDetailView',
    'CreateConversationView',
    'CloseConversationView',
    'GuestConversationTypeView',
    
    # Message views
    'MarkMessagesReadView',
    
    # Media views
    'ChatMediaUploadView',
    'TemplateMediaUploadView',
    
    # Template views
    'MessageTemplateListCreateView',
    'MessageTemplateDetailView',
    'CustomMessageTemplateListCreateView',
    'CustomMessageTemplateDetailView',
    'template_types_view',
    'render_template_preview',
    'template_variables_view',
    
    # Utility functions
    'send_typing_indicator',
]