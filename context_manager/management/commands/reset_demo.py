
from django.core.management.base import BaseCommand
from django.db import transaction
from hotel.models import Hotel
from context_manager.models import ConversationContext, ConversationMessage, MessageQueue

class Command(BaseCommand):
    help = 'Deletes all conversation data associated with demo hotels.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write('Starting demo data reset...')

        # Find all demo hotels
        demo_hotels = Hotel.objects.filter(is_demo=True)
        if not demo_hotels.exists():
            self.stdout.write(self.style.WARNING('No demo hotels found.'))
            return

        demo_hotel_ids = [h.id for h in demo_hotels]
        self.stdout.write(f'Found {len(demo_hotel_ids)} demo hotel(s).')

        # Find all contexts associated with these hotels
        demo_contexts = ConversationContext.objects.filter(hotel_id__in=demo_hotel_ids)

        # Delete from MessageQueue
        mq_deleted_count, _ = MessageQueue.objects.filter(hotel_id__in=demo_hotel_ids).delete()
        self.stdout.write(f'Deleted {mq_deleted_count} entries from MessageQueue.')

        # Delete conversation messages linked to the contexts
        cm_deleted_count, _ = ConversationMessage.objects.filter(context__in=demo_contexts).delete()
        self.stdout.write(f'Deleted {cm_deleted_count} entries from ConversationMessage.')

        # Finally, delete the contexts themselves
        cc_deleted_count, _ = demo_contexts.delete()
        self.stdout.write(f'Deleted {cc_deleted_count} entries from ConversationContext.')

        self.stdout.write(self.style.SUCCESS('Successfully reset all demo data.'))
