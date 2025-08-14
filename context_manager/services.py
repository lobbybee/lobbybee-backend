from .models import ConversationContext, FlowStep
from guest.models import Guest, Stay
from hotel.models import Hotel
import logging
from datetime import datetime

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
        context.last_activity = datetime.now()
        context.save()
        
        # Handle navigation commands
        if user_message in ['back', 'main menu']:
            return handle_navigation(context, user_message)
        
        # Get current step
        current_step_id = context.context_data.get('current_step')
        if not current_step_id:
            logger.error(f"No current step found in context for {whatsapp_number}")
            return {
                'status': 'error',
                'message': 'Conversation state is invalid. Please start over.'
            }
        
        try:
            current_step = FlowStep.objects.get(step_id=current_step_id)
        except FlowStep.DoesNotExist:
            logger.error(f"FlowStep {current_step_id} does not exist")
            return {
                'status': 'error',
                'message': 'Conversation flow is invalid. Please start over.'
            }
        
        # Validate input
        validation_result = validate_input(context, user_message, current_step)
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
        update_accumulated_data(context, user_message, current_step)
        
        # Determine next step
        next_step = transition_step(context, user_message, current_step)
        
        if not next_step:
            # Conversation is ending
            context.is_active = False
            context.save()
            return {
                'status': 'success',
                'message': 'Thank you for your response. Conversation completed successfully.'
            }
        
        # Update context with next step
        context.context_data['current_step'] = next_step.step_id
        context.context_data['navigation_stack'].append(next_step.step_id)
        context.save()
        
        # Generate response for next step
        response_message = generate_response(context, next_step)
        
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

def get_flow_step(step_id):
    """
    Retrieve a flow step by its ID.
    
    Args:
        step_id (str): The step ID to retrieve
        
    Returns:
        FlowStep: The flow step or None if not found
    """
    try:
        return FlowStep.objects.get(step_id=step_id)
    except FlowStep.DoesNotExist:
        return None

def generate_response(context, flow_step):
    """
    Generate a response message for the current flow step.
    
    Args:
        context (ConversationContext): The conversation context
        flow_step (FlowStep): The current flow step
        
    Returns:
        str: The generated response message
    """
    try:
        # Start with the template message
        message_template = flow_step.message_template
        
        # Replace placeholders with actual data
        response_message = replace_placeholders(message_template, context)
        
        # Add options if they exist
        if flow_step.options:
            options_text = "\n"
            for key, value in flow_step.options.items():
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

def transition_step(context, user_input, current_step):
    """
    Determine the next step based on user input and current step.
    
    Args:
        context (ConversationContext): The conversation context
        user_input (str): The user's input
        current_step (FlowStep): The current flow step
        
    Returns:
        FlowStep: The next flow step or None if conversation should end
    """
    try:
        # Check for conditional next steps first
        if current_step.conditional_next_steps:
            for condition, next_step_id in current_step.conditional_next_steps.items():
                # Simple condition checking - in a real implementation, this would be more complex
                if condition == user_input or condition == '*':  # '*' means any input
                    try:
                        return FlowStep.objects.get(step_id=next_step_id)
                    except FlowStep.DoesNotExist:
                        logger.warning(f"Conditional next step {next_step_id} does not exist")
        
        # Check for direct next step
        if current_step.next_step:
            return current_step.next_step
        
        # If no next step defined, conversation ends
        return None
    except Exception as e:
        logger.error(f"Error determining next step: {str(e)}")
        return None

def validate_input(context, user_input, current_step):
    """
    Validate user input against current step requirements.
    
    Args:
        context (ConversationContext): The conversation context
        user_input (str): The user's input
        current_step (FlowStep): The current flow step
        
    Returns:
        dict: Validation result with 'valid' and 'message' keys
    """
    try:
        # Handle special commands
        if user_input in ['back', 'main menu']:
            return {'valid': True}
        
        # Check if step has options
        if current_step.options:
            # Check if input matches one of the options
            if user_input in current_step.options:
                return {'valid': True}
            else:
                # Generate error message with available options
                options_list = ', '.join([f"'{key}'" for key in current_step.options.keys()])
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
            # For now, we'll assume the initial step is 'main_menu' for general flows
            # But fallback to 'checkin_start' for checkin flows
            current_flow = context.context_data.get('current_flow', '')
            if 'checkin' in current_flow:
                initial_step_id = 'checkin_start'
            else:
                initial_step_id = 'main_menu'
            context.context_data['current_step'] = initial_step_id
            context.context_data['navigation_stack'] = [initial_step_id]
            context.save()
            
            # Get the initial step
            try:
                initial_step = FlowStep.objects.get(step_id=initial_step_id)
                response_message = generate_response(context, initial_step)
                return {
                    'status': 'success',
                    'message': response_message
                }
            except FlowStep.DoesNotExist:
                # Fallback to checkin_start if main_menu doesn't exist
                if initial_step_id == 'main_menu':
                    try:
                        initial_step = FlowStep.objects.get(step_id='checkin_start')
                        response_message = generate_response(context, initial_step)
                        return {
                            'status': 'success',
                            'message': response_message
                        }
                    except FlowStep.DoesNotExist:
                        return {
                            'status': 'error',
                            'message': 'Main menu is not available. Please start a new conversation.'
                        }
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
                previous_step_id = navigation_stack[-1]
                context.context_data['navigation_stack'] = navigation_stack
                context.context_data['current_step'] = previous_step_id
                context.context_data['error_count'] = 0  # Reset error count
                context.save()
                
                # Get the previous step
                try:
                    previous_step = FlowStep.objects.get(step_id=previous_step_id)
                    response_message = generate_response(context, previous_step)
                    return {
                        'status': 'success',
                        'message': response_message
                    }
                except FlowStep.DoesNotExist:
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

def update_accumulated_data(context, user_input, current_step):
    """
    Update accumulated data in context based on user input and current step.
    
    Args:
        context (ConversationContext): The conversation context
        user_input (str): The user's input
        current_step (FlowStep): The current flow step
    """
    try:
        # Initialize accumulated_data if it doesn't exist
        if 'accumulated_data' not in context.context_data:
            context.context_data['accumulated_data'] = {}
        
        accumulated_data = context.context_data['accumulated_data']
        
        # Special handling for certain steps
        step_id = current_step.step_id
        
        if step_id == 'checkin_start':
            # Handle name confirmation
            if user_input == '1':  # Yes
                accumulated_data['name_confirmed'] = True
            elif user_input == '2':  # No
                accumulated_data['name_confirmed'] = False
        
        elif step_id == 'checkin_collect_dob':
            # Store date of birth
            accumulated_data['date_of_birth'] = user_input
        
        elif step_id == 'checkin_upload_document_prompt':
            # Mark document as uploaded
            accumulated_data['document_uploaded'] = True
        
        # Save updated context
        context.save()
    except Exception as e:
        logger.error(f"Error updating accumulated data: {str(e)}")