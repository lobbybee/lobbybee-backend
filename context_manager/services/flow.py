import logging

from ..models import FlowStep, FlowStepTemplate, FlowTemplate
from .context import log_conversation_message
from .message import generate_response

logger = logging.getLogger(__name__)


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
