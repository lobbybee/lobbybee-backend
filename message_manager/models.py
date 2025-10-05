from django.db import models


class Conversation(models.Model):
    STATUS_CHOICES = [
        ('demo', 'Demo Mode'),
        ('checkin', 'Check-in Process'),
        ('active', 'Active Guest'),
        ('relay', 'Department Relay'),
        ('closed', 'Closed'),
    ]

    id = models.BigAutoField(primary_key=True)
    stay = models.OneToOneField('guest.Stay', on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='demo')
    current_step = models.CharField(max_length=50, default='start')
    department = models.ForeignKey('hotel.Department', on_delete=models.SET_NULL, null=True, blank=True)
    context_data = models.JSONField(default=dict)  # For flow state
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.stay:
            return f"Conversation for stay {self.stay.id}"
        else:
            return f"Demo conversation {self.id}"


class Message(models.Model):
    SENDER_TYPES = [
        ('guest', 'Guest'),
        ('staff', 'Staff Member'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPES)
    staff_sender = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    whatsapp_message_id = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Message in conversation {self.conversation.stay.id} at {self.timestamp}"


class MessageTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    content = models.TextField()
    department = models.ForeignKey('hotel.Department', on_delete=models.CASCADE, null=True, blank=True)
    template_type = models.CharField(max_length=20, default='text')

    def __str__(self):
        return self.name