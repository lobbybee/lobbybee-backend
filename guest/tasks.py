from celery import shared_task
from django.db import IntegrityError, transaction
from django.utils import timezone
import logging
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import ReminderLog, Stay
from .name_utils import get_first_name_from_full_name
from chat.utils.whatsapp_utils import send_whatsapp_button_message, send_whatsapp_text_message

logger = logging.getLogger(__name__)


def _get_hotel_tz(hotel):
    try:
        return ZoneInfo(hotel.time_zone or 'UTC')
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning(f"Invalid timezone '{hotel.time_zone}' for hotel {hotel.id}, using UTC")
        return ZoneInfo('UTC')


def _checkout_reminder_date(stay):
    hotel_tz = _get_hotel_tz(stay.hotel)
    return stay.check_out_date.astimezone(hotel_tz).date() if stay.check_out_date else timezone.now().astimezone(hotel_tz).date()


def _resolve_reminder_date(stay, reminder_type, reminder_date_str=None):
    if reminder_date_str:
        try:
            return date.fromisoformat(str(reminder_date_str))
        except ValueError:
            logger.warning(
                "Invalid reminder_date '%s' for stay_id=%s reminder_type=%s",
                reminder_date_str,
                stay.id,
                reminder_type,
            )

    if reminder_type == 'checkout':
        return _checkout_reminder_date(stay)

    hotel_tz = _get_hotel_tz(stay.hotel)
    return timezone.now().astimezone(hotel_tz).date()


def _guest_scope_logs(stay, reminder_type, reminder_date):
    """
    Guest-level dedupe scope: one reminder per guest + hotel + type + date.
    """
    return ReminderLog.objects.filter(
        stay__guest_id=stay.guest_id,
        stay__hotel_id=stay.hotel_id,
        reminder_type=reminder_type,
        reminder_date=reminder_date,
    )


def _upsert_reminder_log(
    stay,
    reminder_type,
    reminder_date,
    *,
    status=None,
    reason=None,
    is_test=None,
    scheduled_for=None,
    task_id=None,
    sent_at=None,
    metadata=None,
):
    log_defaults = {}
    if status is not None:
        log_defaults['status'] = status
    if reason is not None:
        log_defaults['reason'] = reason
    if is_test is not None:
        log_defaults['is_test'] = bool(is_test)
    if scheduled_for is not None:
        log_defaults['scheduled_for'] = scheduled_for
    if task_id is not None:
        log_defaults['task_id'] = task_id
    if sent_at is not None:
        log_defaults['sent_at'] = sent_at
    if metadata is not None:
        log_defaults['metadata'] = metadata

    try:
        log, _ = ReminderLog.objects.get_or_create(
            stay=stay,
            reminder_type=reminder_type,
            reminder_date=reminder_date,
            defaults=log_defaults,
        )
    except IntegrityError:
        log = ReminderLog.objects.get(
            stay=stay,
            reminder_type=reminder_type,
            reminder_date=reminder_date,
        )

    update_fields = []
    for field, value in log_defaults.items():
        if getattr(log, field) != value:
            setattr(log, field, value)
            update_fields.append(field)

    if update_fields:
        update_fields.append('updated_at')
        log.save(update_fields=update_fields)

    _log_reminder_event(
        stay_id=stay.id,
        reminder_type=reminder_type,
        reminder_date=reminder_date,
        task_id=task_id or log.task_id,
        status=log.status,
        reason=log.reason,
    )
    return log


def _get_locked_log(stay, reminder_type, reminder_date, is_test=False):
    try:
        return ReminderLog.objects.select_for_update().get(
            stay=stay,
            reminder_type=reminder_type,
            reminder_date=reminder_date,
        )
    except ReminderLog.DoesNotExist:
        try:
            return ReminderLog.objects.create(
                stay=stay,
                reminder_type=reminder_type,
                reminder_date=reminder_date,
                status='scheduled',
                is_test=bool(is_test),
            )
        except IntegrityError:
            return ReminderLog.objects.select_for_update().get(
                stay=stay,
                reminder_type=reminder_type,
                reminder_date=reminder_date,
            )


def _set_log_status(log, *, status, reason=None, is_test=None, sent_at=None, metadata=None):
    update_fields = []

    if log.status != status:
        log.status = status
        update_fields.append('status')

    if reason != log.reason:
        log.reason = reason
        update_fields.append('reason')

    if is_test is not None and log.is_test != bool(is_test):
        log.is_test = bool(is_test)
        update_fields.append('is_test')

    if sent_at is not None and log.sent_at != sent_at:
        log.sent_at = sent_at
        update_fields.append('sent_at')

    if metadata is not None and log.metadata != metadata:
        log.metadata = metadata
        update_fields.append('metadata')

    if update_fields:
        update_fields.append('updated_at')
        log.save(update_fields=update_fields)

    _log_reminder_event(
        stay_id=log.stay_id,
        reminder_type=log.reminder_type,
        reminder_date=log.reminder_date,
        task_id=log.task_id,
        status=log.status,
        reason=log.reason,
    )


def _log_already_sent(log):
    _log_reminder_event(
        stay_id=log.stay_id,
        reminder_type=log.reminder_type,
        reminder_date=log.reminder_date,
        task_id=log.task_id,
        status=log.status,
        reason='already_sent',
    )


def _log_reminder_event(*, stay_id, reminder_type, reminder_date, task_id, status, reason):
    logger.info(
        "reminder_event stay_id=%s reminder_type=%s reminder_date=%s task_id=%s status=%s reason=%s",
        stay_id,
        reminder_type,
        reminder_date,
        task_id,
        status,
        reason,
    )


def _build_meal_message(stay, reminder_type):
    if reminder_type == 'breakfast':
        return (
            f"Good morning! ☀️ You have opted for breakfast with us at {stay.hotel.name}. "
            "This is a friendly reminder that breakfast is being served. We hope you have a wonderful day! 🍳"
        )
    if reminder_type == 'lunch':
        return (
            f"Good afternoon! ☀️ You have opted for lunch with us at {stay.hotel.name}. "
            "This is a friendly reminder that lunch is being served. Enjoy your meal! 🍽️"
        )
    return (
        f"Good evening! 🌅 You have opted for dinner with us at {stay.hotel.name}. "
        "This is a friendly reminder that dinner is being served. Enjoy your meal! 🍽️"
    )


def _format_checkout_time_for_guest(stay, hotel_tz):
    """
    Format checkout time in hotel-local timezone for guest-facing reminder copy.
    """
    if not stay.check_out_date:
        return ""
    checkout_local = stay.check_out_date.astimezone(hotel_tz)
    return checkout_local.strftime('%d %b %Y, %I:%M %p')


def _is_meal_enabled(stay, reminder_type):
    if reminder_type == 'breakfast':
        return stay.breakfast_reminder and stay.hotel.breakfast_reminder
    if reminder_type == 'lunch':
        return stay.lunch_reminder
    if reminder_type == 'dinner':
        return stay.dinner_reminder and stay.hotel.dinner_reminder
    return False


def _send_meal_reminder(reminder_type, stay_id, reminder_date_str=None):
    stay = None
    reminder_date = None
    log = None

    try:
        stay = Stay.objects.select_related('guest', 'hotel').get(id=stay_id)
        reminder_date = _resolve_reminder_date(stay, reminder_type, reminder_date_str)
        with transaction.atomic():
            log = _get_locked_log(stay, reminder_type, reminder_date)

            if log.status == 'sent':
                _log_already_sent(log)
                return {'status': 'skipped', 'reason': 'already_sent'}

            if _guest_scope_logs(stay, reminder_type, reminder_date).exclude(id=log.id).filter(status='sent').exists():
                _set_log_status(log, status='skipped', reason='already_sent_for_guest')
                return {'status': 'skipped', 'reason': 'already_sent_for_guest'}

            if stay.status != 'active':
                _set_log_status(log, status='skipped', reason='stay_not_active')
                return {'status': 'skipped', 'reason': 'stay_not_active'}

            if not _is_meal_enabled(stay, reminder_type):
                _set_log_status(log, status='skipped', reason=f'{reminder_type}_reminder_disabled')
                return {'status': 'skipped', 'reason': f'{reminder_type}_reminder_disabled'}

            if not stay.guest.whatsapp_number:
                _set_log_status(log, status='failed', reason='no_whatsapp_number')
                logger.warning(f"Guest {stay.guest.id} has no WhatsApp number")
                return {'status': 'error', 'reason': 'no_whatsapp_number'}

            send_whatsapp_text_message(
                recipient_number=stay.guest.whatsapp_number,
                message_text=_build_meal_message(stay, reminder_type),
            )

            _set_log_status(log, status='sent', reason=None, sent_at=timezone.now())

        logger.info(
            "Sent %s reminder to guest %s (%s)",
            reminder_type,
            stay.guest.full_name,
            stay.guest.whatsapp_number,
        )

        return {
            'status': 'success',
            'message_type': f'{reminder_type}_reminder',
            'guest_id': stay.guest.id,
            'stay_id': stay_id,
            'reminder_date': reminder_date.isoformat(),
        }

    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(
            "Error sending %s reminder for stay %s: %s",
            reminder_type,
            stay_id,
            str(e),
            exc_info=True,
        )
        if log is not None:
            _set_log_status(log, status='failed', reason='whatsapp_send_failed')
        elif stay is not None and reminder_date is not None:
            _upsert_reminder_log(
                stay,
                reminder_type,
                reminder_date,
                status='failed',
                reason='whatsapp_send_failed',
                metadata={'source': 'send_meal_reminder_exception'},
            )
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_extend_checkin_reminder(self, stay_id, is_test=False, reminder_date=None):
    """
    Send extension check-in reminder message to guest.

    Args:
        stay_id: The ID of the stay
        is_test: Bypasses stale reminder guard when true
        reminder_date: Hotel-local date associated with this reminder
    """
    try:
        stay = Stay.objects.select_related('guest', 'hotel', 'room').get(id=stay_id)
        resolved_reminder_date = _resolve_reminder_date(stay, 'checkout', reminder_date)
        with transaction.atomic():
            log = _get_locked_log(stay, 'checkout', resolved_reminder_date, is_test=is_test)

            if log.status == 'sent':
                _log_already_sent(log)
                return {'status': 'skipped', 'reason': 'already_sent'}

            if _guest_scope_logs(stay, 'checkout', resolved_reminder_date).exclude(id=log.id).filter(status='sent').exists():
                _set_log_status(log, status='skipped', reason='already_sent_for_guest', is_test=is_test)
                return {'status': 'skipped', 'reason': 'already_sent_for_guest'}

            if stay.status != 'active':
                _set_log_status(log, status='skipped', reason='stay_not_active', is_test=is_test)
                return {'status': 'skipped', 'reason': 'stay_not_active'}

            if not stay.check_out_date:
                _set_log_status(log, status='skipped', reason='missing_checkout_date', is_test=is_test)
                return {'status': 'skipped', 'reason': 'missing_checkout_date'}

            now = timezone.now()
            time_to_checkout = stay.check_out_date - now
            if time_to_checkout <= timedelta(seconds=0):
                _set_log_status(log, status='skipped', reason='checkout_passed', is_test=is_test)
                return {'status': 'skipped', 'reason': 'checkout_passed'}

            if (not is_test) and time_to_checkout > timedelta(hours=4, minutes=15):
                _set_log_status(log, status='skipped', reason='stale_reminder_before_window', is_test=is_test)
                return {'status': 'skipped', 'reason': 'stale_reminder_before_window'}

            if not stay.guest.whatsapp_number:
                _set_log_status(log, status='failed', reason='no_whatsapp_number', is_test=is_test)
                logger.warning(f"Guest {stay.guest.id} has no WhatsApp number")
                return {'status': 'error', 'reason': 'no_whatsapp_number'}

            hotel_tz = _get_hotel_tz(stay.hotel)
            checkout_time_text = _format_checkout_time_for_guest(stay, hotel_tz)
            guest_name = get_first_name_from_full_name(stay.guest.full_name)
            active_room_numbers = list(
                Stay.objects.filter(
                    guest=stay.guest,
                    hotel=stay.hotel,
                    status='active',
                    room__isnull=False
                ).values_list('room__room_number', flat=True).distinct()
            )
            if active_room_numbers:
                active_room_numbers = sorted(str(room_no) for room_no in active_room_numbers)
                room_numbers_text = ', '.join(active_room_numbers)
            else:
                room_numbers_text = stay.room.room_number if stay.room else 'N/A'
            message = (
                f"Dear {guest_name},\n\n"
                f"Your check-out time for Room No(s) {room_numbers_text} is {checkout_time_text}.\n"
                "Please settle the bills and return your room keys on time to avoid any additional charges.\n\n"
                "If you like to continue your stay, Please contact Reception immediately to check availability.\n\n"
                "Have a great day!!"
            )

            buttons = [
                {
                    "type": "reply",
                    "reply": {"id": f"stay_extend_yes_{stay.id}", "title": "Yes, Extend"},
                },
                {
                    "type": "reply",
                    "reply": {"id": f"stay_extend_no_{stay.id}", "title": "No, Thanks"},
                },
            ]

            response = send_whatsapp_button_message(
                recipient_number=stay.guest.whatsapp_number,
                message_text=message,
                buttons=buttons,
            )
            if not response:
                _set_log_status(log, status='failed', reason='whatsapp_send_failed', is_test=is_test)
                logger.error(
                    "Failed to send extension reminder button message for stay %s (guest %s)",
                    stay_id,
                    stay.guest.whatsapp_number,
                )
                return {'status': 'error', 'reason': 'whatsapp_send_failed', 'stay_id': stay_id}

            _set_log_status(log, status='sent', reason=None, is_test=is_test, sent_at=timezone.now())

        logger.info(
            "Sent extension check-in reminder to guest %s (%s)",
            stay.guest.full_name,
            stay.guest.whatsapp_number,
        )

        return {
            'status': 'success',
            'message_type': 'extend_checkin',
            'guest_id': stay.guest.id,
            'stay_id': stay_id,
            'is_test': bool(is_test),
            'reminder_date': resolved_reminder_date.isoformat(),
        }

    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found")
        return {'status': 'error', 'reason': 'stay_not_found'}


@shared_task
def schedule_checkin_reminder(stay_id, is_test=False):
    """
    Schedule extension check-in reminder for a new check-in.

    Args:
        stay_id: The ID of the newly checked-in stay
    """
    try:
        stay = Stay.objects.select_related('hotel').get(id=stay_id)

        if not stay.check_out_date:
            return {'status': 'error', 'reason': 'missing_checkout_date'}

        now = timezone.now()
        if is_test:
            countdown_seconds = 120
            scheduled_for = now + timedelta(seconds=countdown_seconds)
        else:
            reminder_time = stay.check_out_date - timedelta(hours=4)
            if reminder_time <= now:
                countdown_seconds = 60
                scheduled_for = now + timedelta(seconds=countdown_seconds)
            else:
                countdown_seconds = int((reminder_time - now).total_seconds())
                scheduled_for = reminder_time

        reminder_date = _checkout_reminder_date(stay)
        task_id = f"extend_reminder_guest_{stay.guest_id}_{reminder_date.strftime('%Y%m%d')}"

        existing_log = _guest_scope_logs(stay, 'checkout', reminder_date).filter(
            status__in={'scheduled', 'sent'}
        ).order_by('-created_at').first()
        if existing_log and existing_log.status == 'sent':
            _log_already_sent(existing_log)
            return {
                'status': 'skipped',
                'reason': 'already_sent',
                'stay_id': stay_id,
                'reminder_date': reminder_date.isoformat(),
            }
        if existing_log and existing_log.status == 'scheduled':
            _log_reminder_event(
                stay_id=stay.id,
                reminder_type='checkout',
                reminder_date=reminder_date,
                task_id=existing_log.task_id,
                status=existing_log.status,
                reason='already_present_for_guest',
            )
            return {
                'status': 'skipped',
                'reason': 'already_present_for_guest',
                'stay_id': stay_id,
                'reminder_date': reminder_date.isoformat(),
            }

        log = _upsert_reminder_log(
            stay,
            'checkout',
            reminder_date,
            status='scheduled',
            reason=None,
            is_test=is_test,
            scheduled_for=scheduled_for,
            task_id=task_id,
            metadata={'source': 'schedule_checkin_reminder'},
        )

        send_extend_checkin_reminder.apply_async(
            args=[stay_id, is_test, reminder_date.isoformat()],
            countdown=countdown_seconds,
            task_id=task_id,
        )

        logger.info(
            "Scheduled extension reminder for stay %s at %s (task_id=%s)",
            stay_id,
            scheduled_for,
            task_id,
        )

        return {
            'status': 'success',
            'stay_id': stay_id,
            'is_test': bool(is_test),
            'countdown_seconds': countdown_seconds,
            'scheduled_for': scheduled_for.isoformat(),
            'reminder_date': reminder_date.isoformat(),
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
def send_breakfast_reminder(self, stay_id, reminder_date=None):
    """Send breakfast reminder message to guest."""
    return _send_meal_reminder('breakfast', stay_id, reminder_date)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_lunch_reminder(self, stay_id, reminder_date=None):
    """Send lunch reminder message to guest."""
    return _send_meal_reminder('lunch', stay_id, reminder_date)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_dinner_reminder(self, stay_id, reminder_date=None):
    """Send dinner reminder message to guest."""
    return _send_meal_reminder('dinner', stay_id, reminder_date)


@shared_task
def schedule_meal_reminders(stay_id):
    """
    Schedule breakfast/lunch/dinner reminders for an active stay in hotel-local timezone.
    """
    try:
        stay = Stay.objects.select_related('hotel').get(id=stay_id)

        if not stay.check_out_date:
            logger.warning(f"Stay {stay_id} has no checkout date")
            return {'status': 'error', 'reason': 'no_checkout_date'}

        hotel_tz = _get_hotel_tz(stay.hotel)
        now = timezone.now()
        now_local = now.astimezone(hotel_tz)
        checkout_local = stay.check_out_date.astimezone(hotel_tz)

        meal_configs = [
            {
                'type': 'breakfast',
                'enabled': bool(stay.breakfast_reminder and stay.hotel.breakfast_reminder),
                'meal_time': stay.hotel.breakfast_time or time(6, 0),
                'task': send_breakfast_reminder,
            },
            {
                'type': 'lunch',
                'enabled': bool(stay.lunch_reminder),
                'meal_time': stay.hotel.lunch_time or time(12, 30),
                'task': send_lunch_reminder,
            },
            {
                'type': 'dinner',
                'enabled': bool(stay.dinner_reminder and stay.hotel.dinner_reminder),
                'meal_time': stay.hotel.dinner_time or time(17, 0),
                'task': send_dinner_reminder,
            },
        ]

        results = {
            'status': 'success',
            'stay_id': stay_id,
            'breakfast_enabled': meal_configs[0]['enabled'],
            'lunch_enabled': meal_configs[1]['enabled'],
            'dinner_enabled': meal_configs[2]['enabled'],
            'breakfast_scheduled': 0,
            'lunch_scheduled': 0,
            'dinner_scheduled': 0,
            'breakfast_already_present': 0,
            'lunch_already_present': 0,
            'dinner_already_present': 0,
            'breakfast_skipped': 0,
            'lunch_skipped': 0,
            'dinner_skipped': 0,
        }

        for config in meal_configs:
            reminder_type = config['type']
            if not config['enabled']:
                continue

            candidate = datetime.combine(
                now_local.date(),
                config['meal_time'],
                tzinfo=hotel_tz,
            )

            if candidate <= now_local:
                candidate += timedelta(days=1)

            while candidate < checkout_local:
                reminder_date = candidate.date()
                task_id = f"{reminder_type}_reminder_guest_{stay.guest_id}_{reminder_date.strftime('%Y%m%d')}"
                countdown = int((candidate - now_local).total_seconds())

                if countdown <= 0:
                    results[f'{reminder_type}_skipped'] += 1
                    candidate += timedelta(days=1)
                    continue

                existing_log = _guest_scope_logs(stay, reminder_type, reminder_date).filter(
                    status__in={'scheduled', 'sent'}
                ).order_by('-created_at').first()

                if existing_log and existing_log.status in {'scheduled', 'sent'}:
                    results[f'{reminder_type}_already_present'] += 1
                    _log_reminder_event(
                        stay_id=stay.id,
                        reminder_type=reminder_type,
                        reminder_date=reminder_date,
                        task_id=existing_log.task_id,
                        status=existing_log.status,
                        reason='already_present',
                    )
                    candidate += timedelta(days=1)
                    continue

                _upsert_reminder_log(
                    stay,
                    reminder_type,
                    reminder_date,
                    status='scheduled',
                    reason=None,
                    is_test=False,
                    scheduled_for=candidate.astimezone(dt_timezone.utc),
                    task_id=task_id,
                    metadata={'source': 'schedule_meal_reminders'},
                )

                config['task'].apply_async(
                    args=[stay_id, reminder_date.isoformat()],
                    countdown=countdown,
                    task_id=task_id,
                )

                logger.info(
                    "Scheduled %s reminder for stay %s at %s (task_id=%s)",
                    reminder_type,
                    stay_id,
                    candidate,
                    task_id,
                )
                results[f'{reminder_type}_scheduled'] += 1
                candidate += timedelta(days=1)

        return results

    except Stay.DoesNotExist:
        logger.error(f"Stay {stay_id} not found when scheduling meal reminders")
        return {'status': 'error', 'reason': 'stay_not_found'}
    except Exception as e:
        logger.error(f"Error scheduling meal reminders for stay {stay_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}
