from ..models import FlowStep
from .context import log_conversation_message
from .flow import start_flow
from .message import generate_response


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
