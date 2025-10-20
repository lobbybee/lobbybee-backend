from django.db import models
import uuid


class Conversation(models.Model):
    STATUS_CHOICES = [
        ('demo', 'Demo Mode'),
        ('checkin', 'Check-in Process'),
        ('active', 'Active Guest'),
        ('relay', 'Department Relay'),
        ('closed', 'Closed'),
    ]

    DEPARTMENT_CHOICES = [
        ('Reception', 'Reception'),
        ('Housekeeping', 'Housekeeping'),
        ('Room Service', 'Room Service'),
        ('Café', 'Café'),
        ('Management', 'Management'),
    ]

    id = models.BigAutoField(primary_key=True)
    stay = models.OneToOneField('guest.Stay', on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='demo')
    current_step = models.CharField(max_length=50, default='start')
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, blank=True, null=True)  # Added to store department for relay

    context_data = models.JSONField(default=dict)  # For flow state
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.stay:
            return f"Conversation for stay {str(self.stay.id)}"
        else:
            return f"Demo conversation {str(self.id)}"


class Message(models.Model):
    SENDER_TYPES = [
        ('guest', 'Guest'),
        ('staff', 'Staff Member'),
        ('system', 'System'),
    ]

    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPES)
    staff_sender = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    whatsapp_message_id = models.CharField(max_length=100, blank=True)

    def __str__(self):
        if self.conversation.stay:
            return f"Message in conversation {str(self.conversation.stay.id)} at {self.timestamp}"
        else:
            return f"Message in demo conversation {str(self.conversation.id)} at {self.timestamp}"


class MessageTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    content = models.TextField()
    template_type = models.CharField(max_length=20, default='text')

    def __str__(self):
        return self.name
