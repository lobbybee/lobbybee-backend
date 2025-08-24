import logging

from ..models import FlowStep, FlowStepTemplate, FlowTemplate
from .context import log_conversation_message
from .message import generate_response, format_message
# Import the checkin finalizer
from .checkin_finalizer import finalize_checkin

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
        return {'status': 'success', 'messages': [format_message(response_message)]}

    except FlowTemplate.DoesNotExist as e:
        logger.error(str(e))
        return {'status': 'error', 'messages': [format_message('This service is currently unavailable.')]}
    except FlowStepTemplate.DoesNotExist as e:
        logger.error(str(e))
        return {'status': 'error', 'messages': [format_message('This service is not configured correctly.')]}


def transition_to_next_step(context, user_input):
    """
    Determines the next step, updates the context, and returns the new step.
    Checks if the next step is the end of the check-in flow and finalizes check-in if so.
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
        
        # Check if this transition leads to the end of the check-in flow
        # This is a simplification. A more robust way is to check if next_step.template
        # is the 'Checkin Success' step or has no further transitions.
        # For now, let's assume the 'Checkin Success' step is the one that signifies completion.
        # We can identify it by its name or a specific flag if added to the template.
        # Let's check by step name for now.
        if next_step.template.step_name == 'Checkin Success':
             # Finalize the check-in process
             guest = finalize_checkin(context)
             logger.info(f"Check-in finalized for guest: {guest}")
        
        # --- Check-in Finalization Logic ---
        # Check if the current flow is 'hotel_checkin' and the next step is the end (None)
        # This assumes the 'Checkin Success' step is the last one in the 'hotel_checkin' flow.
        # A more robust way might be to check the specific step name or a flag on the step template.
        if (current_step.template.flow_template.category == 'hotel_checkin' and 
            next_step.template.flow_template.category != 'hotel_checkin'):
            # The next step belongs to a different flow, implying the check-in flow has ended successfully.
            logger.info("Check-in flow completed. Finalizing guest creation/update.")
            try:
                guest = finalize_checkin(context)
                if guest:
                    logger.info(f"Guest {guest} successfully finalized.")
                else:
                    logger.warning("Check-in finalization did not create/update a guest.")
            except Exception as e:
                logger.error(f"Error during check-in finalization: {e}", exc_info=True)
                # Depending on requirements, you might want to halt the transition or continue
                # For now, we'll log the error and continue the transition.
        
        return next_step

    # --- Check-in Finalization Logic (Alternative) ---
    # If next_step_template is None (end of flow) and the current flow was check-in
    elif current_step.template.flow_template.category == 'hotel_checkin':
         # This case handles if the check-in flow simply ends without transitioning to another flow.
         # The 'Checkin Success' step itself might be the last one.
         logger.info("Check-in flow ended. Finalizing guest creation/update.")
         try:
             guest = finalize_checkin(context)
             if guest:
                 logger.info(f"Guest {guest} successfully finalized.")
             else:
                 logger.warning("Check-in finalization did not create/update a guest.")
         except Exception as e:
             logger.error(f"Error during check-in finalization: {e}", exc_info=True)
             
    return None # End of flow
