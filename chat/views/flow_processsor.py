# utils/webhook_handler.py

import re
import logging
from tempfile import template
from django.utils import timezone

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

    # Handle stay extension response buttons first
    from ..flows.checkout_extension_flow import process_checkout_extension_response
    extension_result = process_checkout_extension_response(guest, message_text)
    if extension_result is not None:
        whatsapp_payload = adapt_checkin_response_to_whatsapp(extension_result, whatsapp_number)
        return whatsapp_payload, 200

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

    # Handle start menu button responses
    if message_text in ['start_demo', 'start_contact', 'start_history']:
        result = handle_start_menu_command(guest, message_text)
        logger.info(f"handle_start_menu_command returned: {result}, type: {type(result)}")
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

    # Check if template has media
    media_url = template_result.get('media_url') if template_result.get('success') else None
    
    # Create welcome message with media if available
    if media_url:
        # Determine media type from URL or default to image
        media_type = 'image'  # Default to image
        if media_url.lower().endswith(('.mp4', '.3gp', '.mov')):
            media_type = 'video'
        elif media_url.lower().endswith(('.mp3', '.aac', '.ogg', '.amr', '.m4a')):
            media_type = 'audio'
        elif media_url.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx')):
            media_type = 'document'
        
        welcome_message = {
            "type": media_type,
            "media_url": media_url,
            "text": message_text  # Text will be used as caption
        }
    else:
        # Create text-only welcome message
        welcome_message = {
            "type": "text",
            "text": message_text
        }

    # Always add follow-up buttons for start/welcome flow
    button_options = [
        {"id": "start_demo", "title": "View Demo"},
        {"id": "start_contact", "title": "Contact"}
    ]

    # Add "Stay History" button if guest exists
    if guest:
        button_options.append({"id": "start_history", "title": "Stay History"})

    button_message = {
        "type": "button",
        "text": "How can we help you?",
        "body_text": "Please select an option below to get started",
        "options": button_options
    }

    # Return multiple messages converted to WhatsApp payloads
    flow_response = [welcome_message, button_message]
    whatsapp_payload = adapt_checkin_response_to_whatsapp(flow_response, whatsapp_number)
    return whatsapp_payload, 200


def handle_start_menu_command(guest, button_id):
    """Handle start menu button clicks."""
    
    if button_id == 'start_demo':
        # Trigger demo mode flow
        return handle_demo_command(guest, {})
    
    elif button_id == 'start_contact':
        return {
            "type": "text",
            "text": "Ready to transform your guest experience? Get in touch with our team and discover how LobbyBee can revolutionize your hotel operations.\n\n📬 Email: hello@lobbybee.com\n📱 Phone: +917736600773\n🌐 Website: https://lobbybee.com\n\nWe're excited to hear from you! 🚀"
        }
    
    elif button_id == 'start_history':
        from guest.models import Stay

        if not guest:
            return {
                "type": "text",
                "text": "No stay history found for this number."
            }

        stays = (
            Stay.objects
            .filter(guest=guest, check_out_date__lt=timezone.now())
            .select_related('hotel', 'room')
            .order_by('-check_out_date')[:5]
        )

        if not stays:
            return {
                "type": "text",
                "text": "🏨 Stay History\n\nNo past stays found yet."
            }

        lines = ["🏨 Stay History (Last 5)\n"]
        for idx, stay in enumerate(stays, start=1):
            room_label = stay.room.number if stay.room else "N/A"
            lines.append(
                f"{idx}. {stay.hotel.name}\n"
                f"   Check-in: {stay.check_in_date.strftime('%d %b %Y')}\n"
                f"   Check-out: {stay.check_out_date.strftime('%d %b %Y')}\n"
                f"   Room: {room_label}\n"
                f"   Status: {stay.get_status_display()}"
            )

        return {
            "type": "text",
            "text": "\n\n".join(lines)
        }
    
    else:
        # Fallback for unknown button ID
        return {
            "type": "text",
            "text": "Sorry, I didn't understand that selection. Please try again."
        }


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

    # Check if template has media
    media_url = template_result.get('media_url') if template_result.get('success') else None
    
    if media_url:
        # Determine media type from URL
        media_type = 'image'  # Default to image
        if media_url.lower().endswith(('.mp4', '.3gp', '.mov')):
            media_type = 'video'
        elif media_url.lower().endswith(('.mp3', '.aac', '.ogg', '.amr', '.m4a')):
            media_type = 'audio'
        elif media_url.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx')):
            media_type = 'document'
        
        return {
            "type": media_type,
            "media_url": media_url,
            "text": message_text  # Text will be used as caption
        }
    else:
        return {
            "type": "text",
            "text": message_text
        }
