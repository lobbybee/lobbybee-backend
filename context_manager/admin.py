from django.contrib import admin
from .models import FlowStep, ConversationContext, ScheduledMessageTemplate, MessageQueue

@admin.register(FlowStep)
class FlowStepAdmin(admin.ModelAdmin):
    list_display = ('step_id', 'flow_type', 'next_step', 'previous_step')
    list_filter = ('flow_type',)
    search_fields = ('step_id', 'message_template')

@admin.register(ConversationContext)
class ConversationContextAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'hotel', 'is_active', 'last_activity')
    list_filter = ('hotel', 'is_active')
    search_fields = ('user_id',)
    raw_id_fields = ('hotel',)

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