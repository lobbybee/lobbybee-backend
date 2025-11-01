"""
Chat views module - Split into logical components for better maintainability.
"""

# Import new modular webhook views
from .webhooks import GuestWebhookView, FlowWebhookView

# Export the new modular views
__all__ = [
    # Webhook views (new modular ones)
    'GuestWebhookView',
    'FlowWebhookView',
]

# Note: Original views remain in views.py for now
# They can be imported directly from chat.views in urls.py