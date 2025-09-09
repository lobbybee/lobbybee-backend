from django.urls import path
from .views import (
    WhatsAppWebhookView,
    FlowStepListView,
    FlowStepDetailView,
    ScheduledMessageTemplateListView,
    ScheduledMessageTemplateDetailView,
    # Admin API views
    FlowTemplateListView,
    FlowTemplateDetailView,
    FlowStepTemplateListView,
    FlowStepTemplateDetailView,
    FlowActionListView,
    FlowActionDetailView,
    # Hotel API views
    CustomizableStepTemplateListView,
    WhatsappMediaUploadView,
)

urlpatterns = [
    path('webhook/', WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
    
    # Admin API endpoints for template management
    path('admin/flow-templates/', FlowTemplateListView.as_view(), name='flow-template-list'),
    path('admin/flow-templates/<int:id>/', FlowTemplateDetailView.as_view(), name='flow-template-detail'),
    path('admin/flow-step-templates/', FlowStepTemplateListView.as_view(), name='flow-step-template-list'),
    path('admin/flow-step-templates/<int:id>/', FlowStepTemplateDetailView.as_view(), name='flow-step-template-detail'),
    path('admin/flow-actions/', FlowActionListView.as_view(), name='flow-action-list'),
    path('admin/flow-actions/<int:id>/', FlowActionDetailView.as_view(), name='flow-action-detail'),
    
    # Hotel API endpoints for flow configuration (hotel ID derived from authenticated user)
    path('hotel/customizable-step-templates/', CustomizableStepTemplateListView.as_view(), name='customizable-step-template-list'),
    path('hotel/media/upload/', WhatsappMediaUploadView.as_view(), name='whatsapp-media-upload'),
    
    # FlowStep endpoints (hotel ID derived from authenticated user)
    path('hotel/flow-steps/', FlowStepListView.as_view(), name='flow-step-list'),
    path('hotel/flow-steps/<str:step_id>/', FlowStepDetailView.as_view(), name='flow-step-detail'),
    
    # ScheduledMessageTemplate endpoints (hotel ID derived from authenticated user)
    path('hotel/message-templates/', ScheduledMessageTemplateListView.as_view(), name='message-template-list'),
    path('hotel/message-templates/<int:template_id>/', ScheduledMessageTemplateDetailView.as_view(), name='message-template-detail'),
]
