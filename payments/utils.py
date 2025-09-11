from django.utils import timezone


def is_hotel_subscribed(hotel):
    """
    Check if a hotel has an active subscription
    """
    try:
        subscription = hotel.subscription
        return subscription.is_active and not subscription.is_expired()
    except Exception:
        return False


def get_hotel_subscription(hotel):
    """
    Get the hotel's subscription if it exists
    """
    try:
        return hotel.subscription
    except Exception:
        return None


def is_subscription_expired(hotel):
    """
    Check if a hotel's subscription is expired
    """
    try:
        subscription = hotel.subscription
        return subscription.is_expired()
    except Exception:
        return True  # No subscription is considered expired