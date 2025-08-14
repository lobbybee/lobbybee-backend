from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

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