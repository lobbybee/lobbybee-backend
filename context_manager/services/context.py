from datetime import timedelta
import json

from django.db import transaction
from django.utils import timezone

from ..models import ConversationContext, ConversationMessage, MessageQueue
from ..tasks import send_pending_messages


@transaction.atomic
def get_or_create_context(whatsapp_number, guest, hotel):
    """
    Retrieves an active context or creates a new one, ensuring atomicity.
    If guest is None, context is created without linking a Guest object.
    If hotel is None, context is created at a platform level.
    The 'guest_id' in context_data is only set if a Guest object is provided.
    """
    defaults = {
        'is_active': True,
        'navigation_stack': [],
        'context_data': {'accumulated_data': {}}
    }
    # Only store guest_id if a Guest object is provided
    if guest:
        defaults['context_data']['guest_id'] = guest.id

    # get_or_create will now work with hotel=None
    context, created = ConversationContext.objects.select_for_update().get_or_create(
        user_id=whatsapp_number,
        hotel=hotel, # This can now be None
        defaults=defaults
    )

    if not created and not context.is_active:
        # Reactivate an inactive context for a new conversation
        context.is_active = True
        context.hotel = hotel # This can now be None
        # Note: context.guest is not set here, as ConversationContext doesn't have a guest field.
        # The guest association is managed through context_data.
        context.current_step = None
        context.navigation_stack = []
        context.context_data = defaults # Reset context_data
        context.error_count = 0
        context.save()
    
    return context

@transaction.atomic
def get_active_context(whatsapp_number):
    """
    Retrieve the active conversation context for a guest.
    """
    return ConversationContext.objects.select_for_update().filter(user_id=whatsapp_number, is_active=True).first()

def update_context_activity(context, message_body, message_type='text', media=None):
    """
    Updates activity timestamps and logs the incoming message.
    """
    context.last_guest_message_at = timezone.now()
    context.last_activity = timezone.now()
    context.save()
    log_conversation_message(context, message_body, is_from_guest=True, message_type=message_type, media=media)
    # Trigger async task to handle pending messages within the 24-hour window
    send_pending_messages.delay(context.user_id)

def log_conversation_message(context, content, is_from_guest, message_type='text', media=None):
    """
    Logs a single message to the ConversationMessage model.
    Serializes dictionary content to JSON strings for proper storage.
    """
    # Serialize dictionary content to JSON string for storage
    if isinstance(content, dict):
        message_content = json.dumps(content)
    else:
        message_content = content
        
    ConversationMessage.objects.create(
        context=context,
        message_content=message_content,
        is_from_guest=is_from_guest,
        message_type=message_type,
        media=media
    )

@transaction.atomic
def reset_conversation(context):
    """
    Resets the conversation context, clearing the navigation stack and accumulated data,
    but keeps the conversation active and linked to the same guest and hotel.
    """
    context.navigation_stack = []
    context.context_data['accumulated_data'] = {}
    context.error_count = 0
    # Optionally, reset to a specific starting flow, e.g., main_menu
    # from .flow import start_flow
    # start_flow(context, 'main_menu') 
    context.save()

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
