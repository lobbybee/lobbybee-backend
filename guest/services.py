from django.utils import timezone
from .models import Stay, Guest

def complete_checkin(stay_id, hotel):
    """
    Complete the check-in process for a guest.
    
    Args:
        stay_id (int): The ID of the stay to check in
        hotel (Hotel): The hotel object (for validation)
        
    Returns:
        tuple: (success: bool, message: str, stay: Stay or None)
    """
    try:
        # Get the stay object
        stay = Stay.objects.get(pk=stay_id, hotel=hotel)
    except Stay.DoesNotExist:
        return False, "Stay not found in this hotel.", None

    # Check if the stay is in the correct status
    if stay.status != "pending":
        return False, f"Check-in cannot be initiated. Stay status is '{stay.status}' instead of 'pending'.", None

    # Check if identity is verified
    if not stay.identity_verified:
        return False, "Identity not verified for this stay.", None

    # Check room availability
    room = stay.room
    if room.status != "available":
        return False, f"Room is not available. Current status: {room.status}", None

    # Update statuses
    stay.status = "active"
    stay.actual_check_in = timezone.now()
    stay.save()

    room.status = "occupied"
    room.current_guest = stay.guest
    room.save()

    guest = stay.guest
    guest.status = "checked_in"
    guest.save()

    return True, "Check-in completed successfully.", stay