from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import ConversationContext, ConversationMessage, MessageQueue
from ..tasks import send_pending_messages


@transaction.atomic
def get_or_create_context(whatsapp_number, guest, hotel):
    """
    Retrieves an active context or creates a new one, ensuring atomicity.
    """
    context, created = ConversationContext.objects.select_for_update().get_or_create(
        user_id=whatsapp_number,
        hotel=hotel,
        defaults={
            'is_active': True,
            'navigation_stack': [],
            'context_data': {'guest_id': guest.id, 'accumulated_data': {}}
        }
    )

    if not created and not context.is_active:
        # Reactivate an inactive context for a new conversation
        context.is_active = True
        context.hotel = hotel
        context.guest = guest
        context.current_step = None
        context.navigation_stack = []
        context.accumulated_data = {}
        context.error_count = 0
        context.save()
    
    return context

def get_active_context(whatsapp_number):
    """
    Retrieve the active conversation context for a guest.
    """
    return ConversationContext.objects.filter(user_id=whatsapp_number, is_active=True).first()

def update_context_activity(context, message_body):
    """
    Updates activity timestamps and logs the incoming message.
    """
    context.last_guest_message_at = timezone.now()
    context.last_activity = timezone.now()
    context.save()
    log_conversation_message(context, message_body, is_from_guest=True)
    # Trigger async task to handle pending messages within the 24-hour window
    send_pending_messages.delay(context.user_id)

def log_conversation_message(context, content, is_from_guest):
    """
    Logs a single message to the ConversationMessage model.
    """
    ConversationMessage.objects.create(
        context=context,
        message_content=content,
        is_from_guest=is_from_guest
    )

@transaction.atomic
def reset_user_conversation(user_id):
    """
    Completely wipes all conversation data for a given user_id.
    This includes ConversationContext, ConversationMessage, and MessageQueue entries.
    """
    # Delete ConversationMessages associated with the user's contexts
    ConversationMessage.objects.filter(context__user_id=user_id).delete()
    
    # Delete MessageQueue entries for the user
    MessageQueue.objects.filter(user_id=user_id).delete()

    # Delete ConversationContexts for the user
    deleted_count, _ = ConversationContext.objects.filter(user_id=user_id).delete()
    return deleted_count
