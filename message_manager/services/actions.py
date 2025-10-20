import logging
logger = logging.getLogger(__name__)

def validate_guest_name(conversation, message_content):
    logger.info(f"ACTION STUB: Validating guest name: {message_content}")
    # Store name in context
    conversation.context_data['guest_name'] = message_content
    try:
        conversation.save()
    except Exception as e:
        logger.error(f"Error saving conversation in validate_guest_name: {str(e)}")
    return {"status": "success", "next_step": "collect_documents"}

def save_document(conversation, message_content):
    if conversation.stay:
        logger.info(f"ACTION STUB: Document upload for conversation {conversation.stay.id}")
    else:
        logger.info(f"ACTION STUB: Document upload for demo conversation {conversation.id}")
    return {"status": "success", "next_step": "services_menu"}

def start_relay_to_department(conversation, message_content, department_type=None):
    try:
        conversation.status = 'relay'
        conversation.department = department_type  # Store the department
        try:
            conversation.save()
        except Exception as e:
            logger.error(f"Error saving conversation in start_relay_to_department: {str(e)}")

        # Trigger WebSocket notification to department
        from .websocket_utils import notify_department_new_conversation
        notify_department_new_conversation(conversation)

        return {"status": "success", "message": "Connecting you to our team..."}
    except Exception as e:
        logger.error(f"Error starting relay: {str(e)}")
        return {"status": "error", "message": "Service temporarily unavailable"}
