from django.urls import path
from .views import (
    WhatsAppWebhookView,
    FlowStepListView,
    FlowStepDetailView,
    ScheduledMessageTemplateListView,
    ScheduledMessageTemplateDetailView
)

urlpatterns = [
    path('webhook/', WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
    
    # FlowStep endpoints
    path('hotels/<uuid:hotel_id>/flow-steps/', FlowStepListView.as_view(), name='flow-step-list'),
    path('hotels/<uuid:hotel_id>/flow-steps/<str:step_id>/', FlowStepDetailView.as_view(), name='flow-step-detail'),
    
    # ScheduledMessageTemplate endpoints
    path('hotels/<uuid:hotel_id>/message-templates/', ScheduledMessageTemplateListView.as_view(), name='message-template-list'),
    path('hotels/<uuid:hotel_id>/message-templates/<int:template_id>/', ScheduledMessageTemplateDetailView.as_view(), name='message-template-detail'),
]
