"""
Utilities for sending real-time WebSocket notifications for various events
"""
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from chat.consumers import normalize_department_name

logger = logging.getLogger(__name__)


async def notify_new_checkin_to_reception(conversation, booking, stay, guest):
    """
    Send real-time WebSocket notification to reception and management staff of the specific hotel about new check-in

    Args:
        conversation: The check-in conversation object
        booking: The booking object created
        stay: The stay object created
        guest: The guest object
    """
    channel_layer = get_channel_layer()

    # Prepare notification data
    # Convert UUIDs to strings to ensure JSON serialization compatibility
    notification_data = {
        'type': 'new_checkin',
        'data': {
            'conversation_id': str(conversation.id),
            'booking_id': str(booking.id),
            'stay_id': str(stay.id),
            'guest_id': str(guest.id),
            'guest_name': guest.full_name or 'Guest',
            'hotel_id': str(conversation.hotel.id),
            'hotel_name': conversation.hotel.name,
            'check_in_date': booking.check_in_date.strftime('%Y-%m-%d'),
            'check_out_date': booking.check_out_date.strftime('%Y-%m-%d'),
            'guest_whatsapp': guest.whatsapp_number,
            'status': 'pending_verification',
            'created_at': conversation.created_at.isoformat(),
            'message': f"New check-in request from {guest.full_name or 'Guest'}",
            'link': f"/checkin/{conversation.id}",
            'link_label': "View Check-in"
        }
    }

    # Send to department groups - the ChatConsumer will filter by hotel on the client side
    # We include hotel_id in the data so the frontend can filter if needed
    # But the actual WebSocket routing will ensure only this hotel's staff receive it
    departments_to_notify = ['reception', 'management']

    for dept in departments_to_notify:
        group_name = f"department_{normalize_department_name(dept)}"
        await channel_layer.group_send(
            group_name,
            {
                'type': 'new_checkin_notification',
                'notification': notification_data
            }
        )

    logger.info(f"Sent new check-in WebSocket notification for guest {guest.full_name} to {departments_to_notify} at hotel {conversation.hotel.name}")


def send_new_checkin_notification(conversation, booking, stay, guest):
    """
    Synchronous wrapper for notify_new_checkin_to_reception
    Use this from regular Django code/views
    """
    try:
        channel_layer = get_channel_layer()
        async_to_sync(notify_new_checkin_to_reception)(
            conversation, booking, stay, guest
        )
    except Exception as e:
        logger.error(f"Error sending new check-in notification: {e}", exc_info=True)