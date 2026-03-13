from django.utils import timezone
import math


def calculate_stay_billing(stay):
    """
    Calculate billing information for a stay.

    Args:
        stay: Stay instance

    Returns:
        dict: Billing information including current_bill and expected_bill
    """
    # Get room rate from room category
    if not stay.room:
        return {
            'current_bill': 0,
            'expected_bill': 0,
        }

    room_rate = stay.room.category.base_price

    # If no check-in yet, bill is 0
    if not stay.actual_check_in:
        return {
            'current_bill': 0,
            'expected_bill': 0,
        }

    now = timezone.now()
    check_in_time = stay.actual_check_in
    checkout_time = stay.check_out_date

    # Calculate duration in seconds
    total_duration_seconds = (checkout_time - check_in_time).total_seconds()
    current_duration_seconds = min((now - check_in_time).total_seconds(), total_duration_seconds)

    # For all stays, bill in 24-hour units with minimum 1 day.
    total_units = math.ceil(total_duration_seconds / (24 * 3600))
    total_units = max(total_units, 1)

    if current_duration_seconds > 0:
        current_units = math.ceil(current_duration_seconds / (24 * 3600))
        current_units = max(current_units, 1)
    else:
        current_units = 0

    expected_bill = total_units * room_rate
    current_bill = current_units * room_rate

    return {
        'current_bill': float(current_bill),
        'expected_bill': float(expected_bill),
    }
