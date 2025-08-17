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
    AdminHotelFlowConfigurationListView,
    # Hotel API views
    HotelFlowConfigurationListView,
    HotelFlowCustomizeView,
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
    path('admin/hotel-configurations/', AdminHotelFlowConfigurationListView.as_view(), name='admin-hotel-flow-config-list'),
    
    # Hotel API endpoints for flow configuration
    path('hotels/<uuid:hotel_id>/flow-configurations/', HotelFlowConfigurationListView.as_view(), name='hotel-flow-config-list'),
    path('hotels/<uuid:hotel_id>/flows/<int:template_id>/customize/', HotelFlowCustomizeView.as_view(), name='hotel-flow-customize'),
    
    # FlowStep endpoints
    path('hotels/<uuid:hotel_id>/flow-steps/', FlowStepListView.as_view(), name='flow-step-list'),
    path('hotels/<uuid:hotel_id>/flow-steps/<str:step_id>/', FlowStepDetailView.as_view(), name='flow-step-detail'),
    
    # ScheduledMessageTemplate endpoints
    path('hotels/<uuid:hotel_id>/message-templates/', ScheduledMessageTemplateListView.as_view(), name='message-template-list'),
    path('hotels/<uuid:hotel_id>/message-templates/<int:template_id>/', ScheduledMessageTemplateDetailView.as_view(), name='message-template-detail'),
]
