import logging
from django.utils import timezone
from zoneinfo import ZoneInfo
from guest.name_utils import get_first_name_from_full_name

logger = logging.getLogger(__name__)


def process_checkout_extension_response(guest, message_text):
    """
    Handle checkout-extension reminder button replies.

    Supported button IDs:
    - stay_extend_yes_{stay_id}
    - stay_extend_no_{stay_id}
    """
    if not guest or not isinstance(message_text, str):
        return None

    yes_prefix = "stay_extend_yes_"
    no_prefix = "stay_extend_no_"

    if not (message_text.startswith(yes_prefix) or message_text.startswith(no_prefix)):
        return None

    stay_id_str = message_text.replace(yes_prefix, "").replace(no_prefix, "")
    try:
        stay_id = int(stay_id_str)
    except (TypeError, ValueError):
        return {
            "type": "text",
            "text": "Invalid extension response. Please contact reception for assistance."
        }

    from guest.models import Stay
    stay = Stay.objects.filter(id=stay_id, guest=guest).select_related("hotel", "room").first()
    if not stay or stay.status != "active":
        return {
            "type": "text",
            "text": "This stay is no longer active. Please contact reception for assistance."
        }

    hotel_tz = ZoneInfo(stay.hotel.time_zone or 'UTC')

    if message_text.startswith(no_prefix):
        checkout_local = stay.check_out_date.astimezone(hotel_tz) if stay.check_out_date else None
        checkout_time_text = checkout_local.strftime('%H:%M') if checkout_local else "the scheduled time"
        return {
            "type": "text",
            "text": (
                "Thank you for your response. We hope you enjoyed your stay. "
                f"You can stay with us till {checkout_time_text}."
            )
        }

    # YES -> notify all hotel staff (admin, manager, receptionist).
    try:
        from notifications.utils import send_notification_to_hotel_staff

        room_number = stay.room.room_number if stay.room else "N/A"
        checkout_local = stay.check_out_date.astimezone(hotel_tz) if stay.check_out_date else None
        checkout_time_text = checkout_local.strftime("%Y-%m-%d %H:%M") if checkout_local else "N/A"

        send_notification_to_hotel_staff(
            hotel=stay.hotel,
            title="Stay Extension Request",
            message=(
                f"{get_first_name_from_full_name(guest.full_name)} requested a stay extension "
                f"(Room: {room_number}, Current checkout: {checkout_time_text})."
            ),
            link=f"/stays/{stay.id}",
            link_label="Review Request"
        )
    except Exception as e:
        logger.error(
            f"Failed to create stay extension notifications for stay {stay.id}: {e}",
            exc_info=True
        )

    return {
        "type": "text",
        "text": "Thanks! We have informed the reception team about your extension request."
    }
