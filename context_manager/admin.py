from django.contrib import admin
from .models import FlowStep, ConversationContext, ScheduledMessageTemplate, MessageQueue, FlowTemplate, FlowStepTemplate, FlowAction, HotelFlowConfiguration, WebhookLog, ConversationMessage

@admin.register(FlowTemplate)
class FlowTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description')

@admin.register(FlowAction)
class FlowActionAdmin(admin.ModelAdmin):
    list_display = ('name', 'action_type')
    list_filter = ('action_type',)
    search_fields = ('name', 'action_type')

@admin.register(FlowStepTemplate)
class FlowStepTemplateAdmin(admin.ModelAdmin):
    list_display = ('step_name', 'flow_template', 'message_type')
    list_filter = ('flow_template', 'message_type')
    search_fields = ('step_name', 'message_template')

@admin.register(FlowStep)
class FlowStepAdmin(admin.ModelAdmin):
    list_display = ('step_id', 'hotel', 'template')
    list_filter = ('hotel',)
    search_fields = ('step_id', 'template__step_name')

@admin.register(HotelFlowConfiguration)
class HotelFlowConfigurationAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'flow_template', 'is_enabled')
    list_filter = ('hotel', 'flow_template', 'is_enabled')

@admin.register(ConversationContext)
class ConversationContextAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'hotel', 'is_active', 'last_activity')
    list_filter = ('hotel', 'is_active')
    search_fields = ('user_id',)
    raw_id_fields = ('hotel', 'current_step')

@admin.register(ScheduledMessageTemplate)
class ScheduledMessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'message_type', 'is_active')
    list_filter = ('hotel', 'is_active', 'message_type')
    search_fields = ('message_template',)
    raw_id_fields = ('hotel',)

@admin.register(MessageQueue)
class MessageQueueAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'hotel', 'message_type', 'status', 'scheduled_time', 'sent_time')
    list_filter = ('status', 'hotel', 'message_type')
    search_fields = ('user_id', 'message_content')
    raw_id_fields = ('hotel',)

@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'processed_successfully')
    list_filter = ('processed_successfully', 'timestamp')
    search_fields = ('error_message',)

@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ('context', 'is_from_guest', 'timestamp')
    list_filter = ('is_from_guest', 'timestamp')
    search_fields = ('message_content',)