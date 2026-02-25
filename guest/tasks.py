from celery import shared_task
from django.utils import timezone
import logging
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .models import Stay
from chat.utils.whatsapp_utils import send_whatsapp_text_message, send_whatsapp_button_message

logger = logging.getLogger(__name__)


def _get_hotel_tz(hotel):
    try:
        return ZoneInfo(hotel.time_zone or 'UTC')
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning(f"Invalid timezone '{hotel.time_zone}' for hotel {hotel.id}, using UTC")
        return ZoneInfo('UTC')


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_extend_checkin_reminder(self, stay_id, is_test=False):
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

        hotel_tz = _get_hotel_tz(stay.hotel)
        checkout_time_text = stay.check_out_date.astimezone(hotel_tz).strftime('%d %b %Y, %H:%M') if stay.check_out_date else ''
        guest_name = stay.guest.full_name or 'Guest'
        room_number = stay.room.room_number if stay.room else 'N/A'
        message = (
            f"Dear {guest_name},\n\n"
            f"Your check-out time for Room No {room_number} is today at {checkout_time_text}.\n"
            f"Please settle the bills and return your room keys on time to avoid any additional charges.\n\n"
            f"If you like to continue your stay, Please contact Reception immediately to check availability.\n\n"
            f"Have a great day!!"
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

        task_id = f"extend_reminder_{stay_id}"
        send_extend_checkin_reminder.apply_async(
            args=[stay_id, is_test],
            countdown=countdown_seconds,
            task_id=task_id
        )

        logger.info(f"Scheduled extension reminder for stay {stay_id} at {scheduled_for} (task_id={task_id})")

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


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_breakfast_reminder(self, stay_id):
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


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_dinner_reminder(self, stay_id):
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


@shared_task
def schedule_meal_reminders(stay_id):
    """
    Schedule breakfast and dinner reminders for a new check-in.
    All time calculations are done in the hotel's local timezone.

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

        hotel_tz = _get_hotel_tz(stay.hotel)
        now = timezone.now()
        now_local = now.astimezone(hotel_tz)
        checkout_datetime = stay.check_out_date
        checkout_local = checkout_datetime.astimezone(hotel_tz)

        breakfast_scheduled = 0
        dinner_scheduled = 0

        # Schedule breakfast reminders at 6 AM hotel-local every day until checkout
        if stay.breakfast_reminder and stay.hotel.breakfast_reminder:
            candidate = now_local.replace(hour=6, minute=0, second=0, microsecond=0)
            if candidate <= now_local:
                candidate += timedelta(days=1)
            while candidate < checkout_local:
                countdown = int((candidate - now).total_seconds())
                if countdown > 0:
                    task_id = f"breakfast_reminder_{stay_id}_{candidate.strftime('%Y%m%d')}"
                    send_breakfast_reminder.apply_async(
                        args=[stay_id],
                        countdown=countdown,
                        task_id=task_id
                    )
                    logger.info(f"Scheduled breakfast reminder for stay {stay_id} at {candidate} (task_id={task_id})")
                    breakfast_scheduled += 1
                candidate += timedelta(days=1)

        # Schedule dinner reminders at 3 PM hotel-local every day until checkout
        if stay.dinner_reminder and stay.hotel.dinner_reminder:
            candidate = now_local.replace(hour=15, minute=0, second=0, microsecond=0)
            if candidate <= now_local:
                candidate += timedelta(days=1)
            while candidate < checkout_local:
                countdown = int((candidate - now).total_seconds())
                if countdown > 0:
                    task_id = f"dinner_reminder_{stay_id}_{candidate.strftime('%Y%m%d')}"
                    send_dinner_reminder.apply_async(
                        args=[stay_id],
                        countdown=countdown,
                        task_id=task_id
                    )
                    logger.info(f"Scheduled dinner reminder for stay {stay_id} at {candidate} (task_id={task_id})")
                    dinner_scheduled += 1
                candidate += timedelta(days=1)

        return {
            'status': 'success',
            'stay_id': stay_id,
            'breakfast_scheduled': breakfast_scheduled,
            'dinner_scheduled': dinner_scheduled,
            'breakfast_enabled': bool(stay.breakfast_reminder and stay.hotel.breakfast_reminder),
            'dinner_enabled': bool(stay.dinner_reminder and stay.hotel.dinner_reminder)
        }

    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found when scheduling meal reminders")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error scheduling meal reminders for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}
