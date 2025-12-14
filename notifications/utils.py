from .models import Notification

def create_notification(user, title, message, link=None, link_label=None):
    """Create a new notification for a user
    
    Args:
        user: User object to create notification for
        title: Notification title
        message: Notification message
        link: Optional URL to navigate to when clicked
        link_label: Optional label text for the link button
    """
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
        link_label=link_label
    )