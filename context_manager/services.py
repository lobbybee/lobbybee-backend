from .models import (
    ConversationContext, FlowStep, FlowStepTemplate, FlowTemplate, 
    HotelFlowConfiguration, ConversationMessage
)
from .tasks import send_pending_messages
from guest.models import Guest, Stay
from hotel.models import Hotel
import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
import uuid

logger = logging.getLogger(__name__)

# --- Main Service Functions ---

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


# --- Context and State Management ---

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
            'context_data': {'guest_id': guest.id, 'accumulated_data': {}},
            'flow_expires_at': timezone.now() + timedelta(hours=5)
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
        context.flow_expires_at = timezone.now() + timedelta(hours=5)
        context.save()
    
    return context

def get_active_context(whatsapp_number):
    """Retrieve the active conversation context for a guest."""
    return ConversationContext.objects.filter(user_id=whatsapp_number, is_active=True).first()

def update_context_activity(context, message_body):
    """Updates activity timestamps and logs the incoming message."""
    context.last_guest_message_at = timezone.now()
    context.last_activity = timezone.now()
    context.save()
    log_conversation_message(context, message_body, is_from_guest=True)
    # Trigger async task to handle pending messages within the 24-hour window
    send_pending_messages.delay(context.user_id)


# --- Flow Control ---

def start_flow(context, flow_category):
    """
    Starts a new conversation flow for the given context.
    """
    try:
        flow_template = FlowTemplate.objects.filter(category=flow_category, is_active=True).first()
        if not flow_template:
            raise FlowTemplate.DoesNotExist(f"Active flow template for category '{flow_category}' not found.")

        first_step_template = FlowStepTemplate.objects.filter(flow_template=flow_template).order_by('id').first()
        
        if not first_step_template:
            raise FlowStepTemplate.DoesNotExist(f"No starting step found for flow category '{flow_category}'.")

        # Get or create the concrete FlowStep for the hotel
        first_step, _ = FlowStep.objects.get_or_create(
            hotel=context.hotel,
            template=first_step_template,
            defaults={'step_id': first_step_template.step_name.lower().replace(' ', '_')}
        )

        context.current_step = first_step
        context.navigation_stack = [first_step.id]
        context.save()

        response_message = generate_response(context)
        log_conversation_message(context, response_message, is_from_guest=False)
        return {'status': 'success', 'message': response_message}

    except FlowTemplate.DoesNotExist as e:
        logger.error(str(e))
        return {'status': 'error', 'message': 'This service is currently unavailable.'}
    except FlowStepTemplate.DoesNotExist as e:
        logger.error(str(e))
        return {'status': 'error', 'message': 'This service is not configured correctly.'}


def transition_to_next_step(context, user_input):
    """
    Determines the next step, updates the context, and returns the new step.
    """
    current_step = context.current_step
    next_step_template = None

    # 1. Check for conditional transitions based on user input
    if current_step.template.conditional_next_steps:
        next_step_template_id = current_step.template.conditional_next_steps.get(user_input) or \
                                current_step.template.conditional_next_steps.get('*')
        if next_step_template_id:
            try:
                next_step_template = FlowStepTemplate.objects.get(id=next_step_template_id)
            except FlowStepTemplate.DoesNotExist:
                logger.warning(f"Conditional next step template ID {next_step_template_id} not found.")

    # 2. If no conditional match, use the default next step
    if not next_step_template:
        next_step_template = current_step.template.next_step_template

    # 3. If there is a next step, update the context
    if next_step_template:
        next_step, _ = FlowStep.objects.get_or_create(
            hotel=context.hotel,
            template=next_step_template,
            defaults={'step_id': next_step_template.step_name.lower().replace(' ', '_')}
        )
        context.current_step = next_step
        context.navigation_stack.append(next_step.id)
        context.save()
        return next_step

    return None # End of flow


# --- Navigation ---

def handle_navigation(context, command):
    """
    Handles 'back' and 'main menu' commands.
    'back' will skip over collection steps where data is already present.
    """
    if command == 'main menu':
        return reset_context_to_main_menu(context, 'Returning to the main menu.')

    elif command == 'back':
        if len(context.navigation_stack) <= 1:
            return reset_context_to_main_menu(context, 'You are at the beginning. Returning to main menu.')

        context.navigation_stack.pop()  # Pop the current step first

        while context.navigation_stack:
            previous_step_id = context.navigation_stack[-1]
            try:
                previous_step = FlowStep.objects.get(id=previous_step_id)
            except FlowStep.DoesNotExist:
                return reset_context_to_main_menu(context, 'Could not navigate back. Returning to main menu.')

            # Check if this step should be skipped
            step_template = previous_step.template
            step_name = step_template.step_name
            should_skip = False
            if 'collect' in step_name.lower():
                data_key = step_name.lower().replace('collect', '').strip().replace(' ', '_')
                if context.context_data.get('accumulated_data', {}).get(data_key):
                    should_skip = True
            
            if should_skip and len(context.navigation_stack) > 1:
                context.navigation_stack.pop()
            else:
                # Found our destination
                context.current_step = previous_step
                context.error_count = 0
                context.save()
                
                response_message = generate_response(context)
                log_conversation_message(context, response_message, is_from_guest=False)
                return {'status': 'success', 'message': response_message}
        
        # If loop finishes, we've popped everything. Go to main menu.
        return reset_context_to_main_menu(context, 'You are at the beginning. Returning to main menu.')


def reset_context_to_main_menu(context, message):
    """
    Resets the context to the main menu flow.
    """
    context.context_data['accumulated_data'] = {}
    context.error_count = 0
    context.save()
    # We pass the context and the category, start_flow handles the rest
    response = start_flow(context, 'main_menu')
    # Prepend the reason for the reset to the response message
    response['message'] = f"{message}\n\n{response.get('message', '')}"
    return response


# --- Input, Response, and Data Handling ---

def validate_input(context, user_input):
    """Validates user input against the current step's requirements."""
    step_template = context.current_step.template
    # Get customized options if they exist
    config = HotelFlowConfiguration.objects.filter(hotel=context.hotel, flow_template=step_template.flow_template).first()
    options = step_template.options
    if config and config.customization_data:
        step_customs = config.customization_data.get('step_customizations', {})
        # IMPORTANT: Assumes customization is keyed by step_name
        custom_options = step_customs.get(step_template.step_name, {}).get('options')
        if custom_options:
            options = custom_options

    if options:
        if user_input in options:
            return True, ""
        else:
            options_list = ", ".join([f"'{k}'" for k in options.keys()])
            return False, f"Invalid option. Please select from: {options_list}"
    
    return True, "" # No options to validate against

def generate_response(context):
    """Generates a response message for the current flow step with placeholders."""
    step_template = context.current_step.template
    config = HotelFlowConfiguration.objects.filter(hotel=context.hotel, flow_template=step_template.flow_template).first()
    
    message_template = step_template.message_template
    options = step_template.options

    # Apply hotel-specific customizations
    if config and config.customization_data:
        step_customs = config.customization_data.get('step_customizations', {})
        # IMPORTANT: Assumes customization is keyed by step_name
        customizations = step_customs.get(step_template.step_name, {})
        message_template = customizations.get('message_template', message_template)
        options = customizations.get('options', options)

    # Replace placeholders and add options
    response_message = replace_placeholders(message_template, context)
    if options:
        options_text = "\n".join([f"{key}. {value}" for key, value in options.items()])
        response_message += f"\n{options_text}"
        
    return response_message

def replace_placeholders(template, context):
    """Replaces placeholders like {guest_name} with actual data."""
    guest_id = context.context_data.get('guest_id')
    guest = Guest.objects.get(id=guest_id) if guest_id else None
    hotel = context.hotel
    stay = Stay.objects.filter(guest=guest, hotel=hotel, status='active').first() if guest else None

    replacements = {
        '{guest_id}': str(guest.id) if guest else '',
        '{guest_name}': getattr(guest, 'full_name', 'Guest') if guest else 'Guest',
        '{guest_email}': getattr(guest, 'email', '') if guest else '',
        '{guest_nationality}': getattr(guest, 'nationality', '') if guest else '',
        '{loyalty_points}': str(getattr(guest, 'loyalty_points', 0)) if guest else '0',
        '{hotel_name}': getattr(hotel, 'name', ''),
        '{wifi_password}': getattr(hotel, 'wifi_password', ''),
        '{room_number}': getattr(stay.room, 'room_number', '') if stay and stay.room else '',
        '{checkin_time}': stay.check_in_date.strftime('%d-%m-%Y %H:%M') if stay and stay.check_in_date else '',
        '{checkout_time}': stay.check_out_date.strftime('%d-%m-%Y %H:%M') if stay and stay.check_out_date else '',
    }

    # Add accumulated data to replacements
    if 'accumulated_data' in context.context_data:
        for key, value in context.context_data['accumulated_data'].items():
            replacements[f'{{{key}}}'] = str(value)

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
        
    return template

def update_accumulated_data(context, user_input):
    """
    Updates the context's accumulated_data based on the current step.
    This logic can be expanded with more sophisticated rules.
    """
    step_name = context.current_step.template.step_name
    # A simple convention: if a step name contains "Collect", store the input
    # using a key derived from the step name.
    if 'collect' in step_name.lower():
        data_key = step_name.lower().replace('collect', '').strip().replace(' ', '_')
        if data_key:
            # Ensure accumulated_data exists
            if 'accumulated_data' not in context.context_data:
                context.context_data['accumulated_data'] = {}
            context.context_data['accumulated_data'][data_key] = user_input
            context.save()

def log_conversation_message(context, content, is_from_guest):
    """Logs a single message to the ConversationMessage model."""
    ConversationMessage.objects.create(
        context=context,
        message_content=content,
        is_from_guest=is_from_guest
    )
