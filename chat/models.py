from django.db import models
from django.utils import timezone
from user.models import User
from guest.models import Guest
from hotel.models import Hotel
from lobbybee.utils.file_url import upload_to_chat_media, upload_to_template_media, upload_to_custom_template_media

class Conversation(models.Model):
    """
    Tracks conversation between a guest and a hotel department
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    ]
    DEPARTMENT_CHOICES = [
        ('Reception', 'Reception'),
        ('Housekeeping', 'Housekeeping'),
        ('Room Service', 'Room Service'),
        ('Restaurant', 'Restaurant'),
        ('Management', 'Management'),
    ]
    CONVERSATION_TYPE_CHOICES = [
        ('service', 'Service'),
        ('demo', 'Demo'),
        ('checkin', 'Check-in'),
        ('checked_in', 'Checked In'),
        ('general', 'General'),
    ]
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='conversations', null=True, blank=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='conversations', null=True, blank=True)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, default='Reception')
    conversation_type = models.CharField(max_length=20, choices=CONVERSATION_TYPE_CHOICES, default='general')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Track the last message and activity
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.TextField(max_length=255, blank=True)

    # Request fulfillment tracking
    is_request_fulfilled = models.BooleanField(
        default=False,
        help_text="Whether the guest's request was successfully fulfilled"
    )
    fulfilled_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the request was marked as fulfilled"
    )
    fulfillment_notes = models.TextField(
        blank=True, null=True,
        help_text="Notes about request fulfillment status"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Only enforce uniqueness for active conversations when guest and hotel are not null
            # Allow multiple closed conversations for the same guest/department combo
            models.UniqueConstraint(
                fields=['guest', 'hotel', 'department', 'conversation_type'],
                condition=models.Q(status='active') & models.Q(guest__isnull=False) & models.Q(hotel__isnull=False),
                name='unique_active_conversation'
            )
        ]
        indexes = [
            models.Index(fields=['guest', 'status']),
            models.Index(fields=['hotel', 'department', 'status']),
            models.Index(fields=['hotel', 'conversation_type', 'status']),
            models.Index(fields=['last_message_at']),
        ]

    def __str__(self):
        guest_name = self.guest.full_name if self.guest else "Unknown Guest"
        hotel_name = self.hotel.name if self.hotel else "Unknown Hotel"
        return f"Conversation: {guest_name} -> {self.department} ({self.get_conversation_type_display()})"

    def update_last_message(self, message_content):
        """Update the last message preview and timestamp"""
        self.last_message_at = timezone.now()
        self.last_message_preview = message_content[:255]
        self.save(update_fields=['last_message_at', 'last_message_preview'])

    def mark_fulfilled(self, fulfilled=True, notes=None):
        """Mark conversation request as fulfilled or unfulfilled"""
        self.is_request_fulfilled = fulfilled
        if fulfilled:
            self.fulfilled_at = timezone.now()
        else:
            self.fulfilled_at = None
        self.fulfillment_notes = notes
        self.save(update_fields=['is_request_fulfilled', 'fulfilled_at', 'fulfillment_notes'])

    def get_fulfillment_status_display(self):
        """Get display text for fulfillment status"""
        if self.is_request_fulfilled:
            return "Fulfilled"
        elif self.fulfilled_at:
            return "Not Fulfilled"
        else:
            return "Pending"
class Message(models.Model):
    """
    Individual messages within a conversation
    """
    SENDER_CHOICES = [
        ('guest', 'Guest'),
        ('staff', 'Staff'),
    ]

    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('document', 'Document'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender_type = models.CharField(max_length=10, choices=SENDER_CHOICES)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages')

    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')
    content = models.TextField()

    # For media messages
    media_file = models.FileField(upload_to=upload_to_chat_media, blank=True, null=True)
    media_filename = models.CharField(max_length=255, blank=True, null=True)
    media_url = models.URLField(blank=True, null=True)  # Keep for backward compatibility

    # Message metadata
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Flow fields for hardcoded flows (checkin, etc.)
    is_flow = models.BooleanField(default=False, help_text="Whether this message is part of a hardcoded flow")
    flow_id = models.CharField(max_length=50, blank=True, null=True, help_text="Identifier for the flow (e.g., 'checkin', 'service_request')")
    flow_step = models.IntegerField(blank=True, null=True, help_text="Current step number in the flow")
    is_flow_step_success = models.BooleanField(null=True, blank=True, help_text="Whether this flow step was successful")

    # WhatsApp integration fields
    whatsapp_message_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="WhatsApp message ID for deduplication of incoming guest messages only"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender_type', 'is_read']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_flow', 'flow_id']),
            models.Index(fields=['flow_id', 'flow_step']),
        ]

    def __str__(self):
        sender_name = self.sender.get_full_name() if self.sender else self.sender_type
        return f"{sender_name}: {self.content[:50]}..."

    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def get_sender_display_name(self):
        """Get display name for sender"""
        if self.sender_type == 'guest':
            if self.conversation.guest:
                return self.conversation.guest.full_name or 'Guest'
            else:
                return 'Guest'
        elif self.sender:
            return self.sender.get_full_name() or self.sender.username
        return self.sender_type.title()

    @property
    def get_media_url(self):
        """Get media URL from file field or legacy URL field"""
        if self.media_file:
            return self.media_file.url
        return self.media_url

    def save(self, *args, **kwargs):
        """Override save to handle media file and URL"""
        is_new = self.pk is None

        if self.media_file:
            # Set media URL from file field
            self.media_url = self.media_file.url
            # Extract filename if not provided
            if not self.media_filename:
                self.media_filename = self.media_file.name.split('/')[-1]

        super().save(*args, **kwargs)

        # Track outgoing messages for deduplication
        if is_new and self.sender_type == 'staff':
            from .utils.webhook_deduplication import create_outgoing_webhook_attempt

            try:
                # Only track if guest exists and has whatsapp number
                if self.conversation.guest and hasattr(self.conversation.guest, 'whatsapp_number'):
                    whatsapp_number = self.conversation.guest.whatsapp_number
                    create_outgoing_webhook_attempt(
                        webhook_type='outgoing',
                        message_content=self.content,
                        whatsapp_number=whatsapp_number,
                        message_id=self.id,
                        conversation_id=self.conversation.id
                    )
            except Exception as e:
                # Don't fail the save if deduplication tracking fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to track outgoing message for deduplication: {e}")


class WebhookAttempt(models.Model):
    """
    Track all webhook attempts for deduplication and debugging purposes
    """
    WEBHOOK_TYPES = [
        ('guest', 'Guest Webhook'),
        ('flow', 'Flow Webhook'),
        ('outgoing', 'Outgoing Message'),
    ]

    STATUSES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('validation_failed', 'Validation Failed'),
        ('processing_failed', 'Processing Failed'),
        ('duplicate', 'Duplicate'),
    ]

    webhook_type = models.CharField(max_length=20, choices=WEBHOOK_TYPES)
    whatsapp_message_id = models.CharField(max_length=100, db_index=True)
    whatsapp_number = models.CharField(max_length=20, db_index=True)
    status = models.CharField(max_length=20, choices=STATUSES, default='pending')

    # Request/Response data for debugging
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)

    # Processing metadata
    processing_time_ms = models.IntegerField(null=True, blank=True)
    message_id = models.IntegerField(null=True, blank=True, help_text="Created message ID if successful")
    conversation_id = models.IntegerField(null=True, blank=True, help_text="Related conversation ID")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['webhook_type', 'whatsapp_message_id']
        indexes = [
            models.Index(fields=['webhook_type', 'status']),
            models.Index(fields=['whatsapp_number', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_webhook_type_display()} - {self.whatsapp_message_id[:20]}... - {self.status}"


class ConversationParticipant(models.Model):
    """
    Track which staff members are participating in conversations
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='participants')
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_participations')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['conversation', 'staff']
        indexes = [
            models.Index(fields=['staff', 'is_active']),
            models.Index(fields=['conversation', 'is_active']),
        ]

    def __str__(self):
        return f"{self.staff.get_full_name()} in {self.conversation}"

    def mark_conversation_read(self):
        """Mark conversation as read for this participant"""
        self.last_read_at = timezone.now()
        self.save(update_fields=['last_read_at'])

        # Mark all messages in conversation as read for this participant
        self.conversation.messages.filter(is_read=False).update(is_read=True, read_at=timezone.now())


class MessageTemplate(models.Model):
    """
    Global message templates that can be used across all hotels
    """
    TEMPLATE_TYPE_CHOICES = [
        ('greeting', 'Greeting'),
        ('checkin', 'Check-in'),
        ('service', 'Service Request'),
        ('farewell', 'Farewell'),
        ('emergency', 'Emergency'),
        ('promotion', 'Promotion'),
        ('general', 'General'),
    ]

    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    text_content = models.TextField()

    # Media for template
    media_file = models.FileField(upload_to=upload_to_template_media, blank=True, null=True)
    media_filename = models.CharField(max_length=255, blank=True, null=True)

    # Template customization
    is_customizable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    # Template variables that can be customized (e.g., {guest_name}, {room_number})
    variables = models.JSONField(default=list, blank=True, help_text="List of variable names that can be customized")

    # Metadata
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['template_type', 'is_active']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    @property
    def get_media_url(self):
        """Get media URL from file field"""
        if self.media_file:
            return self.media_file.url
        return None

    def save(self, *args, **kwargs):
        """Override save to handle media filename"""
        if self.media_file and not self.media_filename:
            self.media_filename = self.media_file.name.split('/')[-1]
        super().save(*args, **kwargs)


class CustomMessageTemplate(models.Model):
    """
    Hotel-specific customized message templates
    """
    TEMPLATE_TYPE_CHOICES = [
        ('greeting', 'Greeting'),
        ('checkin', 'Check-in'),
        ('service', 'Service Request'),
        ('farewell', 'Farewell'),
        ('emergency', 'Emergency'),
        ('promotion', 'Promotion'),
        ('general', 'General'),
    ]

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='custom_templates')
    base_template = models.ForeignKey(MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True,
                                      help_text="Base template this customization is derived from")

    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    text_content = models.TextField()

    # Media for template
    media_file = models.FileField(upload_to=upload_to_custom_template_media, blank=True, null=True)
    media_filename = models.CharField(max_length=255, blank=True, null=True)

    # Template customization
    is_customizable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    # Template variables that can be customized
    variables = models.JSONField(default=list, blank=True, help_text="List of variable names that can be customized")

    # Metadata
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['hotel', 'name']
        indexes = [
            models.Index(fields=['hotel', 'template_type', 'is_active']),
            models.Index(fields=['hotel', 'name']),
        ]

    def __str__(self):
        return f"{self.hotel.name} - {self.name} ({self.get_template_type_display()})"

    @property
    def get_media_url(self):
        """Get media URL from file field"""
        if self.media_file:
            return self.media_file.url
        return None

    def save(self, *args, **kwargs):
        """Override save to handle media filename"""
        if self.media_file and not self.media_filename:
            self.media_filename = self.media_file.name.split('/')[-1]
        super().save(*args, **kwargs)

    def get_rendered_content(self, context=None):
        """
        Render template content with provided context variables

        Args:
            context: Dictionary of variables to replace in template

        Returns:
            Rendered text content
        """
        if not context:
            context = {}

        rendered_content = self.text_content
        for variable in self.variables:
            placeholder = f"{{{variable}}}"
            value = context.get(variable, placeholder)
            rendered_content = rendered_content.replace(placeholder, str(value))

        return rendered_content
