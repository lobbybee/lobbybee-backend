from django.db import models
from hotel.models import Hotel

class FlowTemplate(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.category})"

class FlowAction(models.Model):
    name = models.CharField(max_length=100)
    action_type = models.CharField(max_length=50)  # e.g., 'SEND_NOTIFICATION'
    configuration = models.JSONField(null=True, blank=True)  # e.g., {'department_name': 'reception'}

    def __str__(self):
        return f"{self.name} ({self.action_type})"

class Placeholder(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="The placeholder name, e.g., 'guest_name'")
    description = models.TextField(help_text="A description of what the placeholder represents.")
    resolving_logic = models.CharField(max_length=200, help_text="The logic to resolve the placeholder, e.g., 'guest.full_name'")

    def __str__(self):
        return self.name


class FlowStepTemplate(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('media', 'Media'),
        ('quick-reply', 'Quick Reply'),
        ('list-picker', 'List Picker'),
        ('call-to-action', 'Call to Action'),
        ('template', 'Template'),
    ]

    flow_template = models.ForeignKey(FlowTemplate, on_delete=models.CASCADE, related_name='step_templates')
    step_name = models.CharField(max_length=100)
    order = models.IntegerField(default=0, help_text="Controls the display order of the step in a flow.")
    message_template = models.TextField()
    message_type = models.CharField(
        max_length=50,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )
    options = models.JSONField(default=dict, null=True, blank=True)
    actions = models.ManyToManyField(FlowAction, blank=True)
    next_step_template = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    conditional_next_steps = models.JSONField(null=True, blank=True)
    allowed_flow_categories = models.JSONField(default=list, null=True, blank=True)
    quick_reply_navigation = models.JSONField(default=dict, null=True, blank=True, help_text="e.g., {'Back': 'back', 'Main Menu': 'main_menu'}")

    def __str__(self):
        return f"{self.step_name} ({self.flow_template.name})"

class FlowStep(models.Model):
    template = models.ForeignKey(FlowStepTemplate, on_delete=models.CASCADE)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True)
    step_id = models.CharField(max_length=100)

    class Meta:
        unique_together = ['template', 'hotel']

    def __str__(self):
        return f"{self.template.step_name} for {self.hotel.name if self.hotel else 'Platform'}"

class HotelFlowConfiguration(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    flow_template = models.ForeignKey(FlowTemplate, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True)
    customization_data = models.JSONField(default=dict, null=True, blank=True)  # Stores overrides

    class Meta:
        unique_together = ['hotel', 'flow_template']

    def __str__(self):
        return f"{self.flow_template.name} config for {self.hotel.name}"

class WebhookLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(null=True, blank=True)
    processed_successfully = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"Webhook log {self.timestamp}"

class ConversationMessage(models.Model):
    context = models.ForeignKey('ConversationContext', on_delete=models.CASCADE)
    message_content = models.TextField()
    is_from_guest = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        sender = "Guest" if self.is_from_guest else "System"
        return f"{sender}: {self.message_content[:50]}..."

class ConversationContext(models.Model):
    user_id = models.CharField(max_length=20)  # Typically a phone number
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True) # Allow null/blank for platform-level contexts
    context_data = models.JSONField(default=dict, null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    # New fields for template-based system
    current_step = models.ForeignKey('FlowStep', null=True, on_delete=models.CASCADE)
    navigation_stack = models.JSONField(default=list, null=True, blank=True)  # Stores a stack of visited step_template IDs
    last_guest_message_at = models.DateTimeField(null=True)
    error_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ['user_id', 'hotel']
        indexes = [
            models.Index(fields=['user_id', 'hotel']),
        ]

    def __str__(self):
        hotel_name = self.hotel.name if self.hotel else "Platform"
        return f"Context for {self.user_id} at {hotel_name}"

class ScheduledMessageTemplate(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='message_templates')
    message_type = models.CharField(max_length=50)  # e.g., 'checkout_reminder', 'promo', 'welcome'
    trigger_condition = models.JSONField(null=True, blank=True)  # e.g., {'hours_before_checkout': 2}
    message_template = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.message_type} for {self.hotel.name}"

class MessageQueue(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('on_hold', 'On Hold'),  # For 24-hour window compliance
    ]
    user_id = models.CharField(max_length=20)  # Typically a phone number
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=50)
    message_content = models.TextField()
    scheduled_time = models.DateTimeField(db_index=True)
    sent_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    retry_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Message to {self.user_id} ({self.message_type}) - {self.status}"