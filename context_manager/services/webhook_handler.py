import logging
import uuid

from django.utils import timezone
from guest.models import Guest, Stay
from hotel.models import Hotel

from .context import (
    get_active_context, get_or_create_context, log_conversation_message,
    update_context_activity)
from .flow import start_flow, transition_to_next_step
from .message import (
    generate_response, update_accumulated_data, validate_input)
from .navigation import handle_navigation, reset_context_to_main_menu

logger = logging.getLogger(__name__)

def process_webhook_message(whatsapp_number, message_body):
    """
    Process an incoming message for an ongoing conversation.

    Args:
        whatsapp_number (str): The guest's WhatsApp number.
        message_body (str): The message content.

    Returns:
        dict: Response with status and message.
    """
    try:
        context = get_active_context(whatsapp_number)
        if not context:
            return {
                'status': 'success',
                'message': 'Your session has ended. Please start a new conversation by scanning a QR code or typing "demo".'
            }

        # Update timestamps and log message
        update_context_activity(context, message_body)

        # Check for session expiry (5-hour rule)
        if context.flow_expires_at and timezone.now() > context.flow_expires_at:
            return reset_context_to_main_menu(context, 'Your session has expired. Returning to the main menu.')

        # Handle navigation commands first
        if message_body.lower() in ['back', 'main menu']:
            return handle_navigation(context, message_body.lower())

        # --- Core Flow Processing ---
        current_step = context.current_step
        if not current_step:
            logger.error(f"Context for {whatsapp_number} is active but has no current_step.")
            return reset_context_to_main_menu(context, 'Your conversation state is invalid. Returning to the main menu.')

        # Validate input against the current step's requirements
        is_valid, error_message = validate_input(context, message_body)
        if not is_valid:
            context.error_count += 1
            context.save()
            if context.error_count >= 5:
                context.is_active = False
                context.save()
                return {
                    'status': 'error',
                    'message': 'Too many consecutive errors. Conversation paused. Please start a new conversation.'
                }
            return {'status': 'success', 'message': error_message}

        context.error_count = 0
        context.save()

        # Update accumulated data and execute actions for the current step
        update_accumulated_data(context, message_body)
        # execute_step_actions(context) # Placeholder for future action execution

        # Transition to the next step
        next_step = transition_to_next_step(context, message_body)
        if not next_step:
            context.is_active = False
            context.save()
            return {
                'status': 'success',
                'message': 'Thank you. Conversation completed.' # Customizable in FlowStep
            }

        # Generate and log the response for the new step
        response_message = generate_response(context)
        log_conversation_message(context, response_message, is_from_guest=False)

        return {'status': 'success', 'message': response_message}

    except Exception as e:
        logger.error(f"Error processing webhook message for {whatsapp_number}: {str(e)}", exc_info=True)
        return {'status': 'error', 'message': 'An error occurred. Please try again.'}


def handle_initial_message(whatsapp_number, message_body):
    """
    Handles the first message from a user, which starts a new flow.
    (e.g., from a QR code scan, typing "demo", or a generic greeting).
    """
    flow_category = None
    hotel = None

    if message_body.lower().startswith('start-'):
        try:
            hotel_id_str = message_body.lower().replace('start-', '')
            hotel = Hotel.objects.get(id=uuid.UUID(hotel_id_str))
            flow_category = 'guest_checkin'
        except (ValueError, Hotel.DoesNotExist):
            return {'status': 'error', 'message': 'Invalid hotel identifier.'}
    elif message_body.lower() == 'demo':
        flow_category = 'new_guest_discovery'
        hotel = Hotel.objects.first()  # In demo mode, associate with the first hotel
    else:
        # For a generic greeting, determine if user is new, returning, or in-stay.
        try:
            guest = Guest.objects.get(whatsapp_number=whatsapp_number)
            # Guest exists. Check for an active stay.
            active_stay = Stay.objects.filter(
                guest=guest,
                status='active',
                check_in_date__lte=timezone.now(),
                check_out_date__gte=timezone.now()
            ).select_related('hotel').first()

            if active_stay:
                hotel = active_stay.hotel
                flow_category = 'in_stay_services'
            else:
                # Known guest, but no active stay. This is a returning guest.
                flow_category = 'returning_guest'
                hotel = Hotel.objects.first() # Default hotel for platform interactions

        except Guest.DoesNotExist:
            # Guest is not known, so proceed to discovery.
            flow_category = 'new_guest_discovery_interactive'
            hotel = Hotel.objects.first()

    if not hotel:
        return {'status': 'error', 'message': 'No hotels are configured for the demo.'}

    if not flow_category:
        # This should not be reached with the current logic.
        return {'status': 'error', 'message': 'Could not determine the correct action. Please scan a valid QR code.'}

    # Get or create the guest and context
    guest, _ = Guest.objects.get_or_create(
        whatsapp_number=whatsapp_number,
        defaults={'full_name': 'Guest'} # Basic default
    )
    context = get_or_create_context(whatsapp_number, guest, hotel)
    update_context_activity(context, message_body)

    # Start the determined flow
    return start_flow(context, flow_category)
