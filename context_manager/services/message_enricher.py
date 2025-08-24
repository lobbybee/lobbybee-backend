import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def enrich_message_with_metadata(message: Dict[str, Any], message_type: str = None, status: str = 'info') -> Dict[str, Any]:
    """
    Enrich a message with metadata including message_type and status.
    
    Args:
        message: The message object (dict) to enrich
        message_type: The type of message (e.g., 'text', 'quick-reply', 'list-picker')
        status: The status of the message (e.g., 'success', 'info', 'warning', 'error')
        
    Returns:
        Dict containing the original message with added metadata
    """
    # If message is already enriched, return as-is
    if isinstance(message, dict) and 'metadata' in message:
        return message
    
    enriched_message = {
        'content': message,
        'metadata': {
            'message_type': message_type or _infer_message_type(message),
            'status': status
        }
    }
    
    return enriched_message


def _infer_message_type(message: Dict[str, Any]) -> str:
    """
    Infer the message type from the message content.
    
    Args:
        message: The message object to analyze
        
    Returns:
        Inferred message type
    """
    if not isinstance(message, dict):
        return 'text'
    
    # Check for interactive message types
    if 'type' in message:
        if message['type'] == 'interactive':
            interactive_type = message.get('interactive', {}).get('type', 'unknown')
            if interactive_type == 'button':
                return 'quick-reply'
            elif interactive_type == 'list':
                return 'list-picker'
            else:
                return f'interactive-{interactive_type}'
        else:
            return message['type']
    
    # Check for text messages
    if 'text' in message:
        return 'text'
    
    # Default fallback
    return 'unknown'


def enrich_messages_list(messages: List[Dict[str, Any]], default_message_type: str = None, default_status: str = 'info') -> List[Dict[str, Any]]:
    """
    Enrich a list of messages with metadata.
    
    Args:
        messages: List of message objects to enrich
        default_message_type: Default message type to use if not specified
        default_status: Default status to use if not specified
        
    Returns:
        List of enriched message objects
    """
    enriched_messages = []
    
    for i, message in enumerate(messages):
        # For multiple messages, we might want to vary the status
        status = default_status
        if i == 0 and len(messages) > 1:
            # First message in a multi-message sequence might be informational
            status = 'info'
        
        enriched_message = enrich_message_with_metadata(
            message, 
            message_type=default_message_type,
            status=status
        )
        enriched_messages.append(enriched_message)
    
    return enriched_messages