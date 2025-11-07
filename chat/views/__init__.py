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
from .media import ChatMediaUploadView

# Import utility functions
from .utils import send_typing_indicator

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
    
    # Utility functions
    'send_typing_indicator',
]