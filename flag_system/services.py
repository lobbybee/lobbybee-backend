from django.db.models import Q
from .models import GuestFlag
from guest.models import Stay


def get_active_flags_for_guest(guest_id):
    """
    Get all active flags for a guest with related data preloaded
    """
    return GuestFlag.objects.filter(
        guest_id=guest_id,
        is_active=True
    ).select_related(
        'guest',
        'last_modified_by',
        'stay__hotel',
        'reset_by'
    ).order_by('-created_at')


def get_flag_summary_for_guest(guest_id):
    """
    Get a summary of all flags for a guest (active flags only)
    """
    # Get all active flags
    active_flags = get_active_flags_for_guest(guest_id)
    
    # Check if police flagged
    police_flagged = active_flags.filter(flagged_by_police=True).exists()
    
    return {
        'is_flagged': active_flags.exists(),
        'police_flagged': police_flagged,
        'flags': active_flags
    }


def create_guest_flag(guest_id, stay_id, internal_reason, global_note, flagged_by_police, user):
    """
    Create a new flag for a guest
    """
    guest_flag = GuestFlag.objects.create(
        guest_id=guest_id,
        stay_id=stay_id,
        internal_reason=internal_reason,
        global_note=global_note,
        flagged_by_police=flagged_by_police,
        last_modified_by=user
    )
    
    return guest_flag


def reset_guest_flag(flag_id, reset_reason, user):
    """
    Reset (deactivate) a flag
    """
    try:
        flag = GuestFlag.objects.get(id=flag_id, is_active=True)
        flag.reset(reset_reason=reset_reason, reset_by_user=user)
        return flag
    except GuestFlag.DoesNotExist:
        return None


def get_guest_stay_history_with_ratings(guest_id, hotel_ids=None):
    """
    Get guest's stay history with internal ratings and notes from specified hotels
    """
    stays = Stay.objects.filter(
        guest_id=guest_id,
        status='completed'
    )
    
    if hotel_ids:
        stays = stays.filter(hotel_id__in=hotel_ids)
    
    return stays.exclude(
        Q(internal_rating__isnull=True) & Q(internal_note__exact='')
    ).select_related('hotel').order_by('-actual_check_out')