from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import math


def calculate_stay_billing(stay):
    """
    Calculate billing information for a stay.

    Args:
        stay: Stay instance

    Returns:
        dict: Billing information including current_bill, expected_bill, and hours_24
    """
    # Get room rate from room category
    if not stay.room:
        return {
            'current_bill': 0,
            'expected_bill': 0,
            'hours_24': stay.hours_24
        }

    room_rate = stay.room.category.base_price

    # If no check-in yet, bill is 0
    if not stay.actual_check_in:
        return {
            'current_bill': 0,
            'expected_bill': 0,
            'hours_24': stay.hours_24
        }

    now = timezone.now()
    check_in_time = stay.actual_check_in
    checkout_time = stay.check_out_date

    # Calculate duration in seconds
    total_duration_seconds = (checkout_time - check_in_time).total_seconds()
    current_duration_seconds = min((now - check_in_time).total_seconds(), total_duration_seconds)

    if stay.hours_24:
        # For 24-hour stays
        # Minimum charge is for 1 day (24 hours)
        min_duration_seconds = 24 * 3600  # 24 hours in seconds

        # Calculate total units (days), rounding up to charge for partial days
        total_units = math.ceil(total_duration_seconds / (24 * 3600))
        total_units = max(total_units, 1)  # Minimum 1 day

        # Calculate current units, with minimum of 1 day if any time has passed
        if current_duration_seconds > 0:
            current_units = math.ceil(current_duration_seconds / (24 * 3600))
            current_units = max(current_units, 1)  # Minimum 1 day
        else:
            current_units = 0

        # Calculate bills
        expected_bill = total_units * room_rate
        current_bill = current_units * room_rate

    else:
        # For 12-hour stays
        # Minimum charge is for 12 hours
        min_duration_seconds = 12 * 3600  # 12 hours in seconds

        # Calculate total units (12-hour periods), rounding up
        total_units = math.ceil(total_duration_seconds / (12 * 3600))
        total_units = max(total_units, 1)  # Minimum 1 unit (12 hours)

        # Calculate current units, with minimum of 1 unit if any time has passed
        if current_duration_seconds > 0:
            current_units = math.ceil(current_duration_seconds / (12 * 3600))
            current_units = max(current_units, 1)  # Minimum 1 unit (12 hours)
        else:
            current_units = 0

        # Calculate bills
        expected_bill = total_units * room_rate
        current_bill = current_units * room_rate

    return {
        'current_bill': float(current_bill),
        'expected_bill': float(expected_bill),
        'hours_24': stay.hours_24
    }