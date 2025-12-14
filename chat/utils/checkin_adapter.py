"""
Adapter to convert checkin flow responses to WhatsApp payload format.
"""

from .whatsapp_payload_utils import convert_flow_response_to_whatsapp_payload


def adapt_checkin_response_to_whatsapp(checkin_response, recipient_number):
    """
    Convert checkin flow response to WhatsApp payload format.
    Supports both single message and list of messages.

    Args:
        checkin_response: Response from checkin_flow.py (single dict or list of dicts)
        recipient_number: WhatsApp phone number to send to

    Returns:
        WhatsApp payload dictionary or list of dictionaries ready for sending
    """
    # Handle list of messages
    if isinstance(checkin_response, list):
        payloads = []
        for response in checkin_response:
            payload = _convert_single_checkin_response(response, recipient_number)
            payloads.append(payload)
        return payloads
    
    # Handle single message (backward compatibility)
    return _convert_single_checkin_response(checkin_response, recipient_number)


def _convert_single_checkin_response(checkin_response, recipient_number):
    """
    Convert a single checkin flow response to WhatsApp payload format.

    Args:
        checkin_response: Single response from checkin_flow.py
        recipient_number: WhatsApp phone number to send to

    Returns:
        WhatsApp payload dictionary ready for sending
    """
    if not checkin_response:
        # Empty response - send error message
        flow_result = {
            'status': 'error',
            'response': {
                'response_type': 'text',
                'text': 'No response received from check-in flow.'
            }
        }
        return convert_flow_response_to_whatsapp_payload(flow_result, recipient_number)

    response_type = checkin_response.get('type', 'text')
    text_content = checkin_response.get('text', '')

    # Convert checkin flow format to flow webhook format
    if response_type == 'text':
        flow_result = {
            'status': 'success',
            'response': {
                'response_type': 'text',
                'text': text_content
            }
        }

    elif response_type == 'button':
        # Convert button format
        options = checkin_response.get('options', [])
        flow_result = {
            'status': 'success',
            'response': {
                'response_type': 'buttons',
                'text': text_content,
                'body_text': checkin_response.get('body_text'),
                'options': options  # Pass full option objects with custom IDs
            }
        }

    elif response_type == 'list':
        # Convert list format
        options = checkin_response.get('options', [])
        flow_result = {
            'status': 'success',
            'response': {
                'response_type': 'list',
                'text': text_content,
                'body_text': checkin_response.get('body_text'),
                'options': [opt.get('title', '') for opt in options if opt.get('title')]
            }
        }

    else:
        # Default to text for unknown types
        flow_result = {
            'status': 'success',
            'response': {
                'response_type': 'text',
                'text': text_content or 'Processing your request...'
            }
        }

    return convert_flow_response_to_whatsapp_payload(flow_result, recipient_number)


def create_checkin_text_payload(recipient_number, message_text):
    """
    Create a text payload directly for checkin flow.

    Args:
        recipient_number: WhatsApp phone number to send to
        message_text: The text message to send

    Returns:
        WhatsApp payload dictionary
    """
    checkin_response = {
        'type': 'text',
        'text': message_text
    }
    return adapt_checkin_response_to_whatsapp(checkin_response, recipient_number)


def create_checkin_button_payload(recipient_number, message_text, buttons, body_text=None):
    """
    Create a button payload directly for checkin flow.

    Args:
        recipient_number: WhatsApp phone number to send to
        message_text: The message text to display
        buttons: List of button dictionaries with 'id' and 'title'
        body_text: Optional body text for detailed description

    Returns:
        WhatsApp payload dictionary
    """
    checkin_response = {
        'type': 'button',
        'text': message_text,
        'options': buttons
    }
    if body_text:
        checkin_response['body_text'] = body_text
    return adapt_checkin_response_to_whatsapp(checkin_response, recipient_number)


def create_checkin_list_payload(recipient_number, message_text, options, body_text=None):
    """
    Create a list payload directly for checkin flow.

    Args:
        recipient_number: WhatsApp phone number to send to
        message_text: The message text to display
        options: List of option dictionaries with 'id' and 'title'
        body_text: Optional body text for detailed description

    Returns:
        WhatsApp payload dictionary
    """
    checkin_response = {
        'type': 'list',
        'text': message_text,
        'options': options
    }
    if body_text:
        checkin_response['body_text'] = body_text
    return adapt_checkin_response_to_whatsapp(checkin_response, recipient_number)
