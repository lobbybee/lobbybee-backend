from celery import shared_task
from django.utils import timezone
import logging
from datetime import datetime, timedelta, time
from .models import Stay
from chat.utils.whatsapp_utils import send_whatsapp_text_message, send_whatsapp_button_message

logger = logging.getLogger(__name__)

@shared_task
def send_extend_checkin_reminder(stay_id, is_test=False):
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

        # Guard against stale reminders after checkout extension:
        # only enforce the 4-hour window in normal mode (not test mode).
        if not stay.check_out_date:
            return {'status': 'skipped', 'reason': 'missing_checkout_date'}
        now = timezone.now()
        time_to_checkout = stay.check_out_date - now
        if time_to_checkout <= timedelta(seconds=0):
            return {'status': 'skipped', 'reason': 'checkout_passed'}
        if (not is_test) and time_to_checkout > timedelta(hours=4, minutes=15):
            return {'status': 'skipped', 'reason': 'stale_reminder_before_window'}
        
        # Get guest's WhatsApp number
        if not stay.guest.whatsapp_number:
            logger.warning(f"Guest {stay.guest.id} has no WhatsApp number")
            return {'status': 'error', 'reason': 'no_whatsapp_number'}
        
        checkout_time_text = stay.check_out_date.strftime('%H:%M') if stay.check_out_date else ''
        message = (
            f"Your checkout time is {checkout_time_text}. "
            "Would you like to extend your stay?"
        )

        buttons = [
            {
                "type": "reply",
                "reply": {"id": f"stay_extend_yes_{stay.id}", "title": "Yes, Extend"}
            },
            {
                "type": "reply",
                "reply": {"id": f"stay_extend_no_{stay.id}", "title": "No, Thanks"}
            }
        ]

        # Send WhatsApp interactive button message
        response = send_whatsapp_button_message(
            recipient_number=stay.guest.whatsapp_number,
            message_text=message,
            buttons=buttons
        )
        if not response:
            logger.error(
                f"Failed to send extension reminder button message for stay {stay_id} "
                f"(guest {stay.guest.whatsapp_number})"
            )
            return {'status': 'error', 'reason': 'whatsapp_send_failed', 'stay_id': stay_id}
        
        logger.info(f"Sent extension check-in reminder to guest {stay.guest.full_name} ({stay.guest.whatsapp_number})")
        
        return {
            'status': 'success',
            'message_type': 'extend_checkin',
            'guest_id': stay.guest.id,
            'stay_id': stay_id,
            'is_test': bool(is_test)
        }
        
    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error sending extension check-in reminder for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}

@shared_task
def schedule_checkin_reminder(stay_id, is_test=False):
    """
    Schedule extension check-in reminder for a new check-in
    
    Args:
        stay_id: The ID of the newly checked-in stay
    """
    try:
        # Get the stay to check hours_24 flag
        stay = Stay.objects.get(id=stay_id)

        if not stay.check_out_date:
            return {'status': 'error', 'reason': 'missing_checkout_date'}
        
        now = timezone.now()
        if is_test:
            countdown_seconds = 120
            scheduled_for = now + timedelta(seconds=countdown_seconds)
        else:
            # Schedule reminder around 4 hours before checkout.
            # If close to checkout, send quickly rather than skipping.
            reminder_time = stay.check_out_date - timedelta(hours=4)
            if reminder_time <= now:
                countdown_seconds = 60
                scheduled_for = now + timedelta(seconds=countdown_seconds)
            else:
                countdown_seconds = int((reminder_time - now).total_seconds())
                scheduled_for = reminder_time

        send_extend_checkin_reminder.apply_async(
            args=[stay_id, is_test],
            countdown=countdown_seconds,
            task_id=f"extend_reminder_{stay_id}_{timezone.now().timestamp()}"
        )

        logger.info(f"Scheduled extension reminder for stay {stay_id} at {scheduled_for}")

        return {
            'status': 'success',
            'stay_id': stay_id,
            'hours_24': stay.hours_24,
            'is_test': bool(is_test),
            'countdown_seconds': countdown_seconds,
            'scheduled_for': scheduled_for.isoformat() if hasattr(scheduled_for, 'isoformat') else str(scheduled_for)
        }
        
    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found when scheduling reminder")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error scheduling reminder for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}


# Backward-compatible semantic aliases for clarity.
send_checkout_extension_reminder = send_extend_checkin_reminder
schedule_checkout_extension_reminder = schedule_checkin_reminder


@shared_task
def send_breakfast_reminder(stay_id):
    """
    Send breakfast reminder message to guest

    Args:
        stay_id: The ID of the stay
    """
    try:
        # Get the stay object with related data
        stay = Stay.objects.select_related('guest', 'hotel').get(id=stay_id)

        # Verify stay is still active and breakfast reminder is enabled
        if stay.status != 'active':
            logger.info(f"Stay {stay_id} is no longer active (status: {stay.status}), skipping breakfast reminder")
            return {'status': 'skipped', 'reason': 'stay_not_active'}

        # Check if both hotel and stay breakfast reminders are enabled
        if not (stay.breakfast_reminder and stay.hotel.breakfast_reminder):
            logger.info(f"Breakfast reminder not enabled for stay {stay_id} (hotel: {stay.hotel.breakfast_reminder}, stay: {stay.breakfast_reminder})")
            return {'status': 'skipped', 'reason': 'breakfast_reminder_disabled'}

        # Get guest's WhatsApp number
        if not stay.guest.whatsapp_number:
            logger.warning(f"Guest {stay.guest.id} has no WhatsApp number")
            return {'status': 'error', 'reason': 'no_whatsapp_number'}

        # Prepare breakfast reminder message
        message = f"Good morning! ☀️ You have opted for breakfast with us at {stay.hotel.name}. This is a friendly reminder that breakfast is being served. We hope you have a wonderful day! 🍳"

        # Send WhatsApp message using existing utility
        send_whatsapp_text_message(
            recipient_number=stay.guest.whatsapp_number,
            message_text=message
        )

        logger.info(f"Sent breakfast reminder to guest {stay.guest.full_name} ({stay.guest.whatsapp_number})")

        return {
            'status': 'success',
            'message_type': 'breakfast_reminder',
            'guest_id': stay.guest.id,
            'stay_id': stay_id
        }

    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error sending breakfast reminder for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}


@shared_task
def send_dinner_reminder(stay_id):
    """
    Send dinner reminder message to guest

    Args:
        stay_id: The ID of the stay
    """
    try:
        # Get the stay object with related data
        stay = Stay.objects.select_related('guest', 'hotel').get(id=stay_id)

        # Verify stay is still active and dinner reminder is enabled
        if stay.status != 'active':
            logger.info(f"Stay {stay_id} is no longer active (status: {stay.status}), skipping dinner reminder")
            return {'status': 'skipped', 'reason': 'stay_not_active'}

        # Check if both hotel and stay dinner reminders are enabled
        if not (stay.dinner_reminder and stay.hotel.dinner_reminder):
            logger.info(f"Dinner reminder not enabled for stay {stay_id} (hotel: {stay.hotel.dinner_reminder}, stay: {stay.dinner_reminder})")
            return {'status': 'skipped', 'reason': 'dinner_reminder_disabled'}

        # Get guest's WhatsApp number
        if not stay.guest.whatsapp_number:
            logger.warning(f"Guest {stay.guest.id} has no WhatsApp number")
            return {'status': 'error', 'reason': 'no_whatsapp_number'}

        # Prepare dinner reminder message
        message = f"Good evening! 🌅 You have opted for dinner with us at {stay.hotel.name}. This is a friendly reminder that dinner is being served. Enjoy your meal! 🍽️"

        # Send WhatsApp message using existing utility
        send_whatsapp_text_message(
            recipient_number=stay.guest.whatsapp_number,
            message_text=message
        )

        logger.info(f"Sent dinner reminder to guest {stay.guest.full_name} ({stay.guest.whatsapp_number})")

        return {
            'status': 'success',
            'message_type': 'dinner_reminder',
            'guest_id': stay.guest.id,
            'stay_id': stay_id
        }

    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error sending dinner reminder for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}


@shared_task
def schedule_meal_reminders(stay_id):
    """
    Schedule breakfast and dinner reminders for a new check-in

    Args:
        stay_id: The ID of the newly checked-in stay
    """
    try:
        # Get the stay object
        stay = Stay.objects.select_related('hotel').get(id=stay_id)

        # Check if stay has checkout date
        if not stay.check_out_date:
            logger.warning(f"Stay {stay_id} has no checkout date")
            return {'status': 'error', 'reason': 'no_checkout_date'}

        # Calculate duration of stay in days
        now = timezone.now()
        checkout_datetime = stay.check_out_date
        duration = checkout_datetime - now
        days = max(1, int(duration.days))

        # Schedule breakfast reminders at 6 AM every day until checkout
        if stay.breakfast_reminder and stay.hotel.breakfast_reminder:
            for day in range(days):
                # Calculate next 6 AM time
                reminder_date = now + timedelta(days=day)
                reminder_time = reminder_date.replace(hour=6, minute=0, second=0, microsecond=0)

                # If reminder time has passed today, schedule for tomorrow
                if reminder_time <= now:
                    reminder_time = reminder_time + timedelta(days=1)

                # Calculate countdown in seconds
                countdown_seconds = (reminder_time - now).total_seconds()

                # Only schedule if before checkout
                if reminder_time < checkout_datetime:
                    send_breakfast_reminder.apply_async(
                        args=[stay_id],
                        countdown=countdown_seconds,
                        task_id=f"breakfast_reminder_{stay_id}_{day}_{timezone.now().timestamp()}"
                    )
                    logger.info(f"Scheduled breakfast reminder for stay {stay_id} at {reminder_time}")

        # Schedule dinner reminders at 3 PM every day until checkout
        if stay.dinner_reminder and stay.hotel.dinner_reminder:
            for day in range(days):
                # Calculate next 3 PM time
                reminder_date = now + timedelta(days=day)
                reminder_time = reminder_date.replace(hour=15, minute=0, second=0, microsecond=0)

                # If reminder time has passed today, schedule for tomorrow
                if reminder_time <= now:
                    reminder_time = reminder_time + timedelta(days=1)

                # Calculate countdown in seconds
                countdown_seconds = (reminder_time - now).total_seconds()

                # Only schedule if before checkout
                if reminder_time < checkout_datetime:
                    send_dinner_reminder.apply_async(
                        args=[stay_id],
                        countdown=countdown_seconds,
                        task_id=f"dinner_reminder_{stay_id}_{day}_{timezone.now().timestamp()}"
                    )
                    logger.info(f"Scheduled dinner reminder for stay {stay_id} at {reminder_time}")

        return {
            'status': 'success',
            'stay_id': stay_id,
            'days': days,
            'breakfast_enabled': bool(stay.breakfast_reminder and stay.hotel.breakfast_reminder),
            'dinner_enabled': bool(stay.dinner_reminder and stay.hotel.dinner_reminder)
        }

    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found when scheduling meal reminders")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error scheduling meal reminders for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}
