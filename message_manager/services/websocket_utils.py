from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from hotel.models import Department


def notify_department_new_conversation(conversation):
    """Send WebSocket notification to department when a new conversation is created.
    
    This function sends a notification to all staff members in the department
    that a new conversation has been initiated and requires their attention.
    """
    if not conversation.department:
        return
        
    # Get the channel layer
    channel_layer = get_channel_layer()
    
    # Get all staff members in the department
    department_staff = Department.objects.filter(
        id=conversation.department.id
    ).first()
    
    if department_staff:
        # Send notification to department group
        async_to_sync(channel_layer.group_send)(
            f"department_{conversation.department.id}",
            {
                "type": "new_conversation",
                "stay_id": str(conversation.stay.id) if conversation.stay else None,
                "conversation_id": str(conversation.id),
                "message": "New conversation initiated",
                "timestamp": conversation.created_at.isoformat()
            }
        )