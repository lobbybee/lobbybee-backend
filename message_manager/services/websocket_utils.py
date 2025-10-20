from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from user.models import User


def notify_department_new_conversation(conversation):
    """Send WebSocket notification to staff when a new conversation is created.
    
    This function sends a notification to all active staff members
    that a new conversation has been initiated and requires their attention.
    """
    # Get the channel layer
    channel_layer = get_channel_layer()
    
    # Get all active staff members
    staff_users = User.objects.filter(
        is_active=True
    )
    
    # Only notify if conversation has a stay (skip demo conversations)
    if not conversation.stay:
        return
    
    # Send notification to each staff member
    for staff_user in staff_users:
        async_to_sync(channel_layer.group_send)(
            f"staff_{staff_user.id}",
            {
                "type": "new_conversation",
                "stay_id": str(conversation.stay.id),
                "conversation_id": str(conversation.id),
                "message": f"New conversation initiated",
                "timestamp": conversation.created_at.isoformat()
            }
        )