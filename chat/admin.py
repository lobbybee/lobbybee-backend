from django.contrib import admin
from .models import Conversation, Message, ConversationParticipant, MessageTemplate, CustomMessageTemplate


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin configuration for Conversation model"""
    list_display = [
        'id', 'guest', 'hotel', 'department', 'status', 
        'last_message_at', 'last_message_preview', 'created_at'
    ]
    list_filter = ['status', 'department', 'hotel', 'created_at']
    search_fields = [
        'guest__full_name', 'guest__whatsapp_number', 
        'hotel__name', 'department'
    ]
    readonly_fields = ['created_at', 'updated_at', 'last_message_at']
    ordering = ['-last_message_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('guest', 'hotel', 'department', 'status')
        }),
        ('Message Tracking', {
            'fields': ('last_message_at', 'last_message_preview')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'guest', 'hotel'
        )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin configuration for Message model"""
    list_display = [
        'id', 'conversation', 'sender_type', 'sender', 
        'message_type', 'content_preview', 'is_flow', 'flow_step', 'is_read', 'created_at'
    ]
    list_filter = [
        'sender_type', 'message_type', 'is_flow', 'is_read', 
        'conversation__department', 'conversation__hotel', 'created_at'
    ]
    search_fields = [
        'content', 'conversation__guest__full_name',
        'conversation__guest__whatsapp_number', 'sender__username'
    ]
    readonly_fields = ['created_at', 'updated_at', 'read_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Message Information', {
            'fields': ('conversation', 'sender_type', 'sender', 'message_type')
        }),
        ('Content', {
            'fields': ('content', 'media_url', 'media_filename')
        }),
        ('Flow Information', {
            'fields': ('is_flow', 'flow_id', 'flow_step', 'is_flow_step_success'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def content_preview(self, obj):
        """Show preview of message content"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    content_preview.short_description = 'Content Preview'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'conversation__guest', 'conversation__hotel', 'sender'
        )


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    """Admin configuration for ConversationParticipant model"""
    list_display = [
        'id', 'conversation', 'staff', 'is_active', 
        'joined_at', 'last_read_at'
    ]
    list_filter = [
        'is_active', 'conversation__department', 
        'conversation__hotel', 'joined_at'
    ]
    search_fields = [
        'staff__username', 'staff__email', 
        'conversation__guest__full_name', 'conversation__guest__whatsapp_number'
    ]
    readonly_fields = ['joined_at', 'last_read_at']
    ordering = ['-joined_at']
    
    fieldsets = (
        ('Participation', {
            'fields': ('conversation', 'staff', 'is_active')
        }),
        ('Activity Tracking', {
            'fields': ('joined_at', 'last_read_at')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'conversation__guest', 'conversation__hotel', 
            'staff'
        )


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for MessageTemplate model"""
    list_display = [
        'id', 'name', 'template_type', 'is_customizable', 
        'is_active', 'created_at'
    ]
    list_filter = [
        'template_type', 'is_customizable', 'is_active', 'created_at'
    ]
    search_fields = ['name', 'description', 'text_content']
    readonly_fields = ['created_at', 'updated_at', 'media_filename']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'template_type', 'description')
        }),
        ('Content', {
            'fields': ('text_content', 'media_file', 'media_filename')
        }),
        ('Configuration', {
            'fields': ('is_customizable', 'is_active', 'variables')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(CustomMessageTemplate)
class CustomMessageTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for CustomMessageTemplate model"""
    list_display = [
        'id', 'hotel', 'name', 'template_type', 'is_customizable', 
        'is_active', 'created_at'
    ]
    list_filter = [
        'template_type', 'is_customizable', 'is_active', 
        'hotel', 'created_at'
    ]
    search_fields = [
        'name', 'description', 'text_content', 'hotel__name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'media_filename']
    ordering = ['hotel', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('hotel', 'base_template', 'name', 'template_type', 'description')
        }),
        ('Content', {
            'fields': ('text_content', 'media_file', 'media_filename')
        }),
        ('Configuration', {
            'fields': ('is_customizable', 'is_active', 'variables')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('hotel', 'base_template')


# Customize admin site header and title
admin.site.site_header = "LobbyBee Chat Administration"
admin.site.site_title = "Chat Admin"
admin.site.index_title = "Welcome to LobbyBee Chat Administration"