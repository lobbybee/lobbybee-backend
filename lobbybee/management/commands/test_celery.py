from django.core.management.base import BaseCommand
from context_manager.tasks import send_notification_email

class Command(BaseCommand):
    help = 'Test Celery by sending a test email'

    def handle(self, *args, **options):
        # Send a test email asynchronously
        result = send_notification_email.delay(
            subject='Test Email',
            message='This is a test email sent via Celery',
            recipient_list=['test@example.com']
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully sent test email task with ID: {result.id}'
            )
        )