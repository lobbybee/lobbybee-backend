"""
Flow tracking utility functions for managing check-in and other automated flows.

This module provides functions to track, analyze, and manage flow states
based on Message model data, eliminating the need for temporary flags on Guest model.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from django.db.models import Q, Max
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_guest_pending_flows(guest_id: int, flow_type: str = 'checkin') -> List[Dict]:
    """
    Get incomplete flows for a guest.
    
    Args:
        guest_id: The guest ID to check flows for
        flow_type: Type of flow to check (default: 'checkin')
    
    Returns:
        List of incomplete flow information dictionaries
    """
    from chat.models import Message, Conversation
    
    # Get all conversations for this guest
    conversations = Conversation.objects.filter(guest_id=guest_id)
    
    incomplete_flows = []
    
    for conv in conversations:
        # Find flow messages that haven't reached completion
        flow_messages = Message.objects.filter(
            conversation=conv,
            is_flow=True,
            flow_id=flow_type
        ).order_by('flow_step')
        
        if flow_messages.exists():
            latest_message = flow_messages.last()
            
            # Check if flow is incomplete (no completion message found)
            is_complete = Message.objects.filter(
                conversation=conv,
                is_flow=True,
                flow_id=flow_type,
                flow_step__gte=999  # Assuming completion step has high number
            ).exists()
            
            if not is_complete:
                # Consider flow stale if older than 24 hours
                is_stale = latest_message.created_at < timezone.now() - timedelta(hours=24)
                
                incomplete_flows.append({
                    'conversation_id': conv.id,
                    'flow_id': latest_message.flow_id,
                    'current_step': latest_message.flow_step,
                    'step_success': latest_message.is_flow_step_success,
                    'last_activity': latest_message.created_at,
                    'is_stale': is_stale,
                    'total_steps': flow_messages.count()
                })
    
    return incomplete_flows


def has_guest_completed_checkin_flow(guest_id: int, within_hours: int = 24) -> bool:
    """
    Check if guest has completed a checkin flow within the specified timeframe.
    
    Args:
        guest_id: The guest ID to check
        within_hours: Time window to check for completion (default: 24 hours)
    
    Returns:
        True if guest has completed checkin within timeframe, False otherwise
    """
    from chat.models import Message, Conversation
    
    cutoff_time = timezone.now() - timedelta(hours=within_hours)
    
    # Get conversations for this guest
    conversations = Conversation.objects.filter(guest_id=guest_id)
    
    for conv in conversations:
        # Look for completion message (high step number indicates completion)
        completion_message = Message.objects.filter(
            conversation=conv,
            is_flow=True,
            flow_id='checkin',
            flow_step__gte=999,  # Completion step
            created_at__gte=cutoff_time
        ).first()
        
        if completion_message:
            logger.info(f"Found completed checkin flow for guest {guest_id} in conversation {conv.id}")
            return True
    
    return False


def get_guest_latest_flow_state(guest_id: int, flow_type: str = 'checkin') -> Optional[Dict]:
    """
    Get the latest flow state for a guest.
    
    Args:
        guest_id: The guest ID to check
        flow_type: Type of flow to check (default: 'checkin')
    
    Returns:
        Dictionary with latest flow state or None if no flows found
    """
    from chat.models import Message, Conversation
    
    # Get the most recent flow message across all conversations
    latest_flow_message = Message.objects.filter(
        conversation__guest_id=guest_id,
        is_flow=True,
        flow_id=flow_type
    ).order_by('-created_at').first()
    
    if not latest_flow_message:
        return None
    
    # Get all flow messages in this conversation to determine state
    flow_messages = Message.objects.filter(
        conversation=latest_flow_message.conversation,
        is_flow=True,
        flow_id=flow_type
    ).order_by('flow_step')
    
    # Check if flow is completed
    is_completed = any(msg.flow_step >= 999 for msg in flow_messages)
    
    return {
        'conversation_id': latest_flow_message.conversation_id,
        'flow_id': latest_flow_message.flow_id,
        'current_step': latest_flow_message.flow_step,
        'step_success': latest_flow_message.is_flow_step_success,
        'last_activity': latest_flow_message.created_at,
        'is_completed': is_completed,
        'total_steps': flow_messages.count(),
        'is_stale': latest_flow_message.created_at < timezone.now() - timedelta(hours=24)
    }


def reset_guest_incomplete_flows(guest_id: int, flow_type: str = 'checkin') -> int:
    """
    Reset incomplete flows for a guest by marking them as abandoned.
    
    Args:
        guest_id: The guest ID to reset flows for
        flow_type: Type of flow to reset (default: 'checkin')
    
    Returns:
        Number of flows that were reset
    """
    from chat.models import Message
    
    incomplete_flows = get_guest_pending_flows(guest_id, flow_type)
    reset_count = 0
    
    for flow_info in incomplete_flows:
        # Mark the flow as abandoned by adding an abandonment message
        try:
            Message.objects.create(
                conversation_id=flow_info['conversation_id'],
                sender_type='system',
                message_type='system',
                content=f'Check-in flow abandoned due to fresh start',
                is_flow=True,
                flow_id=flow_type,
                flow_step=998,  # Abandonment step
                is_flow_step_success=False
            )
            reset_count += 1
            logger.info(f"Reset incomplete flow for guest {guest_id}, conversation {flow_info['conversation_id']}")
        except Exception as e:
            logger.error(f"Failed to reset flow for guest {guest_id}: {e}")
    
    return reset_count


def start_fresh_checkin_flow(guest_id: int, conversation_id: int, flow_id: str):
    """
    Start a fresh checkin flow by resetting any incomplete flows and creating start message.
    
    Args:
        guest_id: The guest ID starting the flow
        conversation_id: The conversation ID for the flow
        flow_id: Unique identifier for this flow instance
    
    Returns:
        The created flow start message
    """
    from chat.models import Message
    
    # Reset any incomplete flows first
    reset_count = reset_guest_incomplete_flows(guest_id, 'checkin')
    if reset_count > 0:
        logger.info(f"Reset {reset_count} incomplete flows for guest {guest_id}")
    
    # Create flow start message
    start_message = Message.objects.create(
        conversation_id=conversation_id,
        sender_type='system',
        message_type='system',
        content='Check-in flow started',
        is_flow=True,
        flow_id='checkin',
        flow_step=0,  # Start step
        is_flow_step_success=True
    )
    
    logger.info(f"Started fresh checkin flow {flow_id} for guest {guest_id} in conversation {conversation_id}")
    return start_message


def mark_flow_step_completed(conversation_id: int, flow_id: str, step_number: int, 
                           success: bool = True, content: str = None):
    """
    Mark a flow step as completed.
    
    Args:
        conversation_id: The conversation ID
        flow_id: The flow identifier
        step_number: The step number being completed
        success: Whether the step was successful
        content: Optional content for the message
    
    Returns:
        The created flow step message
    """
    from chat.models import Message
    
    step_content = content or f'Check-in flow step {step_number} completed'
    
    message = Message.objects.create(
        conversation_id=conversation_id,
        sender_type='system',
        message_type='system',
        content=step_content,
        is_flow=True,
        flow_id=flow_id,
        flow_step=step_number,
        is_flow_step_success=success
    )
    
    logger.info(f"Marked flow step {step_number} as {success} for conversation {conversation_id}")
    return message


def determine_checkin_guest_status(guest_id: int, whatsapp_number: str) -> str:
    """
    Determine the guest's checkin status based on flow history.
    
    Args:
        guest_id: The guest ID
        whatsapp_number: The guest's WhatsApp number
    
    Returns:
        'new_guest' - No previous checkin attempts or all completed
        'pending_guest' - Has incomplete checkin flow
        'returning_guest' - Has completed checkin before
    """
    # Get latest flow state
    latest_flow = get_guest_latest_flow_state(guest_id, 'checkin')
    
    logger.info(f"determine_checkin_guest_status for guest_id={guest_id}, latest_flow={latest_flow}")
    
    if not latest_flow:
        # No flow history - new guest
        logger.info(f"No flow history for guest {guest_id}, returning 'new_guest'")
        return 'new_guest'
    
    if latest_flow['is_completed']:
        # Has completed flow before - returning guest
        logger.info(f"Guest {guest_id} has completed flow, returning 'returning_guest'")
        return 'returning_guest'
    
    if latest_flow['is_stale']:
        # Incomplete but stale flow - treat as new guest
        logger.info(f"Guest {guest_id} has stale flow, returning 'new_guest'")
        return 'new_guest'
    
    # Active incomplete flow - pending guest
    logger.info(f"Guest {guest_id} has active incomplete flow, returning 'pending_guest'")
    return 'pending_guest'


def get_flow_step_name_mapping() -> Dict[int, str]:
    """
    Get mapping of flow step numbers to human-readable names.
    
    Returns:
        Dictionary mapping step numbers to names
    """
    return {
        0: 'checkin_start',
        1: 'id_type_selection',  # Moved to first step
        2: 'id_upload',
        3: 'id_back_upload', 
        4: 'name',
        5: 'email',
        6: 'dob',
        7: 'nationality',
        8: 'additional_info',
        9: 'aadhar_confirmation',
        10: 'confirmation',
        999: 'checkin_complete',
        998: 'flow_abandoned'
    }