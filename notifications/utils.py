from .models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()


def create_user_notification(user, title, message, link=None, link_label=None):
    """
    Create a notification for a single user
    """
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
        link_label=link_label
    )


def create_hotel_staff_notification(hotel, title, message, link=None, link_label=None):
    """
    Create a notification for all hotel staff (hotel_admin, manager, receptionist) in a specific hotel
    """
    return Notification.objects.create(
        group_type='hotel_staff',
        hotel=hotel,
        title=title,
        message=message,
        link=link,
        link_label=link_label
    )


def create_platform_user_notification(title, message, link=None, link_label=None):
    """
    Create a notification for all platform users (platform_admin, platform_staff)
    """
    return Notification.objects.create(
        group_type='platform_user',
        title=title,
        message=message,
        link=link,
        link_label=link_label
    )


def send_notification_to_user(user, title, message, link=None, link_label=None):
    """
    Send notification to a specific user
    """
    return create_user_notification(user, title, message, link, link_label)


def send_notification_to_hotel_staff(hotel, title, message, link=None, link_label=None):
    """
    Send notification to all hotel staff in a hotel
    """
    return create_hotel_staff_notification(hotel, title, message, link, link_label)


def send_notification_to_platform_users(title, message, link=None, link_label=None):
    """
    Send notification to all platform users
    """
    return create_platform_user_notification(title, message, link, link_label)


from django.db.models import Q

def get_user_notifications(user, include_group_notifications=True):
    """
    Get all notifications for a user, including group notifications they belong to
    Using Q objects for full compatibility with filters and updates.
    """
    # Personal notifications
    q_filter = Q(user=user)
    
    if include_group_notifications:
        # Hotel staff notifications
        if user.user_type in ['hotel_admin', 'manager', 'receptionist'] and hasattr(user, 'hotel') and user.hotel:
            q_filter |= Q(group_type='hotel_staff', hotel=user.hotel)
        
        # Platform user notifications
        if user.user_type in ['platform_admin', 'platform_staff']:
            q_filter |= Q(group_type='platform_user')
            
    return Notification.objects.filter(q_filter).order_by('-created_at')


# Backward compatibility
def create_notification(user, title, message, link=None, link_label=None):
    """Create a new notification for a user
    
    Args:
        user: User object to create notification for
        title: Notification title
        message: Notification message
        link: Optional URL to navigate to when clicked
        link_label: Optional label text for the link button
    """
    return create_user_notification(user, title, message, link, link_label)