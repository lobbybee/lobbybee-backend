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
    generate_response, update_accumulated_data, validate_input, format_message)
from .navigation import handle_navigation, reset_context_to_main_menu
from .message_enricher import enrich_message_with_metadata, enrich_messages_list
# Import the new checkin finalizer
from .checkin_finalizer import finalize_checkin

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
        dict: Response with status and a list of messages.
    """
    try:
        # --- Admin Command Handling ---
        if FROM_NO_ADMIN and whatsapp_number == FROM_NO_ADMIN and message_body.lower().startswith(ADMIN_RESET_COMMAND):
            target_user_id = message_body.lower().replace(ADMIN_RESET_COMMAND, '').strip()
            if target_user_id:
                deleted_count = reset_user_conversation(target_user_id)
                admin_message = format_message(f'Conversation data for user {target_user_id} reset. Deleted {deleted_count} contexts.')
                enriched_message = enrich_message_with_metadata(
                    admin_message,
                    message_type='text',
                    status='success'
                )
                return {
                    'status': 'success',
                    'messages': [enriched_message]
                }
            else:
                error_message = format_message(f'Usage: {ADMIN_RESET_COMMAND}<user_id_to_reset>')
                enriched_error = enrich_message_with_metadata(
                    error_message,
                    message_type='text',
                    status='error'
                )
                return {
                    'status': 'error',
                    'messages': [enriched_error]
                }

        context = get_active_context(whatsapp_number)
        if not context:
            session_ended_message = format_message('Your session has ended. Please start a new conversation by scanning a QR code or typing "demo".')
            enriched_message = enrich_message_with_metadata(
                session_ended_message,
                message_type='text',
                status='info'
            )
            return {
                'status': 'success',
                'messages': [enriched_message]
            }

        # Check for session expiry based on idle time
        if timezone.now() - context.last_activity > SESSION_TIMEOUT:
            # If the session is for a demo hotel, wipe the user's data completely.
            if context.hotel and context.hotel.is_demo:
                user_id = context.user_id
                reset_user_conversation(user_id)
                demo_expired_message = format_message('Your demo session has expired and all associated data has been cleared. Type "demo" to start a new one.')
                enriched_message = enrich_message_with_metadata(
                    demo_expired_message,
                    message_type='text',
                    status='info'
                )
                return {
                    'status': 'success',
                    'messages': [enriched_message]
                }
            # Otherwise, for a real hotel, just reset to the main menu.
            return reset_context_to_main_menu(context, 'Your session has expired due to inactivity. Returning to the main menu.')

        # Update timestamps and log message *after* the expiry check
        update_context_activity(context, message_body)

        # Handle global commands that can interrupt a flow
        if message_body.lower().startswith('start-'):
            # Deactivate the current context to allow a new one to be created/re-activated.
            context.is_active = False
            context.save()
            # Let handle_initial_message create the new context and start the flow.
            return handle_initial_message(whatsapp_number, message_body)

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
                too_many_errors_message = format_message('Too many consecutive errors. Conversation paused. Please start a new conversation.')
                enriched_error = enrich_message_with_metadata(
                    too_many_errors_message,
                    message_type='text',
                    status='error'
                )
                return {
                    'status': 'error',
                    'messages': [enriched_error]
                }
            
            invalid_option_message = format_message(error_message)
            enriched_error = enrich_message_with_metadata(
                invalid_option_message,
                message_type='text',
                status='warning'
            )
            return {'status': 'success', 'messages': [enriched_error]}

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
            # The flow has ended. Send a completion message and then show the main menu.
            completion_message = 'Thank you. Conversation completed.'
            # By not deactivating the context and resetting to main menu,
            # the user can immediately start a new interaction.
            return reset_context_to_main_menu(context, completion_message)

        # Generate and log the response for the new step
        response_message = generate_response(context)
        log_conversation_message(context, response_message, is_from_guest=False)
        
        # Enrich the message with metadata
        enriched_message = enrich_message_with_metadata(
            format_message(response_message),
            message_type=context.current_step.template.message_type,
            status='success'
        )

        return {'status': 'success', 'messages': [enriched_message]}

    except Exception as e:
        logger.error(f"Error processing webhook message for {whatsapp_number}: {str(e)}", exc_info=True)
        error_message = format_message('An error occurred. Please try again.')
        enriched_error = enrich_message_with_metadata(
            error_message,
            message_type='text',
            status='error'
        )
        return {'status': 'error', 'messages': [enriched_error]}


def handle_initial_message(whatsapp_number, message_body):
    """
    Handles the first message from a user, which starts a new flow.
    (e.g., from a QR code scan, typing "demo", or a generic greeting).
    This function avoids creating a Guest object immediately.
    For checkin flows, it checks for an existing guest.
    For other flows, no Guest object is created here.
    """
    flow_category = None
    hotel = None
    guest = None # Initialize guest as None

    if message_body.lower().startswith('start-'):
        try:
            hotel_id_str = message_body.lower().replace('start-', '')
            hotel = Hotel.objects.get(id=uuid.UUID(hotel_id_str))
            flow_category = 'guest_checkin'
            # For checkin, check if guest already exists, but don't create yet
            try:
                guest = Guest.objects.get(whatsapp_number=whatsapp_number)
                # Indicate this is an existing guest for checkin
                # We'll store this flag in context_data later
            except Guest.DoesNotExist:
                # Guest does not exist, will be created at checkin completion
                # Store a flag in context_data to indicate this
                pass
        except (ValueError, Hotel.DoesNotExist):
            error_message = format_message('Invalid hotel identifier.')
            enriched_error = enrich_message_with_metadata(
                error_message,
                message_type='text',
                status='error'
            )
            return {'status': 'error', 'messages': [enriched_error]}
    elif message_body.lower().strip() == 'demo':
        # Aligning with seed.sql: 'random_guest' is the correct category for demo/discovery
        flow_category = 'random_guest'
        hotel = Hotel.objects.filter(is_demo=True).first()
        logger.info(f"Attempting to start demo flow. Found hotel: {hotel.name if hotel else 'None'}")
        if not hotel:
            error_message = format_message('No hotels are configured for the demo.')
            enriched_error = enrich_message_with_metadata(
                error_message,
                message_type='text',
                status='error'
            )
            return {'status': 'error', 'messages': [enriched_error]}
        # No guest creation for demo
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
                # Do not assign a specific hotel, handle at platform level
                hotel = None # Indicate platform-level context
            # Guest object 'guest' is already retrieved and will be passed

        except Guest.DoesNotExist:
            # Guest is not known, so proceed to discovery.
            # Aligning with seed.sql: 'random_guest' is the flow for new/discovery
            flow_category = 'random_guest'
            hotel = None # Platform level context for unknown users
            # No guest creation for unknown returning/discovery flows

    if not flow_category:
        # This should not be reached with the current logic.
        error_message = format_message('Could not determine the correct action. Please scan a valid QR code.')
        enriched_error = enrich_message_with_metadata(
            error_message,
            message_type='text',
            status='error'
        )
        return {'status': 'error', 'messages': [enriched_error]}

    # Get or create the context. Guest is passed but get_or_create_context handles guest=None
    context = get_or_create_context(whatsapp_number, guest, hotel)
    
    # Store additional flags in context_data based on the flow initiation logic
    if flow_category == 'guest_checkin':
        if guest:
             # Existing guest, flag for potential update
            context.context_data['is_temp_guest'] = False
        else:
            # New guest for checkin, flag for creation
            context.context_data['is_temp_guest'] = True
            context.context_data['temp_whatsapp_number'] = whatsapp_number
        context.save(update_fields=['context_data']) # Save the flags
        
    update_context_activity(context, message_body)

    # Start the determined flow
    return start_flow(context, flow_category)