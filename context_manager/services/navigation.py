from ..models import FlowStep
from .context import log_conversation_message
from .flow import start_flow
from .message import generate_response, format_message


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

        context.navigation_stack.pop()  # Pop the current step

        previous_step_id = context.navigation_stack[-1]
        try:
            previous_step = FlowStep.objects.get(id=previous_step_id)
            context.current_step = previous_step
            context.error_count = 0
            context.save()

            response_message = generate_response(context)
            log_conversation_message(context, response_message, is_from_guest=False)
            return {'status': 'success', 'messages': [format_message(response_message)]}
        except FlowStep.DoesNotExist:
            return reset_context_to_main_menu(context, 'Could not navigate back. Returning to main menu.')


def reset_context_to_main_menu(context, message):
    """
    Resets the context to the main menu flow.
    """
    context.context_data['accumulated_data'] = {}
    context.error_count = 0
    context.save()
    # We pass the context and the category, start_flow handles the rest
    # Aligning with seed.sql: 'random_guest' acts as the main menu/discovery flow
    response = start_flow(context, 'random_guest')
    # Prepend the reason for the reset to the response message
    original_messages = response.get('messages', [])
    response['messages'] = [format_message(message)] + original_messages
    return response