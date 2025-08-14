from django.db import models
from hotel.models import Hotel

class FlowStep(models.Model):
    step_id = models.CharField(max_length=100, unique=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True)  # Hotel-specific customization
    flow_type = models.CharField(max_length=50)  # e.g., 'room_service', 'checkin'
    message_template = models.TextField()
    options = models.JSONField(default=dict, blank=True)  # User-facing options
    next_step = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='parent_next')
    previous_step = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='parent_previous')
    conditional_next_steps = models.JSONField(null=True, blank=True)  # For branching logic
    is_optional = models.BooleanField(default=False)
    is_hotel_customizable = models.BooleanField(
        default=True,
    )

    def __str__(self):
        hotel_name = self.hotel.name if self.hotel else "Platform"
        return f"{self.flow_type} - {self.step_id} ({hotel_name})"

class ConversationContext(models.Model):
    user_id = models.CharField(max_length=20)  # Typically a phone number
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    context_data = models.JSONField(default=dict)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user_id', 'hotel']
        indexes = [
            models.Index(fields=['user_id', 'hotel']),
        ]

    def __str__(self):
        return f"Context for {self.user_id} at {self.hotel.name}"

class ScheduledMessageTemplate(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='message_templates')
    message_type = models.CharField(max_length=50)  # e.g., 'checkout_reminder', 'promo', 'welcome'
    trigger_condition = models.JSONField()  # e.g., {'hours_before_checkout': 2}
    message_template = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.message_type} for {self.hotel.name}"

class MessageQueue(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
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
