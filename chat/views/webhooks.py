"""
Webhook views for handling incoming messages from various sources.
"""

from .base import (
    views, status, response, AllowAny, User, transaction, timezone,
    async_to_sync, get_channel_layer, normalize_phone_number,
    download_whatsapp_media, GuestMessageSerializer, FlowMessageSerializer, Conversation,
    Message, Guest, Stay, logger, create_response, ContentFile
)
from ..consumers import notify_new_conversation_to_department
from ..utils.whatsapp_payload_utils import convert_flow_response_to_whatsapp_payload
from ..utils.webhook_deduplication import (
    check_and_create_webhook_attempt,
    update_webhook_attempt
)
import uuid
import time
from hotel.models import Hotel


def process_guest_webhook(request_data, request_headers=None, media_id=None):
    """
    Function to process guest webhook requests.
    Same logic as GuestWebhookView.post() but callable directly.
    Note: Deduplication is handled at the view level (GuestConversationTypeView).

    Args:
        request_data: The request data/payload
        request_headers: Optional request headers for logging
        media_id: Optional WhatsApp media ID

    Returns:
        Tuple of (response_data, status_code)
    """
    start_time = time.time()

    if request_headers:
        logger.info(f"process_guest_webhook: Request headers: {dict(request_headers)}")
    logger.info(f"process_guest_webhook: Request body: {request_data}")

    # NOTE: Deduplication is handled at the view level (GuestConversationTypeView)
    # This function processes the message directly without duplicate checking

    try:
        serializer = GuestMessageSerializer(data=request_data)
        if not serializer.is_valid():
            error_msg = f"process_guest_webhook: Serializer validation failed: {serializer.errors}"
            logger.error(error_msg)
            return (
                {'error': 'Invalid data', 'details': serializer.errors},
                status.HTTP_400_BAD_REQUEST
            )

        whatsapp_number = normalize_phone_number(serializer.validated_data['whatsapp_number'])
        if not whatsapp_number:
            error_msg = f"process_guest_webhook: Invalid whatsapp number format: {serializer.validated_data['whatsapp_number']}"
            logger.error(error_msg)
            return (
                {'error': 'Invalid whatsapp number format'},
                status.HTTP_400_BAD_REQUEST
            )

        message_content = serializer.validated_data['message']
        message_type = serializer.validated_data.get('message_type', 'text')
        media_url = serializer.validated_data.get('media_url')
        media_filename = serializer.validated_data.get('media_filename')
        conversation_id = serializer.validated_data.get('conversation_id')
        department_type = serializer.validated_data.get('department')

        logger.info(f"process_guest_webhook: Parsed data - whatsapp_number={whatsapp_number}, message_type={message_type}, conversation_id={conversation_id}, department={department_type}")

        # Handle WhatsApp media files from webhook
        provided_media_id = media_id or request_data.get('media_id')
        media_file = None
        logger.info(f"process_guest_webhook: Checking media - media_id={provided_media_id}, message_type={message_type}")

        if provided_media_id and message_type in ['image', 'document', 'video', 'audio']:
            try:
                logger.info(f"process_guest_webhook: Attempting to download WhatsApp media {provided_media_id} for message_type: {message_type}")
                # Download media from WhatsApp
                media_data = download_whatsapp_media(provided_media_id)
                logger.info(f"process_guest_webhook: Media download result: {media_data}")

                if media_data and media_data.get('content'):
                    # Save the downloaded file to a ContentFile
                    media_file = ContentFile(media_data['content'], name=media_data['filename'])
                    # Update message_type based on downloaded file
                    message_type = media_data['message_type']
                    media_filename = media_data['filename']
                    logger.info(f"process_guest_webhook: Successfully downloaded WhatsApp media {provided_media_id} as {message_type}: {media_filename}")
                else:
                    logger.warning(f"process_guest_webhook: No content received for WhatsApp media {provided_media_id}")
                    provided_media_id = None
                    message_type = 'text'  # Fallback to text if media download fails
            except Exception as e:
                logger.error(f"process_guest_webhook: Failed to download WhatsApp media {provided_media_id}: {e}", exc_info=True)
                # Continue without media but log the error
                provided_media_id = None
                message_type = 'text'  # Fallback to text if media download fails
        # Also handle case where message_type indicates media but no media_id provided
        elif message_type in ['image', 'document', 'video', 'audio'] and not provided_media_id:
            logger.warning(f"process_guest_webhook: Message type {message_type} but no media_id provided, falling back to text")
            message_type = 'text'

        logger.info(f"process_guest_webhook: Media processing complete - final message_type={message_type}, has_media_file={media_file is not None}")

        # Validate guest exists and has active stay
        try:
            logger.info(f"process_guest_webhook: Looking up guest with whatsapp_number: {whatsapp_number}")
            guest = Guest.objects.get(whatsapp_number=whatsapp_number)
            logger.info(f"process_guest_webhook: Found guest: {guest.id} - {guest.full_name}")

            active_stay = Stay.objects.filter(guest=guest, status='active').first()
            if not active_stay:
                logger.error(f"process_guest_webhook: Guest {guest.id} has no active stay")
                return (
                    {'error': 'Guest does not have an active stay'},
                    status.HTTP_400_BAD_REQUEST
                )
            logger.info(f"process_guest_webhook: Found active stay: {active_stay.id} at hotel {active_stay.hotel.name}")
        except Guest.DoesNotExist:
            logger.error(f"process_guest_webhook: Guest not found with whatsapp_number: {whatsapp_number}")
            return (
                {'error': 'Guest not found'},
                status.HTTP_404_NOT_FOUND
            )

        hotel = active_stay.hotel
        logger.info(f"process_guest_webhook: Processing for hotel: {hotel.name}")

        # Always use 'service' as default conversation type
        conversation_type = 'service'
        logger.info(f"process_guest_webhook: Using conversation_type: {conversation_type}")

        # Handle conversation lookup vs creation
        if conversation_id:
            # Use existing conversation
            try:
                logger.info(f"process_guest_webhook: Looking up existing conversation_id: {conversation_id}")
                conversation = Conversation.objects.get(
                    id=conversation_id,
                    guest=guest,
                    hotel=hotel,
                    status='active'
                )
                department_type = conversation.department
                logger.info(f"process_guest_webhook: Found existing conversation: {conversation.id} with department: {department_type}")
            except Conversation.DoesNotExist:
                logger.error(f"process_guest_webhook: Conversation {conversation_id} not found or access denied")
                return (
                    {'error': 'Conversation not found or access denied'},
                    status.HTTP_404_NOT_FOUND
                )
        else:
            # Create new conversation - department is required
            if not department_type:
                logger.error(f"process_guest_webhook: Department is required when creating new conversation, but none provided")
                return (
                    {'error': 'Department is required when creating new conversation'},
                    status.HTTP_400_BAD_REQUEST
                )
            logger.info(f"process_guest_webhook: Will create new conversation with department: {department_type}")

        # Handle message creation
        logger.info(f"process_guest_webhook: Starting message creation in transaction")
        with transaction.atomic():
            if conversation_id:
                # Use existing conversation
                logger.info(f"process_guest_webhook: Updating existing conversation {conversation.id}")
                conversation.update_last_message(message_content)
                created = False
            else:
                # Check if there's an existing active conversation with the same department
                existing_conversation = Conversation.objects.filter(
                    guest=guest,
                    hotel=hotel,
                    department=department_type,
                    conversation_type=conversation_type,
                    status='active'
                ).first()

                if existing_conversation:
                    # Use existing conversation instead of creating new one
                    logger.info(f"process_guest_webhook: Using existing active conversation {existing_conversation.id}")
                    conversation = existing_conversation

                    # Check if user is returning after being away (30 minutes threshold)
                    time_threshold = timezone.now() - timezone.timedelta(minutes=30)
                    is_returning_user = (
                        conversation.last_message_at and
                        conversation.last_message_at < time_threshold
                    )

                    if is_returning_user:
                        logger.info(f"process_guest_webhook: User is returning after {timezone.now() - conversation.last_message_at}")
                        # Create a service message to notify staff that user is back online
                        try:
                            guest_display_name = guest.full_name or 'Guest'
                            return_message = Message.objects.create(
                                conversation=conversation,
                                sender_type='staff',
                                content=f"{guest_display_name} is back online",
                                message_type='system'
                            )
                            logger.info(f"process_guest_webhook: Created 'User is back online' service message {return_message.id}")

                            # Broadcast the service message to staff first
                            try:
                                channel_layer = get_channel_layer()
                                department_group_name = f"department_{conversation.department.lower()}"

                                service_message_data = {
                                    'id': return_message.id,
                                    'conversation_id': conversation.id,
                                    'sender_type': 'staff',
                                    'sender_name': 'System',
                                    'sender_id': None,
                                    'message_type': return_message.message_type,
                                    'content': return_message.content,
                                    'media_url': return_message.get_media_url,
                                    'media_filename': return_message.media_filename,
                                    'is_read': return_message.is_read,
                                    'created_at': return_message.created_at.isoformat(),
                                    'updated_at': return_message.updated_at.isoformat(),
                                    'guest_info': {
                                        'id': guest.id,
                                        'name': guest.full_name,
                                        'whatsapp_number': guest.whatsapp_number,
                                        'room_number': active_stay.room.room_number if active_stay else None
                                    }
                                }

                                async_to_sync(channel_layer.group_send)(
                                    department_group_name,
                                    {
                                        'type': 'chat_message',
                                        'message': service_message_data
                                    }
                                )
                                logger.info(f"process_guest_webhook: Broadcasted 'User is back online' service message")
                            except Exception as ws_error:
                                logger.error(f"process_guest_webhook: Failed to broadcast service message: {ws_error}", exc_info=True)
                        except Exception as e:
                            logger.error(f"process_guest_webhook: Failed to create 'User is back online' service message: {e}", exc_info=True)

                    # Now update the conversation with the actual user message
                    conversation.update_last_message(message_content)
                    created = False
                else:
                    # Create new conversation
                    logger.info(f"process_guest_webhook: Creating new conversation")
                    conversation = Conversation.objects.create(
                        guest=guest,
                        hotel=hotel,
                        department=department_type,
                        conversation_type=conversation_type,
                        status='active',
                        last_message_at=timezone.now(),
                        last_message_preview=message_content[:255]
                    )
                    created = True
                    logger.info(f"process_guest_webhook: Created new conversation {conversation.id}")

                    # Notify department staff about new conversation
                    try:
                        channel_layer = get_channel_layer()

                        conversation_data = {
                            'id': conversation.id,
                            'guest_name': conversation.guest.full_name,
                            'department': conversation.department.lower(),
                            'conversation_type': conversation.conversation_type,
                            'status': conversation.status,
                            'created_at': conversation.created_at.isoformat(),
                            'last_message_preview': conversation.last_message_preview,
                            'last_message_at': conversation.last_message_at.isoformat() if conversation.last_message_at else None
                        }

                        relevant_group = f"department_{conversation.department.lower()}"

                        async_to_sync(channel_layer.group_send)(
                            relevant_group,
                            {
                                'type': 'new_conversation_notification',
                                'notification': {
                                    'type': 'new_conversation',
                                    'data': conversation_data
                                }
                            }
                        )
                        logger.info(f"process_guest_webhook: Sent new conversation notification for conversation {conversation.id}")
                    except Exception as notify_error:
                        logger.error(f"process_guest_webhook: Failed to send new conversation notification: {notify_error}", exc_info=True)

            # Create message
            logger.info(f"process_guest_webhook: Creating message - type: {message_type}, has_media: {media_file is not None}")

            # Prepare message creation data
            message_data = {
                'conversation': conversation,
                'sender_type': 'guest',
                'message_type': message_type,
                'content': message_content,
                'media_file': media_file,
                'media_url': media_url,
                'media_filename': media_filename,
            }

            # Add WhatsApp message ID if it exists (for incoming guest messages)
            whatsapp_message_id = request_data.get('whatsapp_message_id')
            if whatsapp_message_id:
                message_data['whatsapp_message_id'] = whatsapp_message_id
                logger.info(f"process_guest_webhook: Creating message with WhatsApp ID {whatsapp_message_id}")

            message = Message.objects.create(**message_data)
            logger.info(f"process_guest_webhook: Created message {message.id} successfully")

        # Broadcast message to department staff via WebSocket
        try:
            logger.info(f"process_guest_webhook: Broadcasting message to department group: {department_type}")
            channel_layer = get_channel_layer()
            department_group_name = f"department_{department_type.lower()}"

            message_data = {
                'id': message.id,
                'conversation_id': conversation.id,
                'sender_type': 'guest',
                'sender_name': guest.full_name or 'Guest',
                'sender_id': None,
                'message_type': message.message_type,
                'content': message.content,
                'media_url': message.get_media_url,
                'media_filename': message.media_filename,
                'is_read': message.is_read,
                'created_at': message.created_at.isoformat(),
                'updated_at': message.updated_at.isoformat(),
                'guest_info': {
                    'id': guest.id,
                    'name': guest.full_name,
                    'whatsapp_number': guest.whatsapp_number,
                    'room_number': active_stay.room.room_number if active_stay else None
                }
            }

            logger.info(f"process_guest_webhook: Sending to WebSocket group: {department_group_name}")
            async_to_sync(channel_layer.group_send)(
                department_group_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )
            logger.info(f"process_guest_webhook: WebSocket broadcast completed successfully")
        except Exception as ws_error:
            logger.error(f"process_guest_webhook: Failed to broadcast to WebSocket: {ws_error}", exc_info=True)
            # Continue anyway - message was created successfully

        response_data = {
            'success': True,
            'message_id': message.id,
            'conversation_id': conversation.id,
            'department': department_type,
            'conversation_type': conversation_type,
            'conversation_created': created if not conversation_id else False
        }
        logger.info(f"process_guest_webhook: Successfully processed webhook - {response_data}")

        return (response_data, status.HTTP_201_CREATED)

    except Exception as e:
        error_msg = f"process_guest_webhook: Internal server error: {e}"
        logger.error(error_msg, exc_info=True)

        return (
            {'error': 'Internal server error', 'details': str(e)},
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )
