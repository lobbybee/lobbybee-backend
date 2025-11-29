# utils/webhook_handler.py

import re
import logging
from tempfile import template

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
    from chat.utils.template_util import process_template

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

    if command_type == 'demo':
        result = handle_demo_command(guest, flow_data)
        logger.info(f"handle_demo_command returned: {result}, type: {type(result)}")
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

    message_text = "Welcome to Lobbybee hotel CRM"
    template_result = process_template(
        hotel_id=1,
        template_name='lobbybee_app_start'
    )
    if template_result.get('success') and template_result.get('processed_content'):
        message_text = template_result['processed_content']

    # No command matched - fallback response
    return create_text_message_payload(
        whatsapp_number,
        message_text
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

    # Check for demo command: /demo
    demo_pattern = r'^/demo$'
    if re.match(demo_pattern, message_text, re.IGNORECASE):
        return ('demo', {})

    return (None, {})


def get_active_flow_conversation(guest):
    """Get guest's active flow conversation if any."""
    from chat.models import Conversation

    if not guest:
        return None

    logger.info(f"Looking for active flow conversation for guest: {guest.id}")

    # Priority order: checkin > demo > feedback
    # This ensures checkin flow responses don't get routed to feedback flows
    conversation_priority = ['checkin', 'demo', 'feedback']
    
    for conv_type in conversation_priority:
        active_conversation = Conversation.objects.filter(
            guest=guest,
            status='active',
            conversation_type=conv_type
        ).order_by('-created_at').first()  # Use created_at for more consistent ordering
        
        if active_conversation:
            logger.info(f"Found active {active_conversation.conversation_type} flow conversation: {active_conversation.id}")
            return active_conversation

    logger.info(f"No active flow conversation found for guest {guest.id}")
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


def handle_demo_command(guest, flow_data):
    """Handle /demo command."""
    from ..flows.demo_flow import process_demo_flow

    # Let the demo flow handle everything
    result = process_demo_flow(
        guest=guest,
        hotel_id=None,  # Demo doesn't need a real hotel
        flow_data=flow_data,
        is_fresh_demo_command=True
    )
    logger.info(f"process_demo_flow returned: {result}, type: {type(result)}")
    return result


def route_to_flow_handler(guest, conversation, flow_data):
    """Route message to appropriate flow handler."""
    from ..flows.checkin_flow import process_checkin_flow
    from ..flows.demo_flow import process_demo_flow
    from ..flows.feedback_flow import process_feedback_flow
    from chat.utils.template_util import process_template

    if conversation.conversation_type == 'checkin':
        result = process_checkin_flow(
            conversation=conversation,
            guest=guest,
            flow_data=flow_data
        )
        return result

    if conversation.conversation_type == 'demo':
        result = process_demo_flow(
            conversation=conversation,
            guest=guest,
            flow_data=flow_data
        )
        return result

    if conversation.conversation_type == 'feedback':
        result = process_feedback_flow(
            conversation=conversation,
            guest=guest,
            flow_data=flow_data
        )
        return result

    template_result = process_template(
        hotel_id=1,
        template_name='lobbybee_app_start'
    )

    # Unknown flow type - use template result if successful, otherwise fallback to default
    message_text = "Welcome to Lobbybee hotel CRM"
    if template_result.get('success') and template_result.get('processed_content'):
        message_text = template_result['processed_content']

    return {
        "type": "text",
        "text": message_text
    }
