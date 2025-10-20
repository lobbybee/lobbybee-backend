from django.contrib import admin
from .models import Conversation, Message, MessageTemplate

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'stay', 'status', 'current_step', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('stay__guest__name', 'context_data')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender_type', 'timestamp', 'content')
    list_filter = ('sender_type', 'timestamp')
    search_fields = ('content', 'conversation__stay__guest__name')

@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'content')
    list_filter = ('template_type',)
    search_fields = ('name', 'content')
