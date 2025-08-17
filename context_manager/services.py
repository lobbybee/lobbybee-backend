from .models import ConversationContext, FlowStep, FlowStepTemplate, FlowTemplate, HotelFlowConfiguration
from guest.models import Guest, Stay
from hotel.models import Hotel
import logging
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)

def process_incoming_message(payload):
    """
    Process an incoming WhatsApp message and generate appropriate response.
    
    Args:
        payload (dict): Dictionary containing 'from_no' and 'message' keys
        
    Returns:
        dict: Response containing 'status' and 'message' keys
    """
    try:
        whatsapp_number = payload.get('from_no')
        user_message = payload.get('message', '').strip().lower()
        
        if not whatsapp_number:
            return {
                'status': 'error',
                'message': 'WhatsApp number is required'
            }
        
        # Get active context for this guest
        context = get_active_context(whatsapp_number)
        
        if not context:
            # Handle as new conversation or inactive context
            return {
                'status': 'success',
                'message': 'Thank you for your message. Please start a new conversation by scanning a QR code or typing "demo".'
            }
        
        # Reset last activity timestamp
        context.last_activity = timezone.now()
        context.save()
        
        # Handle navigation commands
        if user_message in ['back', 'main menu']:
            return handle_navigation(context, user_message)
        
        # Get current step using template system
        current_step_template_id = context.context_data.get('current_step_template')
        if not current_step_template_id:
            logger.error(f"No current step template found in context for {whatsapp_number}")
            return {
                'status': 'error',
                'message': 'Conversation state is invalid. Please start over.'
            }
        
        try:
            current_step_template = FlowStepTemplate.objects.get(id=current_step_template_id)
        except FlowStepTemplate.DoesNotExist:
            logger.error(f"FlowStepTemplate {current_step_template_id} does not exist")
            return {
                'status': 'error',
                'message': 'Conversation flow is invalid. Please start over.'
            }
        
        # Get hotel-specific flow step (with customizations)
        hotel_step = get_hotel_flow_step(context.hotel, current_step_template)
        
        # Validate input
        validation_result = validate_input(context, user_message, current_step_template, hotel_step)
        if not validation_result['valid']:
            # Increment error count
            context.context_data['error_count'] = context.context_data.get('error_count', 0) + 1
            context.save()
            
            # Check for error cooloff
            if context.context_data['error_count'] >= 5:
                context.is_active = False
                context.save()
                return {
                    'status': 'error',
                    'message': 'Too many consecutive errors. Conversation paused. Please start a new conversation.'
                }
            
            # Return validation error message
            return {
                'status': 'success',
                'message': validation_result['message']
            }
        
        # Reset error count on valid input
        if context.context_data.get('error_count', 0) > 0:
            context.context_data['error_count'] = 0
            context.save()
        
        # Update accumulated data
        update_accumulated_data(context, user_message, current_step_template)
        
        # Determine next step
        next_step_template = transition_step(context, user_message, current_step_template, hotel_step)
        
        if not next_step_template:
            # Conversation is ending
            context.is_active = False
            context.save()
            return {
                'status': 'success',
                'message': 'Thank you for your response. Conversation completed successfully.'
            }
        
        # Update context with next step
        context.context_data['current_step_template'] = next_step_template.id
        navigation_stack = context.context_data.get('navigation_stack', [])
        navigation_stack.append(next_step_template.id)
        context.context_data['navigation_stack'] = navigation_stack
        
        # Update flow expiry (5-hour rule)
        from datetime import timedelta
        context.flow_expires_at = timezone.now() + timedelta(hours=5)
        context.save()
        
        # Generate response for next step
        response_message = generate_response(context, next_step_template)
        
        return {
            'status': 'success',
            'message': response_message
        }
        
    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")
        return {
            'status': 'error',
            'message': 'An error occurred while processing your message. Please try again.'
        }

def get_active_context(whatsapp_number):
    """
    Retrieve the active conversation context for a guest.
    
    Args:
        whatsapp_number (str): Guest's WhatsApp number
        
    Returns:
        ConversationContext: Active context or None if not found
    """
    try:
        # For now, we'll assume the guest is associated with one hotel
        # In a real implementation, we might need to determine the hotel from the message
        context = ConversationContext.objects.filter(
            user_id=whatsapp_number,
            is_active=True
        ).first()
        return context
    except Exception as e:
        logger.error(f"Error retrieving context for {whatsapp_number}: {str(e)}")
        return None

def get_hotel_flow_step(hotel, step_template):
    """
    Get hotel-specific flow step with customizations.
    
    Args:
        hotel (Hotel): The hotel
        step_template (FlowStepTemplate): The base step template
        
    Returns:
        dict: Combined step data with hotel customizations
    """
    try:
        # Get hotel flow configuration
        config = HotelFlowConfiguration.objects.filter(
            hotel=hotel,
            flow_template=step_template.flow_template,
            is_enabled=True
        ).first()
        
        # Start with base template data
        step_data = {
            'message_template': step_template.message_template,
            'options': step_template.options,
            'conditional_next_steps': step_template.conditional_next_steps
        }
        
        # Apply customizations if they exist
        if config and config.customization_data:
            customizations = config.customization_data.get('step_customizations', {})
            step_customization = customizations.get(step_template.id, {})
            
            # Override with hotel customizations
            if 'message_template' in step_customization:
                step_data['message_template'] = step_customization['message_template']
            if 'options' in step_customization:
                step_data['options'] = step_customization['options']
            if 'conditional_next_steps' in step_customization:
                step_data['conditional_next_steps'] = step_customization['conditional_next_steps']
        
        return step_data
    except Exception as e:
        logger.error(f"Error getting hotel flow step: {str(e)}")
        # Return base template data if error occurs
        return {
            'message_template': step_template.message_template,
            'options': step_template.options,
            'conditional_next_steps': step_template.conditional_next_steps
        }

def generate_response(context, step_template):
    """
    Generate a response message for the current flow step.
    
    Args:
        context (ConversationContext): The conversation context
        step_template (FlowStepTemplate): The current flow step template
        
    Returns:
        str: The generated response message
    """
    try:
        # Get hotel-specific step data
        hotel_step_data = get_hotel_flow_step(context.hotel, step_template)
        
        # Start with the template message
        message_template = hotel_step_data['message_template']
        
        # Replace placeholders with actual data
        response_message = replace_placeholders(message_template, context)
        
        # Add options if they exist
        options = hotel_step_data['options']
        if options:
            options_text = "\n"
            for key, value in options.items():
                options_text += f"{key}. {value}\n"
            response_message += options_text
        
        return response_message
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return "An error occurred while generating the response. Please try again."

def replace_placeholders(template, context):
    """
    Replace placeholders in a template with actual data from context.
    
    Args:
        template (str): The template string with placeholders
        context (ConversationContext): The conversation context
        
    Returns:
        str: The template with placeholders replaced
    """
    try:
        # Get guest and stay information if available
        guest = None
        stay = None
        hotel = None
        
        guest_id = context.context_data.get('guest_id')
        stay_id = context.context_data.get('stay_id')
        hotel_id = context.hotel_id
        
        if guest_id:
            try:
                guest = Guest.objects.get(id=guest_id)
            except Guest.DoesNotExist:
                pass
        
        if stay_id:
            try:
                stay = Stay.objects.get(id=stay_id)
                hotel = stay.hotel
            except Stay.DoesNotExist:
                pass
        
        if hotel_id and not hotel:
            try:
                hotel = Hotel.objects.get(id=hotel_id)
            except Hotel.DoesNotExist:
                pass
        
        # Replace placeholders
        message = template
        
        # Guest placeholders
        if guest:
            message = message.replace('{guest_name}', guest.full_name or 'Guest')
            message = message.replace('{guest_email}', guest.email or '')
            message = message.replace('{guest_nationality}', guest.nationality or '')
        
        # Stay placeholders
        if stay:
            message = message.replace('{checkin_time}', stay.check_in_date.strftime('%d-%m-%Y %H:%M') if stay.check_in_date else '')
            message = message.replace('{checkout_time}', stay.check_out_date.strftime('%d-%m-%Y %H:%M') if stay.check_out_date else '')
            message = message.replace('{total_guests}', str(stay.number_of_guests))
            
            if stay.room:
                message = message.replace('{room_number}', stay.room.room_number or '')
        
        # Hotel placeholders
        if hotel:
            message = message.replace('{hotel_name}', hotel.name or '')
            message = message.replace('{wifi_password}', hotel.wifi_password or '')
        
        # Accumulated data placeholders
        accumulated_data = context.context_data.get('accumulated_data', {})
        for key, value in accumulated_data.items():
            placeholder = f'{{{key}}}'
            message = message.replace(placeholder, str(value))
        
        return message
    except Exception as e:
        logger.error(f"Error replacing placeholders: {str(e)}")
        return template

def transition_step(context, user_input, current_step_template, hotel_step_data):
    """
    Determine the next step based on user input and current step.
    
    Args:
        context (ConversationContext): The conversation context
        user_input (str): The user's input
        current_step_template (FlowStepTemplate): The current flow step template
        hotel_step_data (dict): Hotel-specific step data
        
    Returns:
        FlowStepTemplate: The next flow step template or None if conversation should end
    """
    try:
        # Check for conditional next steps first
        conditional_next_steps = hotel_step_data.get('conditional_next_steps', current_step_template.conditional_next_steps)
        if conditional_next_steps:
            for condition, next_step_template_id in conditional_next_steps.items():
                # Simple condition checking - in a real implementation, this would be more complex
                if condition == user_input or condition == '*':  # '*' means any input
                    try:
                        return FlowStepTemplate.objects.get(id=next_step_template_id)
                    except FlowStepTemplate.DoesNotExist:
                        logger.warning(f"Conditional next step template {next_step_template_id} does not exist")
        
        # Check for direct next step
        if current_step_template.next_step_template:
            return current_step_template.next_step_template
        
        # If no next step defined, conversation ends
        return None
    except Exception as e:
        logger.error(f"Error determining next step: {str(e)}")
        return None

def validate_input(context, user_input, step_template, hotel_step_data):
    """
    Validate user input against current step requirements.
    
    Args:
        context (ConversationContext): The conversation context
        user_input (str): The user's input
        step_template (FlowStepTemplate): The current flow step template
        hotel_step_data (dict): Hotel-specific step data
        
    Returns:
        dict: Validation result with 'valid' and 'message' keys
    """
    try:
        # Handle special commands
        if user_input in ['back', 'main menu']:
            return {'valid': True}
        
        # Check if step has options
        options = hotel_step_data.get('options', step_template.options)
        if options:
            # Check if input matches one of the options
            if user_input in options:
                return {'valid': True}
            else:
                # Generate error message with available options
                options_list = ', '.join([f"'{key}'" for key in options.keys()])
                return {
                    'valid': False,
                    'message': f"Please select a valid option: {options_list}"
                }
        
        # For steps without options, any input is valid
        return {'valid': True}
    except Exception as e:
        logger.error(f"Error validating input: {str(e)}")
        return {
            'valid': False,
            'message': 'An error occurred while validating your input. Please try again.'
        }

def handle_navigation(context, command):
    """
    Handle navigation commands (back, main menu).
    
    Args:
        context (ConversationContext): The conversation context
        command (str): The navigation command
        
    Returns:
        dict: Response with status and message
    """
    try:
        if command == 'main menu':
            # Reset to initial step and clear accumulated data
            context.context_data['accumulated_data'] = {}
            context.context_data['error_count'] = 0
            context.context_data['navigation_stack'] = []
            
            # For template-based system, we need to determine the initial flow
            # For now, we'll use a default approach
            initial_template = FlowStepTemplate.objects.first()
            if initial_template:
                context.context_data['current_step_template'] = initial_template.id
                context.context_data['navigation_stack'] = [initial_template.id]
                context.save()
                
                response_message = generate_response(context, initial_template)
                return {
                    'status': 'success',
                    'message': response_message
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Main menu is not available. Please start a new conversation.'
                }
        
        elif command == 'back':
            # Navigate back in the stack
            navigation_stack = context.context_data.get('navigation_stack', [])
            if len(navigation_stack) > 1:
                # Remove current step
                navigation_stack.pop()
                # Get previous step
                previous_step_template_id = navigation_stack[-1]
                context.context_data['navigation_stack'] = navigation_stack
                context.context_data['current_step_template'] = previous_step_template_id
                context.context_data['error_count'] = 0  # Reset error count
                context.save()
                
                # Get the previous step template
                try:
                    previous_step_template = FlowStepTemplate.objects.get(id=previous_step_template_id)
                    response_message = generate_response(context, previous_step_template)
                    return {
                        'status': 'success',
                        'message': response_message
                    }
                except FlowStepTemplate.DoesNotExist:
                    return {
                        'status': 'error',
                        'message': 'Unable to navigate back. Please try again.'
                    }
            else:
                # Already at the beginning, go to main menu
                return handle_navigation(context, 'main menu')
        
        return {
            'status': 'error',
            'message': 'Invalid navigation command.'
        }
    except Exception as e:
        logger.error(f"Error handling navigation: {str(e)}")
        return {
            'status': 'error',
            'message': 'An error occurred while processing your navigation request.'
        }

def update_accumulated_data(context, user_input, step_template):
    """
    Update accumulated data in context based on user input and current step.
    
    Args:
        context (ConversationContext): The conversation context
        user_input (str): The user's input
        step_template (FlowStepTemplate): The current flow step template
    """
    try:
        # Initialize accumulated_data if it doesn't exist
        if 'accumulated_data' not in context.context_data:
            context.context_data['accumulated_data'] = {}
        
        accumulated_data = context.context_data['accumulated_data']
        
        # Special handling for certain steps
        step_name = step_template.step_name
        
        # This is a simplified approach - in a real implementation, you might have
        # more sophisticated logic based on step names or other identifiers
        if 'checkin' in step_name.lower() and 'start' in step_name.lower():
            # Handle name confirmation
            if user_input == '1':  # Yes
                accumulated_data['name_confirmed'] = True
            elif user_input == '2':  # No
                accumulated_data['name_confirmed'] = False
        
        elif 'collect' in step_name.lower() and 'dob' in step_name.lower():
            # Store date of birth
            accumulated_data['date_of_birth'] = user_input
        
        elif 'upload' in step_name.lower() and 'document' in step_name.lower():
            # Mark document as uploaded
            accumulated_data['document_uploaded'] = True
        
        # Save updated context
        context.save()
    except Exception as e:
        logger.error(f"Error updating accumulated data: {str(e)}")