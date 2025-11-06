from rest_framework import serializers
from .models import Conversation, Message, ConversationParticipant, MessageTemplate, CustomMessageTemplate
from .utils.phone_utils import normalize_phone_number
from guest.serializers import GuestSerializer
from user.serializers import UserSerializer


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for Conversation model"""
    guest_info = serializers.SerializerMethodField()
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'guest', 'hotel', 'department', 'status',
            'guest_info', 'hotel_name',
            'last_message_at', 'last_message_preview',
            'unread_count', 'last_message', 'created_at', 'updated_at',
            'is_request_fulfilled', 'fulfilled_at', 'fulfillment_notes'
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_message_at', 'last_message_preview', 'fulfilled_at']

    def get_unread_count(self, obj):
        """Get unread message count for current user"""
        request = self.context.get('request')
        if request and request.user:
            return obj.messages.filter(
                sender_type='guest',
                is_read=False
            ).count()
        return 0

    def get_guest_info(self, obj):
        """Get guest information including room number and floor"""
        active_stay = obj.guest.stays.filter(status='active').first()
        if active_stay:
            return {
                'id': obj.guest.id,
                'full_name': obj.guest.full_name,
                'email': obj.guest.email,
                'whatsapp_number': obj.guest.whatsapp_number,
                'date_of_birth': obj.guest.date_of_birth,
                'nationality': obj.guest.nationality,
                'status': obj.guest.status,
                'room_number': active_stay.room.room_number,
                'floor': active_stay.room.floor,
            }
        else:
            return {
                'id': obj.guest.id,
                'full_name': obj.guest.full_name,
                'email': obj.guest.email,
                'whatsapp_number': obj.guest.whatsapp_number,
                'date_of_birth': obj.guest.date_of_birth,
                'nationality': obj.guest.nationality,
                'status': obj.guest.status,
                'room_number': None,
                'floor': None,
            }

    def get_last_message(self, obj):
        """Get last message details"""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return MessageSerializer(last_message, context=self.context).data
        return None

    def get_fulfillment_status_display(self, obj):
        """Get display text for fulfillment status"""
        return obj.get_fulfillment_status_display()


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    sender_name = serializers.CharField(source='get_sender_display_name', read_only=True)
    guest_info = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender_type', 'sender', 'sender_name',
            'message_type', 'content', 'media_file', 'media_url', 'media_filename',
            'is_read', 'read_at', 'guest_info', 'time_ago',
            'is_flow', 'flow_id', 'flow_step', 'is_flow_step_success',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'read_at', 'media_url']

    def get_guest_info(self, obj):
        """Get guest information for the message"""
        active_stay = obj.conversation.guest.stays.filter(status='active').first()
        return {
            'id': obj.conversation.guest.id,
            'name': obj.conversation.guest.full_name,
            'whatsapp_number': obj.conversation.guest.whatsapp_number,
            'room_number': active_stay.room.room_number if active_stay else None,
            'floor': active_stay.room.floor if active_stay else None
        }

    def get_time_ago(self, obj):
        """Get human readable time ago"""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        diff = now - obj.created_at

        if diff < timedelta(minutes=1):
            return "Just now"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff < timedelta(days=7):
            days = diff.days
            return f"{days} day{'s' if days > 1 else ''} ago"
        else:
            return obj.created_at.strftime('%b %d, %Y')

    def to_representation(self, instance):
        """Override to provide media_url from file field"""
        data = super().to_representation(instance)
        
        # Set media_url from the file field if available
        if instance.media_file:
            data['media_url'] = instance.media_file.url
        elif not data.get('media_url'):
            data['media_url'] = None
            
        return data


class ConversationParticipantSerializer(serializers.ModelSerializer):
    """Serializer for ConversationParticipant model"""
    staff_info = UserSerializer(source='staff', read_only=True)

    class Meta:
        model = ConversationParticipant
        fields = [
            'id', 'conversation', 'staff', 'staff_info',
            'is_active', 'joined_at', 'last_read_at'
        ]
        read_only_fields = ['joined_at', 'last_read_at']


class GuestMessageSerializer(serializers.Serializer):
    """Serializer for incoming guest messages via webhook"""
    whatsapp_number = serializers.CharField(max_length=20)
    message = serializers.CharField()
    message_type = serializers.CharField(default='text')
    media_file = serializers.FileField(required=False, allow_null=True)
    media_url = serializers.URLField(required=False, allow_null=True)
    media_filename = serializers.CharField(required=False, allow_null=True, max_length=255)
    media_id = serializers.CharField(required=False, allow_null=True, max_length=100, help_text="WhatsApp media ID for downloading media from WhatsApp API")
    department = serializers.ChoiceField(choices=[
        ('Reception', 'Reception'),
        ('Housekeeping', 'Housekeeping'),
        ('Room Service', 'Room Service'),
        ('Restaurant', 'Restaurant'),
        ('Management', 'Management'),
    ], required=False)  # Make department optional when conversation_id is provided
    conversation_id = serializers.IntegerField(required=False)

    def validate_whatsapp_number(self, value):
        """Validate and normalize WhatsApp number format"""
        # Normalize the phone number
        normalized = normalize_phone_number(value)
        if not normalized:
            raise serializers.ValidationError("Invalid WhatsApp number format")
        return normalized

    def validate(self, data):
        """Validate that either conversation_id or department is provided"""
        if not data.get('conversation_id') and not data.get('department'):
            raise serializers.ValidationError(
                "Either conversation_id or department must be provided"
            )
        
        # Validate media file and message type consistency
        message_type = data.get('message_type', 'text')
        media_file = data.get('media_file')
        media_url = data.get('media_url')
        media_id = data.get('media_id')
        
        if message_type in ['image', 'document', 'video', 'audio'] and not media_file and not media_url and not media_id:
            raise serializers.ValidationError(
                f"Media file or media_id is required for {message_type} messages"
            )
        
        if media_file and message_type == 'text':
            data['message_type'] = 'image' if media_file.content_type.startswith('image/') else 'document'
        
        return data


class StaffMessageSerializer(serializers.Serializer):
    """Serializer for staff messages via WebSocket"""
    conversation_id = serializers.IntegerField()
    content = serializers.CharField()
    message_type = serializers.CharField(default='text')
    media_file = serializers.FileField(required=False, allow_null=True)
    media_url = serializers.URLField(required=False, allow_null=True)
    media_filename = serializers.CharField(required=False, allow_null=True, max_length=255)

    def validate_content(self, value):
        """Validate message content"""
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        return value.strip()
    
    def validate(self, data):
        """Validate media file and message type consistency"""
        message_type = data.get('message_type', 'text')
        media_file = data.get('media_file')
        media_url = data.get('media_url')
        
        if message_type in ['image', 'document'] and not media_file and not media_url:
            raise serializers.ValidationError(
                f"Media file is required for {message_type} messages"
            )
        
        if media_file and message_type == 'text':
            data['message_type'] = 'image' if media_file.content_type.startswith('image/') else 'document'
        
        return data


class ConversationCreateSerializer(serializers.Serializer):
    """Serializer for creating new conversations"""
    guest_whatsapp_number = serializers.CharField(max_length=20)
    department_type = serializers.ChoiceField(choices=[
        ('Reception', 'Reception'),
        ('Housekeeping', 'Housekeeping'),
        ('Room Service', 'Room Service'),
        ('Café', 'Café'),
        ('Management', 'Management'),
    ])

    def validate_guest_whatsapp_number(self, value):
        """Validate guest exists and has active stay"""
        from guest.models import Guest, Stay
        from .utils.phone_utils import normalize_phone_number

        # Normalize the phone number
        normalized_number = normalize_phone_number(value)
        if not normalized_number:
            raise serializers.ValidationError("Invalid phone number format")

        try:
            guest = Guest.objects.get(whatsapp_number=normalized_number)
            if not Stay.objects.filter(guest=guest, status='active').exists():
                raise serializers.ValidationError("Guest does not have an active stay")
            return guest
        except Guest.DoesNotExist:
            raise serializers.ValidationError("Guest not found")


class MessageReadSerializer(serializers.Serializer):
    """Serializer for marking messages as read"""
    conversation_id = serializers.IntegerField()
    message_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Optional: List of specific message IDs to mark as read. If not provided, all unread messages in conversation will be marked as read."
    )


class TypingIndicatorSerializer(serializers.Serializer):
    """Serializer for typing indicators"""
    conversation_id = serializers.IntegerField()
    is_typing = serializers.BooleanField()


class MessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer for MessageTemplate model"""
    media_url = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'name', 'template_type', 'text_content', 'media_file', 
            'media_filename', 'media_url', 'is_customizable', 'is_active',
            'variables', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'media_filename']
    
    def get_media_url(self, obj):
        """Get media URL from file field"""
        return obj.get_media_url


class CustomMessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer for CustomMessageTemplate model"""
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    base_template_name = serializers.CharField(source='base_template.name', read_only=True)
    media_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomMessageTemplate
        fields = [
            'id', 'hotel', 'hotel_name', 'base_template', 'base_template_name',
            'name', 'template_type', 'text_content', 'media_file', 'media_filename',
            'media_url', 'is_customizable', 'is_active', 'variables',
            'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'media_filename']
    
    def get_media_url(self, obj):
        """Get media URL from file field"""
        return obj.get_media_url


class TemplateRenderSerializer(serializers.Serializer):
    """Serializer for rendering templates with context variables"""
    template_id = serializers.IntegerField()
    context = serializers.JSONField(default=dict, help_text="Dictionary of variables to replace in template")
    
    def validate_template_id(self, value):
        """Validate template exists"""
        try:
            MessageTemplate.objects.get(id=value, is_active=True)
        except MessageTemplate.DoesNotExist:
            try:
                CustomMessageTemplate.objects.get(id=value, is_active=True)
            except CustomMessageTemplate.DoesNotExist:
                raise serializers.ValidationError("Template not found or inactive")
        return value


class TemplateMessageSerializer(serializers.Serializer):
    """Serializer for sending template-based messages"""
    conversation_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    context = serializers.JSONField(default=dict, help_text="Dictionary of variables to replace in template")
    message_type = serializers.CharField(default='text')


class FlowMessageSerializer(serializers.Serializer):
    """
    Minimal serializer for flow webhook processing.
    Only includes essential fields needed for automated flow processing.
    """
    whatsapp_number = serializers.CharField(max_length=20, required=True)
    message = serializers.CharField(required=True)
    message_type = serializers.CharField(default='text')
    media_file = serializers.FileField(required=False, allow_null=True)
    media_url = serializers.URLField(required=False, allow_null=True)
    media_filename = serializers.CharField(required=False, allow_null=True, max_length=255)
    media_id = serializers.CharField(required=False, allow_null=True, max_length=100, 
                                   help_text="WhatsApp media ID for downloading media from WhatsApp API")
    flow_id = serializers.CharField(required=False, allow_null=True, max_length=100,
                                   help_text="Unique flow identifier for continuing existing flows")
    flow_type = serializers.CharField(required=False, allow_null=True, max_length=50,
                                     help_text="Explicit flow type (checkin, general, etc.)")
    previous_flow_message = serializers.JSONField(required=False, allow_null=True,
                                                 help_text="Previous flow state for continuation")

    def validate_whatsapp_number(self, value):
        """Validate and normalize WhatsApp number format"""
        normalized = normalize_phone_number(value)
        if not normalized:
            raise serializers.ValidationError("Invalid WhatsApp number format")
        return normalized

    def validate(self, data):
        """Validate media file and message type consistency"""
        message_type = data.get('message_type', 'text')
        media_file = data.get('media_file')
        media_url = data.get('media_url')
        media_id = data.get('media_id')
        
        if message_type in ['image', 'document', 'video', 'audio'] and not media_file and not media_url and not media_id:
            raise serializers.ValidationError(
                f"Media file or media_id is required for {message_type} messages"
            )
        
        if media_file and message_type == 'text':
            data['message_type'] = 'image' if media_file.content_type.startswith('image/') else 'document'
        
        return data
