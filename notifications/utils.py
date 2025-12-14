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


def get_user_notifications(user, include_group_notifications=True):
    """
    Get all notifications for a user, including group notifications they belong to
    Compatible with both PostgreSQL and SQLite
    """
    from django.db import connection
    
    # Start with personal notifications
    query = Notification.objects.filter(user=user)
    
    if include_group_notifications:
        # Build conditions for group notifications
        conditions = []
        
        # Get hotel staff notifications if user is hotel staff
        if user.user_type in ['hotel_admin', 'manager', 'receptionist'] and user.hotel:
            conditions.append(
                Notification.objects.filter(
                    group_type='hotel_staff',
                    hotel=user.hotel
                )
            )
        
        # Get platform user notifications if user is platform user
        if user.user_type in ['platform_admin', 'platform_staff']:
            conditions.append(
                Notification.objects.filter(
                    group_type='platform_user'
                )
            )
        
        # Combine queries based on database type
        if conditions:
            if connection.vendor == 'postgresql':
                # PostgreSQL supports UNION with ORDER BY
                for condition in conditions:
                    query = query.union(condition)
            else:
                # For SQLite and others, use the ID collection approach
                notification_ids = list(query.values_list('id', flat=True))
                for condition in conditions:
                    notification_ids.extend(condition.values_list('id', flat=True))
                
                # Remove duplicates and fetch
                unique_ids = list(set(notification_ids))
                if unique_ids:
                    return Notification.objects.filter(id__in=unique_ids).order_by('-created_at')
                return Notification.objects.none()
    
    return query.order_by('-created_at')


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