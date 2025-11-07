"""
Utility functions for converting various response formats to WhatsApp payloads.
"""

from .whatsapp_flow_utils import generate_error_text_payload


def convert_flow_response_to_whatsapp_payload(flow_result, recipient_number):
    """
    Convert flow webhook response to WhatsApp payload
    
    Args:
        flow_result: Response from flow webhook processing
        recipient_number: WhatsApp phone number to send to
        
    Returns:
        WhatsApp payload dictionary ready for sending
    """
    if not flow_result or not flow_result.get('success'):
        # Return error payload for failed flow
        return generate_error_text_payload(
            recipient_number,
            "Sorry, there was an error processing your request. Please try again."
        )
    
    response = flow_result.get('response', {})
    response_type = response.get('response_type', 'text')
    
    base_payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual", 
        "to": recipient_number
    }
    
    if response_type == 'text':
        base_payload.update({
            "type": "text",
            "text": {
                "body": response.get('text', '')
            }
        })
        
    elif response_type == 'buttons':
        # Interactive buttons response
        options = response.get('options', [])
        if len(options) > 3:
            # Too many buttons, convert to list
            base_payload.update({
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "header": {
                        "type": "text", 
                        "text": response.get('text', 'Please select an option:')
                    },
                    "body": {
                        "text": "Please choose from the options below:"
                    },
                    "action": {
                        "button": "Select Option",
                        "sections": [{
                            "title": "Options",
                            "rows": [
                                {
                                    "id": f"option_{i}",
                                    "title": option,
                                    "description": ""
                                } for i, option in enumerate(options)
                            ]
                        }]
                    }
                }
            })
        else:
            # Use buttons (max 3)
            base_payload.update({
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": response.get('text', '')
                    },
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {
                                    "id": f"btn_{i}",
                                    "title": option
                                }
                            } for i, option in enumerate(options)
                        ]
                    }
                }
            })
            
    elif response_type == 'list':
        # Interactive list response
        options = response.get('options', [])
        base_payload.update({
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {
                    "type": "text",
                    "text": response.get('text', 'Please select an option:')
                },
                "body": {
                    "text": "Please choose from the options below:"
                },
                "footer": {
                    "text": "Powered by LobbyBee"
                },
                "action": {
                    "button": "Select Option",
                    "sections": [{
                        "title": "Options",
                        "rows": [
                            {
                                "id": f"option_{i}",
                                "title": option,
                                "description": ""
                            } for i, option in enumerate(options)
                        ]
                    }]
                }
            }
        })
        
    elif response_type in ['image', 'document', 'video', 'audio']:
        # Media response - use link format
        media_url = response.get('media_url')
        if media_url:
            base_payload.update({
                "type": response_type,
                response_type: {
                    "link": media_url
                }
            })
            
            # Add caption if provided
            if response.get('caption'):
                base_payload[response_type]['caption'] = response['caption']
        else:
            # Fallback to text if no media URL
            base_payload.update({
                "type": "text",
                "text": {
                    "body": response.get('text', 'Media received but not available.')
                }
            })
    
    else:
        # Default text response for unknown types
        base_payload.update({
            "type": "text", 
            "text": {
                "body": response.get('text', 'Thank you for your message.')
            }
        })
    
    return base_payload


def create_text_message_payload(recipient_number, message_text):
    """
    Create a simple text message WhatsApp payload
    
    Args:
        recipient_number: WhatsApp phone number to send to
        message_text: The text message to send
        
    Returns:
        WhatsApp payload dictionary
    """
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "text",
        "text": {
            "body": message_text
        }
    }


def create_media_payload(recipient_number, media_type, media_url, caption=None):
    """
    Create a media message WhatsApp payload using link format
    
    Args:
        recipient_number: WhatsApp phone number to send to
        media_type: One of 'image', 'document', 'video', 'audio'
        media_url: URL to the media file
        caption: Optional caption for the media
        
    Returns:
        WhatsApp payload dictionary
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": media_type,
        media_type: {
            "link": media_url
        }
    }
    
    if caption:
        payload[media_type]['caption'] = caption
        
    return payload


def create_button_payload(recipient_number, message_text, buttons):
    """
    Create an interactive button WhatsApp payload (max 3 buttons)
    
    Args:
        recipient_number: WhatsApp phone number to send to
        message_text: The message text to display
        buttons: List of button text strings (max 3)
        
    Returns:
        WhatsApp payload dictionary
    """
    if len(buttons) > 3:
        raise ValueError("Maximum 3 buttons allowed")
    
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": message_text
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"btn_{i}",
                            "title": button
                        }
                    } for i, button in enumerate(buttons)
                ]
            }
        }
    }


def create_list_payload(recipient_number, header_text, options, footer_text="Powered by LobbyBee"):
    """
    Create an interactive list WhatsApp payload
    
    Args:
        recipient_number: WhatsApp phone number to send to
        header_text: The header text for the list
        options: List of option strings
        footer_text: Optional footer text
        
    Returns:
        WhatsApp payload dictionary
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
                "text": header_text
            },
            "body": {
                "text": "Please choose from the options below:"
            },
            "footer": {
                "text": footer_text
            },
            "action": {
                "button": "Select Option",
                "sections": [{
                    "title": "Options",
                    "rows": [
                        {
                            "id": f"option_{i}",
                            "title": option,
                            "description": ""
                        } for i, option in enumerate(options)
                    ]
                }]
            }
        }
    }