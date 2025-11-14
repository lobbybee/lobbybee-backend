# flows/demo_flow.py

import logging
from django.db import transaction

logger = logging.getLogger(__name__)


class DemoStep:
    """Constants for demo flow steps."""
    INITIAL = 0
    SERVICE_MENU = 1
    SERVICE_SELECTED = 2
    ORDER_CONFIRMATION = 3
    COMPLETED = 4


# Demo services available
DEMO_SERVICES = {
    'restaurant': 'Restaurant',
    'management': 'Management',
    'housekeeping': 'Housekeeping',
    'exit': 'Exit Demo'
}


def process_demo_flow(guest=None, hotel_id=None, conversation=None, flow_data=None, is_fresh_demo_command=False):
    """
    Process demo flow messages.

    Args:
        guest: Guest object (can be None for new guests)
        hotel_id: Hotel ID from command
        conversation: Conversation object (for continuing flows)
        flow_data: WhatsApp message data dict
        is_fresh_demo_command: Whether this is a fresh /demo command

    Returns:
        dict: Response object to send back
    """
    # Extract data from flow_data
    message_text = flow_data.get('message', '') if flow_data else ''
    message_id = flow_data.get('message_id') if flow_data else None
    logger.info(f"Received demo message: {message_text}")

    # Step handler pattern
    step_handlers = {
        DemoStep.INITIAL: handle_initial_step,
        DemoStep.SERVICE_MENU: handle_service_menu_step,
        DemoStep.SERVICE_SELECTED: handle_service_selected_step,
        DemoStep.ORDER_CONFIRMATION: handle_order_confirmation_step,
    }

    # Handle fresh demo command
    if is_fresh_demo_command:
        return handle_fresh_demo_command(guest, hotel_id, flow_data)

    # For continuing flows, determine current step
    if not conversation:
        return {
            "type": "text",
            "text": "No active demo conversation found. Please start again with /demo"
        }

    # Get the last SYSTEM flow message to determine current step
    last_flow_message = conversation.messages.filter(
        is_flow=True,
        sender_type='staff'
    ).order_by('-created_at').first()

    if last_flow_message is None:
        current_step = DemoStep.INITIAL
    else:
        current_step = last_flow_message.flow_step

    logger.info(f"DEBUG: Determined current_step={current_step} from last_system_message flow_step={last_flow_message.flow_step if last_flow_message else None}")

    # Save incoming guest message
    save_guest_message(conversation, message_text, message_id, current_step)

    # Get appropriate step handler
    handler = step_handlers.get(current_step, handle_unknown_step)

    return handler(conversation, guest, message_text, flow_data)


def handle_fresh_demo_command(guest, hotel_id, flow_data):
    """Handle fresh /demo command."""
    from hotel.models import Hotel
    from chat.models import Conversation

    # For demo flow, we don't need a real hotel - just use any active hotel or create a demo context
    hotel = None
    if hotel_id:
        try:
            hotel = Hotel.objects.get(id=hotel_id, is_active=True)
        except Hotel.DoesNotExist:
            # Continue without hotel for demo purposes
            logger.info(f"Hotel {hotel_id} not found, continuing with demo flow without hotel")
            pass

    # Create guest if not exists (for demo purposes)
    if not guest:
        from guest.models import Guest
        whatsapp_number = flow_data.get('whatsapp_number')
        guest, created = Guest.objects.get_or_create(
            whatsapp_number=whatsapp_number,
            defaults={
                'status': 'demo_active',
                'is_whatsapp_active': True,
                'full_name': 'Demo Guest',  # Default demo name
            }
        )
    else:
        # Update guest status for demo
        guest.status = 'demo_active'
        guest.save(update_fields=['status'])

    # Archive any existing active demo conversations for this guest
    Conversation.objects.filter(
        guest=guest,
        conversation_type='demo',
        status='active'
    ).update(status='archived')

    # Create new demo conversation
    with transaction.atomic():
        conversation = Conversation.objects.create(
            guest=guest,
            hotel=hotel,
            department='Demo',
            conversation_type='demo',
            status='active'
        )

        # Start with initial step
        return handle_initial_step(conversation, guest, flow_data.get('message', ''), flow_data)


def handle_initial_step(conversation, guest, message_text, flow_data):
    """Initial step - welcome message and service menu."""
    
    response_text = "Welcome to Demo Hotel!"
    body_text = "Here are the services we offer:\n\n• Restaurant - Order food and drinks\n• Management - Speak with hotel management\n• Housekeeping - Request room services\n• Exit Demo - End the demo experience\n\nPlease select a service from the options below:"
    
    save_system_message(conversation, f"{response_text}\n\n{body_text}", DemoStep.SERVICE_MENU)
    
    return {
        "type": "list",
        "text": response_text,
        "body_text": body_text,
        "options": [
            {"id": "restaurant", "title": "🍽️ Restaurant"},
            {"id": "management", "title": "👔 Management"},
            {"id": "housekeeping", "title": "🧹 Housekeeping"},
            {"id": "exit", "title": "🚪 Exit Demo"}
        ]
    }


def handle_service_menu_step(conversation, guest, message_text, flow_data):
    """Handle service selection from menu."""
    
    response = message_text.strip().lower()
    
    # Handle both text responses and button responses (option_0, option_1, etc.)
    selected_service = None
    
    # Check for direct service name matches
    if response in ['restaurant', 'management', 'housekeeping', 'exit']:
        selected_service = response
    # Handle WhatsApp interactive button responses
    elif response.startswith('option_'):
        try:
            option_index = int(response.split('_')[1])
            service_keys = list(DEMO_SERVICES.keys())
            if 0 <= option_index < len(service_keys):
                selected_service = service_keys[option_index]
        except (ValueError, IndexError):
            pass
    # Handle button responses for specific services
    elif response in ['btn_0', 'btn_1', 'btn_2']:
        button_map = {'btn_0': 'restaurant', 'btn_1': 'management', 'btn_2': 'housekeeping'}
        selected_service = button_map.get(response)
    elif response == 'btn_3':  # Exit demo button
        selected_service = 'exit'
    
    if not selected_service or selected_service not in DEMO_SERVICES:
        # Invalid selection - show menu again
        return handle_initial_step(conversation, guest, message_text, flow_data)
    
    if selected_service == 'exit':
        # End the demo
        conversation.status = 'closed'
        conversation.save(update_fields=['status'])
        
        response_text = "Thank you for trying Demo Hotel!"
        body_text = "We hope you enjoyed exploring our services. This was a demonstration of the Lobbybee hotel CRM system. In a real hotel, you would be connected to actual services and staff members.\n\nFeel free to start the demo again with /demo"
        
        save_system_message(conversation, f"{response_text}\n\n{body_text}", DemoStep.COMPLETED)
        
        return {
            "type": "text",
            "text": response_text,
            "body_text": body_text
        }
    
    # Service selection is stored in the guest message content, no need for separate storage
    
    # Show service connection message
    service_name = DEMO_SERVICES[selected_service]
    response_text = f"Connecting to {service_name}"
    body_text = f"You are now live connected to the {service_name}. Please place your order or make your request:"
    
    save_system_message(conversation, f"{response_text}\n\n{body_text}", DemoStep.SERVICE_SELECTED)
    
    return {
        "type": "text",
        "text": response_text,
        "body_text": body_text
    }


def handle_service_selected_step(conversation, guest, message_text, flow_data):
    """Handle messages after service selection - simulate order processing."""
    
    # Get the selected service from the previous guest message
    selected_service = 'restaurant'  # Default
    
    # Look at the last guest message from the service menu step to determine what service was selected
    last_guest_message_from_service_menu = conversation.messages.filter(
        sender_type='guest',
        is_flow=True,
        flow_step=DemoStep.SERVICE_MENU
    ).order_by('-created_at').first()
    
    if last_guest_message_from_service_menu:
        guest_response = last_guest_message_from_service_menu.content.strip().lower()
        
        # Parse the service selection from the guest's response
        if guest_response in ['restaurant', 'management', 'housekeeping']:
            selected_service = guest_response
        elif guest_response.startswith('option_'):
            try:
                option_index = int(guest_response.split('_')[1])
                service_keys = list(DEMO_SERVICES.keys())
                if 0 <= option_index < len(service_keys):
                    selected_service = service_keys[option_index]
            except (ValueError, IndexError):
                pass
        elif guest_response in ['btn_0', 'btn_1', 'btn_2']:
            button_map = {'btn_0': 'restaurant', 'btn_1': 'management', 'btn_2': 'housekeeping'}
            selected_service = button_map.get(guest_response, 'restaurant')
    
    service_name = DEMO_SERVICES[selected_service]
    
    # Simulate order confirmation based on service
    if selected_service == 'restaurant':
        response_text = "Restaurant Order Received"
        body_text = f"Your order has been placed and forwarded to our kitchen staff. Please be awaited while we prepare your order.\n\nEstimated time: 15-20 minutes"
    elif selected_service == 'management':
        response_text = "Management Request Received"
        body_text = f"Your request has been forwarded to hotel management. Someone will contact you shortly to address your concerns.\n\nResponse time: Within 10 minutes"
    elif selected_service == 'housekeeping':
        response_text = "Housekeeping Request Received"
        body_text = f"Your housekeeping request has been registered. Our staff will attend to your room shortly.\n\nResponse time: Within 5-10 minutes"
    else:
        response_text = "Request Received"
        body_text = f"Your request has been received and forwarded to the appropriate department.\n\nWe will respond as soon as possible."
    
    save_system_message(conversation, f"{response_text}\n\n{body_text}", DemoStep.ORDER_CONFIRMATION)
    
    return {
        "type": "button",
        "text": response_text,
        "body_text": body_text,
        "options": [
            {"id": "back_to_menu", "title": "Back to Main Menu"}
        ]
    }


def handle_order_confirmation_step(conversation, guest, message_text, flow_data):
    """Handle back to main menu request."""
    
    response = message_text.strip().lower()
    
    # Handle button response
    if response in ['back_to_menu', 'btn_0']:
        # Return to service menu
        return handle_initial_step(conversation, guest, message_text, flow_data)
    else:
        # Any other response - show confirmation again
        return handle_service_selected_step(conversation, guest, message_text, flow_data)


def handle_unknown_step(conversation, guest, message_text, flow_data):
    """Handle unknown step."""
    return {
        "type": "text",
        "text": "Something went wrong with the demo flow. Please start again with /demo"
    }


def save_guest_message(conversation, message_text, message_id, flow_step):
    """Save incoming guest message."""
    from chat.models import Message

    Message.objects.create(
        conversation=conversation,
        sender_type='guest',
        message_type='text',
        content=message_text,
        whatsapp_message_id=message_id,
        is_flow=True,
        flow_id='demo',
        flow_step=flow_step
    )

    conversation.update_last_message(message_text)


def save_system_message(conversation, content, flow_step, is_success=True):
    """Save system/bot response message."""
    from chat.models import Message

    Message.objects.create(
        conversation=conversation,
        sender_type='staff',
        message_type='system',
        content=content,
        is_flow=True,
        flow_id='demo',
        flow_step=flow_step,
        is_flow_step_success=is_success
    )