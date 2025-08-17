from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import MessageQueue, ConversationContext
from datetime import timedelta
from django.utils import timezone

@shared_task
def send_notification_email(subject, message, recipient_list):
    """
    Send a notification email asynchronously
    """
    return send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        fail_silently=False,
    )

@shared_task
def process_guest_checkin(guest_id):
    """
    Process guest check-in asynchronously
    """
    # This is a placeholder for actual check-in processing logic
    # You would implement the actual business logic here
    return f"Processed check-in for guest {guest_id}"

@shared_task
def send_pending_messages(recipient_whatsapp_number):
    """
    Send pending messages that are now within the 24-hour window.
    
    Args:
        recipient_whatsapp_number (str): The recipient's WhatsApp number
    """
    try:
        # Get the conversation context for this recipient
        context = ConversationContext.objects.filter(
            user_id=recipient_whatsapp_number,
            is_active=True
        ).first()
        
        if not context or not context.last_guest_message_at:
            return "No active context or last message timestamp found"
        
        # Check if we're now within the 24-hour window
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        is_within_window = context.last_guest_message_at >= twenty_four_hours_ago
        
        if not is_within_window:
            return "Still outside 24-hour window"
        
        # Get pending messages for this recipient
        pending_messages = MessageQueue.objects.filter(
            user_id=recipient_whatsapp_number,
            status='pending'
        )
        
        sent_count = 0
        for message in pending_messages:
            # In a real implementation, you would actually send the message via WhatsApp API
            # For now, we'll just update the status
            
            message.status = 'sent'
            message.sent_time = timezone.now()
            message.save()
            sent_count += 1
        
        return f"Sent {sent_count} pending messages"
        
    except Exception as e:
        # Log the error but don't fail the task
        print(f"Error sending pending messages: {str(e)}")
        return f"Error: {str(e)}"