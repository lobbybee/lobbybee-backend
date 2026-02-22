from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List
import logging
import re

logger = logging.getLogger(__name__)

DEFAULT_DEPARTMENTS = [
    "Reception",
    "Housekeeping",
    "Room Service",
    "Restaurant",
    "Management",
]

DEPARTMENT_DESCRIPTIONS = {
    "Reception": "Front desk and guest services",
    "Housekeeping": "Room cleaning and maintenance",
    "Room Service": "In-room dining and amenities",
    "Restaurant": "Dining reservations and inquiries",
    "Management": "Speak with hotel management",
}

def is_conversation_expired(last_message_at, expiry_minutes=2):
    """
    Check if conversation is expired based on last message time
    """
    if not last_message_at:
        return True

    # Ensure last_message_at is timezone-aware
    if last_message_at.tzinfo is None:
        last_message_at = last_message_at.replace(tzinfo=timezone.utc)

    current_time = datetime.now(timezone.utc)
    time_diff = (current_time - last_message_at).total_seconds() / 60
    return time_diff > expiry_minutes


def extract_whatsapp_message_data(webhook_body):
    """
    Safely extract WhatsApp message data from webhook
    Returns: (message_data, error_message)
    """
    try:
        if not webhook_body:
            return None, "Missing webhook body"

        entry = webhook_body.get('entry', [])
        if not entry or len(entry) == 0:
            return None, "Invalid webhook structure: missing entry"

        changes = entry[0].get('changes', [])
        if not changes or len(changes) == 0:
            return None, "Invalid webhook structure: missing changes"

        value = changes[0].get('value', {})
        messages = value.get('messages', [])
        if not messages or len(messages) == 0:
            return None, "Invalid webhook structure: missing messages"

        message = messages[0]

        # Extract media ID if present
        media_id = None
        msg_type = message.get('type')
        if msg_type in ['image', 'audio', 'video', 'document']:
            media_obj = message.get(msg_type, {})
            if media_obj:
                media_id = media_obj.get('id')

        return {
            'from': message.get('from'),
            'id': message.get('id'),  # WhatsApp message ID for deduplication
            'type': message.get('type'),
            'timestamp': message.get('timestamp'),
            'text': message.get('text', {}).get('body', ''),
            'interactive': message.get('interactive'),
            'image': message.get('image'),
            'audio': message.get('audio'),
            'video': message.get('video'),
            'document': message.get('document'),
            'media_id': media_id,  # Extract media ID for downloading
        }, None

    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Error extracting WhatsApp message: {e}")
        return None, f"Failed to parse webhook data: {str(e)}"


def get_message_type_info(message_data):
    """
    Get detailed message type information
    """
    if not message_data:
        return None

    msg_type = message_data.get('type')
    result = {
        'type': msg_type,
        'is_text': msg_type == 'text',
        'is_interactive': msg_type == 'interactive',
        'is_media': msg_type in ['image', 'audio', 'video', 'document'],
        'interactive_type': None,
        'is_list_reply': False,
        'is_button_reply': False,
    }

    if result['is_interactive'] and message_data.get('interactive'):
        interactive_type = message_data['interactive'].get('type')
        result['interactive_type'] = interactive_type
        result['is_list_reply'] = interactive_type == 'list_reply'
        result['is_button_reply'] = interactive_type == 'button_reply'

        if result['is_list_reply']:
            result['list_reply_id'] = message_data['interactive'].get('list_reply', {}).get('id')
            result['list_reply_title'] = message_data['interactive'].get('list_reply', {}).get('title')
        elif result['is_button_reply']:
            result['button_reply_id'] = message_data['interactive'].get('button_reply', {}).get('id')
            result['button_reply_title'] = message_data['interactive'].get('button_reply', {}).get('title')

    return result


def _normalize_departments(available_departments=None):
    """Normalize department names into canonical values used by conversations."""
    if not available_departments:
        return DEFAULT_DEPARTMENTS.copy()

    resolved = []
    seen = set()
    for raw_value in available_departments:
        if not isinstance(raw_value, str):
            continue
        value = raw_value.strip()
        if not value:
            continue

        canonical = next(
            (dept for dept in DEFAULT_DEPARTMENTS if dept.lower() == value.lower()),
            None,
        )
        if canonical and canonical not in seen:
            seen.add(canonical)
            resolved.append(canonical)

    return resolved or DEFAULT_DEPARTMENTS.copy()


def _build_department_options(available_departments=None):
    """
    Build WhatsApp list rows and ID lookup map for department selection.
    """
    normalized_departments = _normalize_departments(available_departments)
    rows = []
    id_to_department = {}

    for department_name in normalized_departments:
        slug = re.sub(r"[^a-z0-9]+", "_", department_name.lower()).strip("_")
        row_id = f"dept_{slug}" if slug else f"dept_{len(rows) + 1}"

        # Ensure uniqueness in edge cases.
        original_row_id = row_id
        suffix = 2
        while row_id in id_to_department:
            row_id = f"{original_row_id}_{suffix}"
            suffix += 1

        id_to_department[row_id] = department_name
        # Backward compatibility with legacy static IDs and titles.
        id_to_department[slug] = department_name
        id_to_department[department_name.lower()] = department_name

        rows.append(
            {
                "id": row_id,
                "title": department_name,
                "description": DEPARTMENT_DESCRIPTIONS.get(
                    department_name, "Guest support and assistance"
                ),
            }
        )

    return normalized_departments, id_to_department, rows


def generate_department_menu_payload(recipient_number, guest_name="Guest", available_departments=None):
    """
    Generate WhatsApp interactive list payload for department selection
    """
    _, _, rows = _build_department_options(available_departments)

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": f"Hi {guest_name}, Welcome to Hotel Services"
            },
            "body": {
                "text": "Please choose a department you'd like to contact:"
            },
            "footer": {
                "text": "Powered by LobbyBee"
            },
            "action": {
                "button": "View Departments 🐝",
                "sections": [
                    {
                        "title": "Hotel Departments",
                        "rows": rows
                    }
                ]
            }
        }
    }


def generate_error_text_payload(recipient_number, error_message):
    """
    Generate WhatsApp text message payload for errors
    """
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "text",
        "text": {
            "body": error_message
        }
    }


def generate_success_text_payload(recipient_number, department_name, guest_name="Guest"):
    """
    Generate WhatsApp text message payload for successful department connection
    """
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "text",
        "text": {
            "body": f"✅ You are now connected to {department_name}, {guest_name}!\n\nOur team will be with you shortly. Please share your request, and we'll be happy to assist you. 🐝"
        }
    }


def validate_department_selection(department_id, available_departments=None, list_reply_title=None):
    """
    Validate if department ID is from our menu
    Returns: (is_valid, normalized_department_name)
    """
    normalized_departments, id_to_department, _ = _build_department_options(available_departments)

    if list_reply_title:
        title_match = next(
            (
                department_name
                for department_name in normalized_departments
                if department_name.lower() == list_reply_title.strip().lower()
            ),
            None,
        )
        if title_match:
            return True, title_match

    if department_id:
        resolved_department = id_to_department.get(department_id.lower())
        if resolved_department:
            return True, resolved_department

    return False, None


def find_active_department_conversation(conversations: List[Dict], department_name: str) -> Optional[Dict]:
    """
    Find an active (non-expired) conversation for a specific department

    Args:
        conversations: List of conversation dictionaries (not DB objects)
        department_name: Department name to search for

    Returns:
        Conversation dict if found, None otherwise
    """
    if not conversations or not department_name:
        return None

    for conv in conversations:
        # Skip expired conversations
        if conv.get('is_expired', False):
            continue

        # Check department match (case-insensitive)
        conv_dept = conv.get('department', '')
        if conv_dept.lower() == department_name.lower():
            return conv

    return None
