from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

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

        return {
            'from': message.get('from'),
            'type': message.get('type'),
            'timestamp': message.get('timestamp'),
            'text': message.get('text', {}).get('body', ''),
            'interactive': message.get('interactive'),
            'image': message.get('image'),
            'audio': message.get('audio'),
            'video': message.get('video'),
            'document': message.get('document'),
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


def generate_department_menu_payload(recipient_number, guest_name="Guest"):
    """
    Generate WhatsApp interactive list payload for department selection
    """
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
                        "rows": [
                            {
                                "id": "reception",
                                "title": "Reception",
                                "description": "Front desk and guest services"
                            },
                            {
                                "id": "housekeeping",
                                "title": "Housekeeping",
                                "description": "Room cleaning and maintenance"
                            },
                            {
                                "id": "room_service",
                                "title": "Room Service",
                                "description": "In-room dining and amenities"
                            },
                            {
                                "id": "restaurant",
                                "title": "Restaurant",
                                "description": "Dining reservations and inquiries"
                            },
                            {
                                "id": "management",
                                "title": "Management",
                                "description": "Speak with hotel management"
                            }
                        ]
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


def validate_department_selection(department_id):
    """
    Validate if department ID is from our menu
    Returns: (is_valid, normalized_department_name)
    """
    valid_departments = {
        'reception': 'Reception',
        'housekeeping': 'Housekeeping',
        'room_service': 'Room Service',
        'restaurant': 'Restaurant',
        'management': 'Management'
    }

    if department_id and department_id.lower() in valid_departments:
        return True, valid_departments[department_id.lower()]
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
