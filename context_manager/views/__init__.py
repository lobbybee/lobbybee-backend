# Views package for context_manager app

from .webhook import WhatsAppWebhookView
from .flow_steps import FlowStepListView, FlowStepDetailView
from .message_templates import ScheduledMessageTemplateListView, ScheduledMessageTemplateDetailView
from .admin_api import (
    FlowTemplateListView,
    FlowTemplateDetailView,
    FlowStepTemplateListView,
    FlowStepTemplateDetailView,
    FlowActionListView,
    FlowActionDetailView,
    HotelFlowConfigurationListView as AdminHotelFlowConfigurationListView,
)
from .hotel_api import (
    HotelFlowConfigurationListView,
    HotelFlowCustomizeView,
)

__all__ = [
    'WhatsAppWebhookView',
    'FlowStepListView',
    'FlowStepDetailView',
    'ScheduledMessageTemplateListView',
    'ScheduledMessageTemplateDetailView',
    'FlowTemplateListView',
    'FlowTemplateDetailView',
    'FlowStepTemplateListView',
    'FlowStepTemplateDetailView',
    'FlowActionListView',
    'FlowActionDetailView',
    'AdminHotelFlowConfigurationListView',
    'HotelFlowConfigurationListView',
    'HotelFlowCustomizeView',
]