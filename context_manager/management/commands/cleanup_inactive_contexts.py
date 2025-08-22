from django.core.management.base import BaseCommand
from datetime import timedelta
from django.utils import timezone
from context_manager.models import ConversationContext

class Command(BaseCommand):
    help = 'Deletes inactive conversation contexts older than 7 days.'

    def handle(self, *args, **options):
        seven_days_ago = timezone.now() - timedelta(days=7)
        stale_contexts = ConversationContext.objects.filter(last_activity__lt=seven_days_ago)
        
        count = stale_contexts.count()
        stale_contexts.delete()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} stale conversation contexts.'))
