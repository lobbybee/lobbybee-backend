from celery import shared_task
from django.utils import timezone
import logging
from .models import Stay
from chat.utils.whatsapp_utils import send_whatsapp_text_message

logger = logging.getLogger(__name__)

@shared_task
def send_extend_checkin_reminder(stay_id):
    """
    Send extension check-in reminder message to guest
    
    Args:
        stay_id: The ID of the stay
    """
    try:
        # Get the stay object with related data
        stay = Stay.objects.select_related('guest', 'hotel').get(id=stay_id)
        
        # Verify stay is still active (not checked out)
        if stay.status != 'active':
            logger.info(f"Stay {stay_id} is no longer active (status: {stay.status}), skipping message")
            return {'status': 'skipped', 'reason': 'stay_not_active'}
        
        # Get guest's WhatsApp number
        if not stay.guest.whatsapp_number:
            logger.warning(f"Guest {stay.guest.id} has no WhatsApp number")
            return {'status': 'error', 'reason': 'no_whatsapp_number'}
        
        # Prepare extension check-in message
        message = "would you like to extend checkin?"
        
        # Send WhatsApp message using existing utility
        send_whatsapp_text_message(
            recipient_number=stay.guest.whatsapp_number,
            message_text=message
        )
        
        logger.info(f"Sent extension check-in reminder to guest {stay.guest.full_name} ({stay.guest.whatsapp_number})")
        
        return {
            'status': 'success',
            'message_type': 'extend_checkin',
            'guest_id': stay.guest.id,
            'stay_id': stay_id
        }
        
    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error sending extension check-in reminder for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}

@shared_task
def schedule_checkin_reminder(stay_id):
    """
    Schedule extension check-in reminder for a new check-in
    
    Args:
        stay_id: The ID of the newly checked-in stay
    """
    try:
        # Get the stay to check hours_24 flag
        stay = Stay.objects.get(id=stay_id)
        
        # Schedule extend check-in message based on hours_24
        # 11 hours for 12-hour stay, 23 hours for 24-hour stay
        countdown_hours = 23 if stay.hours_24 else 11
        countdown_seconds = countdown_hours * 3600
        
        send_extend_checkin_reminder.apply_async(
            args=[stay_id],
            countdown=countdown_seconds,
            task_id=f"extend_reminder_{stay_id}_{timezone.now().timestamp()}"
        )
        
        logger.info(f"Scheduled extension reminder for stay {stay_id} in {countdown_hours} hours")
        
        return {
            'status': 'success',
            'stay_id': stay_id,
            'hours_24': stay.hours_24,
            'countdown_hours': countdown_hours,
            'countdown_seconds': countdown_seconds
        }
        
    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found when scheduling reminder")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error scheduling reminder for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}