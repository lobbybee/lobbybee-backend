"""
Webhook deduplication utilities for preventing duplicate processing
"""

import time
from django.db import transaction
from ..models import WebhookAttempt
import logging

logger = logging.getLogger(__name__)


def check_and_create_webhook_attempt(webhook_type, whatsapp_message_id, whatsapp_number, request_data):
    """
    Check if webhook attempt exists and create a new one if not
    
    Args:
        webhook_type: Type of webhook ('guest', 'flow', 'outgoing')
        whatsapp_message_id: WhatsApp message ID (can be None for outgoing)
        whatsapp_number: Phone number
        request_data: Request data for debugging
        
    Returns:
        Tuple of (webhook_attempt, is_duplicate, is_new)
        - webhook_attempt: WebhookAttempt instance
        - is_duplicate: Boolean indicating if this is a duplicate
        - is_new: Boolean indicating if this is a new attempt
    """
    try:
        with transaction.atomic():
            # Check if attempt already exists
            existing_attempt = WebhookAttempt.objects.filter(
                webhook_type=webhook_type,
                whatsapp_message_id=whatsapp_message_id
            ).first()
            
            if existing_attempt:
                logger.info(f"Webhook deduplication: Found existing attempt for {webhook_type} - {whatsapp_message_id}")
                return existing_attempt, True, False
            
            # Create new attempt
            webhook_attempt = WebhookAttempt.objects.create(
                webhook_type=webhook_type,
                whatsapp_message_id=whatsapp_message_id,
                whatsapp_number=whatsapp_number,
                status='processing',
                request_data=request_data
            )
            
            logger.info(f"Webhook deduplication: Created new attempt for {webhook_type} - {whatsapp_message_id}")
            return webhook_attempt, False, True
            
    except Exception as e:
        logger.error(f"Webhook deduplication error: {e}")
        # Return a fake attempt to avoid breaking the flow
        return None, False, False


def update_webhook_attempt(webhook_attempt, status, response_data=None, error_message=None, 
                          message_id=None, conversation_id=None, processing_time_ms=None):
    """
    Update webhook attempt with results
    
    Args:
        webhook_attempt: WebhookAttempt instance
        status: New status
        response_data: Response data for debugging
        error_message: Error message if failed
        message_id: Created message ID if successful
        conversation_id: Related conversation ID
        processing_time_ms: Processing time in milliseconds
    """
    if not webhook_attempt:
        return
        
    try:
        update_fields = ['status', 'updated_at']
        
        webhook_attempt.status = status
        
        if response_data is not None:
            webhook_attempt.response_data = response_data
            update_fields.append('response_data')
            
        if error_message is not None:
            webhook_attempt.error_message = error_message
            update_fields.append('error_message')
            
        if message_id is not None:
            webhook_attempt.message_id = message_id
            update_fields.append('message_id')
            
        if conversation_id is not None:
            webhook_attempt.conversation_id = conversation_id
            update_fields.append('conversation_id')
            
        if processing_time_ms is not None:
            webhook_attempt.processing_time_ms = processing_time_ms
            update_fields.append('processing_time_ms')
            
        webhook_attempt.save(update_fields=update_fields)
        
    except Exception as e:
        logger.error(f"Error updating webhook attempt: {e}")


def create_outgoing_webhook_attempt(webhook_type, message_content, whatsapp_number, message_id=None, conversation_id=None):
    """
    Create a webhook attempt for outgoing messages
    
    Args:
        webhook_type: Type of webhook ('outgoing')
        message_content: Content of the message
        whatsapp_number: Recipient phone number
        message_id: Created message ID
        conversation_id: Related conversation ID
        
    Returns:
        WebhookAttempt instance
    """
    try:
        # Generate a synthetic message ID for outgoing messages
        synthetic_message_id = f"outgoing_{int(time.time())}_{message_id or 'unknown'}"
        
        webhook_attempt = WebhookAttempt.objects.create(
            webhook_type=webhook_type,
            whatsapp_message_id=synthetic_message_id,
            whatsapp_number=whatsapp_number,
            status='success',
            request_data={'message_content': message_content},
            message_id=message_id,
            conversation_id=conversation_id
        )
        
        logger.info(f"Created outgoing webhook attempt: {synthetic_message_id}")
        return webhook_attempt
        
    except Exception as e:
        logger.error(f"Error creating outgoing webhook attempt: {e}")
        return None


def is_duplicate_outgoing_message(message_content, whatsapp_number, time_window_seconds=30):
    """
    Check if an outgoing message is a duplicate within a time window
    
    Args:
        message_content: Content of the message
        whatsapp_number: Recipient phone number
        time_window_seconds: Time window to check for duplicates
        
    Returns:
        Boolean indicating if this is a duplicate
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(seconds=time_window_seconds)
        
        recent_attempts = WebhookAttempt.objects.filter(
            webhook_type='outgoing',
            whatsapp_number=whatsapp_number,
            status='success',
            created_at__gte=cutoff_time
        )
        
        for attempt in recent_attempts:
            request_data = attempt.request_data or {}
            if request_data.get('message_content') == message_content:
                logger.info(f"Found duplicate outgoing message to {whatsapp_number}: {message_content[:50]}...")
                return True
                
        return False
        
    except Exception as e:
        logger.error(f"Error checking duplicate outgoing message: {e}")
        return False