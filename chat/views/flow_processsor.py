# utils/webhook_handler.py

import re
import logging

logger = logging.getLogger(__name__)

# Import WhatsApp payload conversion utilities
from ..utils.whatsapp_payload_utils import create_text_message_payload
from ..utils.checkin_adapter import adapt_checkin_response_to_whatsapp


def handle_incoming_whatsapp_message(whatsapp_number, flow_data):
    """
    Main webhook handler for incoming WhatsApp flow messages.

    Args:
        whatsapp_number (str): Guest's WhatsApp number (core identifier)
        flow_data (dict): WhatsApp message data containing:
            - message (str): The message content
            - message_type (str): Type of message ('text', 'image', 'document', 'video', 'audio')
            - media_url (str, optional): URL to media file
            - media_filename (str, optional): Original filename

    Returns:
        tuple: (whatsapp_payload, status_code)
    """

    # Validate core parameter
    if not whatsapp_number:
        logger.error("handle_incoming_whatsapp_message: whatsapp_number is required")
        return create_text_message_payload(
            whatsapp_number or "unknown",
            "Invalid request: phone number required"
        ), 400

    # Extract data from flow_data
    message_text = flow_data.get('message', '')
    message_type = flow_data.get('message_type', 'text')
    
    # Extract media_id from flow_data if it's media
    media_id = flow_data.get('media_id') if message_type != 'text' else None

    # Try to get existing guest (don't create)
    guest = get_existing_guest(whatsapp_number)
    
    # Check if this is a command message
    command_type, extracted_data = detect_command(message_text)

    if command_type == 'checkin':
        hotel_id = extracted_data.get('hotel_id')
        result = handle_checkin_command(guest, hotel_id, flow_data)
        logger.info(f"handle_checkin_command returned: {result}, type: {type(result)}")
        # Convert result to WhatsApp payload
        whatsapp_payload = adapt_checkin_response_to_whatsapp(result, whatsapp_number)
        return whatsapp_payload, 200

    # Check if guest has an active flow conversation
    active_flow_conversation = get_active_flow_conversation(guest) if guest else None

    if active_flow_conversation:
        result = route_to_flow_handler(
            guest=guest,
            conversation=active_flow_conversation,
            flow_data=flow_data
        )
        # Convert result to WhatsApp payload
        whatsapp_payload = adapt_checkin_response_to_whatsapp(result, whatsapp_number)
        return whatsapp_payload, 200

    # No command matched - fallback response
    return create_text_message_payload(
        whatsapp_number,
        "Welcome to Lobbybee hotel CRM"
    ), 200


def get_existing_guest(whatsapp_number):
    """Get existing guest or return None."""
    from guest.models import Guest

    try:
        return Guest.objects.get(whatsapp_number=whatsapp_number)
    except Guest.DoesNotExist:
        return None


def detect_command(message_text):
    """
    Detect if message is a command and extract relevant data.

    Returns:
        tuple: (command_type, extracted_data)
    """
    message_text = message_text.strip()

    # Check for checkin command: /checkin-{hotel_id}
    checkin_pattern = r'^/checkin[-\s]([a-zA-Z0-9\-]+)$'
    match = re.match(checkin_pattern, message_text, re.IGNORECASE)

    if match:
        hotel_id = match.group(1)
        return ('checkin', {'hotel_id': hotel_id})

    return (None, {})


def get_active_flow_conversation(guest):
    """Get guest's active flow conversation if any."""
    from chat.models import Conversation

    if not guest:
        return None

    logger.info(f"Looking for active flow conversation for guest: {guest.id}")
    
    # First try to get any active conversation (prioritize checkin type)
    active_conversation = Conversation.objects.filter(
        guest=guest,
        status='active'
    ).order_by('-last_message_at').first()
    
    if active_conversation:
        logger.info(f"Found active conversation: {active_conversation.id}, type: {active_conversation.conversation_type}")
        
        # Check if it's a checkin flow conversation
        if active_conversation.conversation_type == 'checkin':
            logger.info(f"Found active checkin flow conversation: {active_conversation.id}")
            return active_conversation
        else:
            logger.info(f"Active conversation {active_conversation.id} is not a checkin flow (type: {active_conversation.conversation_type})")
    else:
        logger.info(f"No active conversation found for guest {guest.id}")

    return None


def handle_checkin_command(guest, hotel_id, flow_data):
    """Handle /checkin-{hotel_id} command."""
    from ..flows.checkin_flow import process_checkin_flow

    # Let the flow handle all validation, guest creation, and business logic
    result = process_checkin_flow(
        guest=guest,
        hotel_id=hotel_id,
        flow_data=flow_data,
        is_fresh_checkin_command=True
    )
    logger.info(f"process_checkin_flow returned: {result}, type: {type(result)}")
    return result


def route_to_flow_handler(guest, conversation, flow_data):
    """Route message to appropriate flow handler."""
    from ..flows.checkin_flow import process_checkin_flow

    if conversation.conversation_type == 'checkin':
        result = process_checkin_flow(
            conversation=conversation,
            guest=guest,
            flow_data=flow_data
        )
        return result

    # Unknown flow type
    return {
        "type": "text",
        "text": "Welcome to Lobbybee hotel CRM"
    }
