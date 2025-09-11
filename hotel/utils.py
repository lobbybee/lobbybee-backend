def is_hotel_subscribed(hotel):
    """
    Check if a hotel has an active subscription
    """
    try:
        from payments.utils import is_hotel_subscribed as payment_is_subscribed
        return payment_is_subscribed(hotel)
    except ImportError:
        # If payments app is not available, return False
        return False