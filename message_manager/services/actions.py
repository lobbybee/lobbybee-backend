import logging
logger = logging.getLogger(__name__)

def validate_guest_name(conversation, message_content):
    logger.info(f"ACTION STUB: Validating guest name: {message_content}")
    # Store name in context
    conversation.context_data['guest_name'] = message_content
    conversation.save()
    return {"status": "success", "next_step": "collect_documents"}

def save_document(conversation, message_content):
    logger.info(f"ACTION STUB: Document upload for conversation {conversation.stay.id}")
    return {"status": "success", "next_step": "services_menu"}

def start_relay_to_department(conversation, department_type):
    from hotel.models import Department
    try:
        department = Department.objects.get(
            hotel=conversation.stay.hotel,
            department_type=department_type
        )
        conversation.status = 'relay'
        conversation.department = department
        conversation.save()

        # Trigger WebSocket notification to department
        from .websocket_utils import notify_department_new_conversation
        notify_department_new_conversation(conversation)

        return {"status": "success", "message": "Connecting you to our team..."}
    except Department.DoesNotExist:
        return {"status": "error", "message": "Service temporarily unavailable"}