import math
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from celery import current_app

from flag_system.models import GuestFlag
from flag_system.services import create_guest_flag
from guest.models import Booking, Guest, ReminderLog, Stay


def should_send_checkout_comms(guest, hotel):
    """
    Send checkout comms only when the guest has no active stays left in this hotel.
    """
    return not Stay.objects.filter(guest=guest, hotel=hotel, status='active').exists()


def _calculate_checkout_amount(stay, checkout_at):
    """
    Fallback checkout billing when amount is not provided.
    Uses room category base rate * number of stay days (minimum 1 day).
    """
    if not stay.room or not stay.room.category or stay.room.category.base_price is None:
        return Decimal('0.00')

    start_time = stay.actual_check_in or stay.check_in_date
    if not start_time:
        return Decimal('0.00')

    total_seconds = (checkout_at - start_time).total_seconds()
    days = max(1, math.ceil(max(total_seconds, 0) / (24 * 3600)))
    return Decimal(stay.room.category.base_price) * Decimal(days)


def _resolve_booking_status(booking):
    """
    Booking supports pending/confirmed/cancelled only.
    - confirmed while any active stay exists
    - pending while any pending stay exists and no active stay exists
    - cancelled if all stays are cancelled
    - confirmed if all stays are completed (fulfilled booking)
    """
    statuses = list(booking.stays.values_list('status', flat=True))
    if not statuses:
        return booking.status

    unique_statuses = set(statuses)
    if 'active' in unique_statuses:
        return 'confirmed'
    if 'pending' in unique_statuses:
        return 'pending'
    if unique_statuses == {'cancelled'}:
        return 'cancelled'
    if unique_statuses == {'completed'}:
        return 'confirmed'
    return 'confirmed'


def _revoke_tasks_after_commit(task_ids):
    """Revoke pending Celery tasks after checkout transaction commits."""
    for task_id in task_ids:
        try:
            current_app.control.revoke(task_id)
        except Exception:
            # Revoke errors should not fail checkout completion.
            continue


def checkout_stays_for_guest(*, hotel, guest_id, stay_ids, actor, options):
    """
    Checkout multiple active stays for a single guest atomically.

    Returns:
        dict with checked_out_stays, guest_has_active_stays, should_send_comms,
        total_amount, and representative_stay.
    """
    if not stay_ids:
        raise serializers.ValidationError({'stay_ids': 'This list may not be empty.'})

    if len(set(stay_ids)) != len(stay_ids):
        raise serializers.ValidationError({'stay_ids': 'stay_ids must be unique.'})

    stays = list(
        Stay.objects.select_related('guest', 'room', 'room__category', 'booking', 'hotel')
        .filter(id__in=stay_ids, hotel=hotel)
    )

    if len(stays) != len(stay_ids):
        found_ids = {s.id for s in stays}
        invalid_ids = [sid for sid in stay_ids if sid not in found_ids]
        raise serializers.ValidationError({'stay_ids': f'Invalid stay_ids for this hotel: {invalid_ids}'})

    guest_ids = {s.guest_id for s in stays}
    if guest_ids != {guest_id}:
        raise serializers.ValidationError({'stay_ids': 'All stays must belong to the provided guest_id.'})

    non_active = [s.id for s in stays if s.status != 'active']
    if non_active:
        raise serializers.ValidationError({'stay_ids': f'All stays must be active. Invalid stay_ids: {non_active}'})

    try:
        guest = Guest.objects.get(id=guest_id)
    except Guest.DoesNotExist as exc:
        raise serializers.ValidationError({'guest_id': 'Guest not found.'}) from exc

    amount_paid = options.get('amount_paid')
    internal_rating = options.get('internal_rating')
    internal_note = options.get('internal_note')
    flag_user = options.get('flag_user', False)

    checkout_at = timezone.now()
    checked_out_stays = []
    affected_booking_ids = set()
    total_amount = Decimal('0.00')
    reminder_task_ids_to_revoke = []

    with transaction.atomic():
        for stay in stays:
            stay_amount = amount_paid if amount_paid is not None else _calculate_checkout_amount(stay, checkout_at)
            stay.total_amount = stay_amount
            stay.status = 'completed'
            stay.actual_check_out = checkout_at

            if internal_rating is not None:
                stay.internal_rating = internal_rating
            if internal_note is not None:
                stay.internal_note = internal_note

            stay.save()
            total_amount += Decimal(stay_amount)
            checked_out_stays.append(stay)

            if stay.room:
                stay.room.status = 'cleaning'
                stay.room.current_guest = None
                stay.room.save(update_fields=['status', 'current_guest', 'updated_at'])

            if stay.booking_id:
                affected_booking_ids.add(stay.booking_id)

        checked_out_stay_ids = [stay.id for stay in checked_out_stays]
        future_logs = ReminderLog.objects.filter(
            stay_id__in=checked_out_stay_ids,
            status='scheduled',
            scheduled_for__gt=checkout_at,
        )
        reminder_task_ids_to_revoke = list(
            future_logs.exclude(task_id__isnull=True).exclude(task_id='').values_list('task_id', flat=True)
        )
        if future_logs.exists():
            future_logs.update(
                status='skipped',
                reason='checked_out_before_schedule',
                updated_at=timezone.now(),
            )

        if flag_user:
            existing_flag = GuestFlag.objects.filter(
                guest=guest,
                stay__hotel=hotel,
                is_active=True,
            ).first()
            if not existing_flag:
                reference_stay = checked_out_stays[0]
                flag_note = internal_note or reference_stay.internal_note or 'Flagged during checkout'
                create_guest_flag(
                    guest_id=guest.id,
                    stay_id=reference_stay.id,
                    internal_reason=flag_note,
                    global_note=flag_note,
                    flagged_by_police=False,
                    user=actor,
                )

        for booking_id in affected_booking_ids:
            booking = Booking.objects.get(id=booking_id)
            booking_total = booking.stays.aggregate(total=Sum('total_amount')).get('total') or Decimal('0.00')
            booking.status = _resolve_booking_status(booking)
            booking.total_amount = booking_total
            booking.save(update_fields=['status', 'total_amount'])

        guest_has_active_stays = Stay.objects.filter(guest=guest, hotel=hotel, status='active').exists()
        guest.status = 'checked_in' if guest_has_active_stays else 'checked_out'
        guest.save(update_fields=['status'])

        if reminder_task_ids_to_revoke:
            transaction.on_commit(lambda: _revoke_tasks_after_commit(reminder_task_ids_to_revoke))

    checked_out_stays.sort(key=lambda stay: stay.id)
    representative_stay = checked_out_stays[0]

    return {
        'guest': guest,
        'checked_out_stays': checked_out_stays,
        'guest_has_active_stays': guest_has_active_stays,
        'should_send_comms': should_send_checkout_comms(guest, hotel),
        'total_amount': total_amount,
        'representative_stay': representative_stay,
    }
