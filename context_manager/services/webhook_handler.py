import logging
import os
import uuid
from datetime import timedelta

from django.utils import timezone
from guest.models import Guest, Stay
from hotel.models import Hotel

from .context import (
    get_active_context, get_or_create_context, log_conversation_message,
    update_context_activity, reset_user_conversation)
from .flow import start_flow, transition_to_next_step
from .message import (
    generate_response, update_accumulated_data, validate_input)
from .navigation import handle_navigation, reset_context_to_main_menu

logger = logging.getLogger(__name__)

# Define the session timeout duration
SESSION_TIMEOUT = timedelta(hours=5)

# Admin command configuration
ADMIN_RESET_COMMAND = "admin_reset_user:"
FROM_NO_ADMIN = os.environ.get('FROM_NO_ADMIN')

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
        # --- Admin Command Handling ---
        if FROM_NO_ADMIN and whatsapp_number == FROM_NO_ADMIN and message_body.lower().startswith(ADMIN_RESET_COMMAND):
            target_user_id = message_body.lower().replace(ADMIN_RESET_COMMAND, '').strip()
            if target_user_id:
                deleted_count = reset_user_conversation(target_user_id)
                return {
                    'status': 'success',
                    'message': f'Conversation data for user {target_user_id} reset. Deleted {deleted_count} contexts.'
                }
            else:
                return {
                    'status': 'error',
                    'message': f'Usage: {ADMIN_RESET_COMMAND}<user_id_to_reset>'
                }

        context = get_active_context(whatsapp_number)
        if not context:
            return {
                'status': 'success',
                'message': 'Your session has ended. Please start a new conversation by scanning a QR code or typing "demo".'
            }

        # Check for session expiry based on idle time
        if timezone.now() - context.last_activity > SESSION_TIMEOUT:
            return reset_context_to_main_menu(context, 'Your session has expired due to inactivity. Returning to the main menu.')

        # Update timestamps and log message *after* the expiry check
        update_context_activity(context, message_body)

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

        # --- Flow Transition Check ---
        if (
            context.current_step.template.allowed_flow_categories
            and message_body in context.current_step.template.allowed_flow_categories
        ):
            return start_flow(context, message_body)

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
            # Aligning with seed.sql: 'random_guest' is the flow for new/discovery
            flow_category = 'random_guest'
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
