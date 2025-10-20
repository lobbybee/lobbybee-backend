from django.core.management.base import BaseCommand
# Removed context_manager import as app is no longer used

class Command(BaseCommand):
    help = 'Test Celery by sending a test email'

    def handle(self, *args, **options):
        # TODO: Implement test email functionality without context_manager
        self.stdout.write(
            self.style.WARNING(
                'Test email functionality disabled - context_manager app removed'
            )
        )