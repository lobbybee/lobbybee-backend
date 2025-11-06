"""
Webhook views for handling incoming messages from various sources.
"""

from .base import (
    views, status, response, AllowAny, User, transaction, timezone,
    async_to_sync, get_channel_layer, normalize_phone_number,
    download_whatsapp_media, GuestMessageSerializer, FlowMessageSerializer, Conversation,
    Message, Guest, Stay, logger, create_response, ContentFile
)
import uuid
import time
from hotel.models import Hotel


class GuestWebhookView(views.APIView):
    """
    Webhook endpoint for receiving messages from guest applications (Service messages only)
    """
    permission_classes = [AllowAny]  # No authentication required for webhook

    def post(self, request):
        logger.info(f"GuestWebhookView: Received webhook request")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Request body: {request.data}")

        try:
            serializer = GuestMessageSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"GuestWebhookView: Serializer validation failed: {serializer.errors}")
                return create_response(
                    {'error': 'Invalid data', 'details': serializer.errors},
                    status.HTTP_400_BAD_REQUEST
                )

            whatsapp_number = normalize_phone_number(serializer.validated_data['whatsapp_number'])
            if not whatsapp_number:
                logger.error(f"GuestWebhookView: Invalid whatsapp number format: {serializer.validated_data['whatsapp_number']}")
                return create_response(
                    {'error': 'Invalid whatsapp number format'},
                    status.HTTP_400_BAD_REQUEST
                )

            message_content = serializer.validated_data['message']
            message_type = serializer.validated_data.get('message_type', 'text')
            media_url = serializer.validated_data.get('media_url')
            media_filename = serializer.validated_data.get('media_filename')
            conversation_id = serializer.validated_data.get('conversation_id')
            department_type = serializer.validated_data.get('department')

            logger.info(f"GuestWebhookView: Parsed data - whatsapp_number={whatsapp_number}, message_type={message_type}, conversation_id={conversation_id}, department={department_type}")

            # Handle WhatsApp media files from webhook
            media_id = request.data.get('media_id')  # WhatsApp media ID from webhook
            media_file = None
            logger.info(f"GuestWebhookView: Checking media - media_id={media_id}, message_type={message_type}")

            if media_id and message_type in ['image', 'document', 'video', 'audio']:
                try:
                    logger.info(f"GuestWebhookView: Attempting to download WhatsApp media {media_id} for message_type: {message_type}")
                    # Download media from WhatsApp
                    media_data = download_whatsapp_media(media_id)
                    logger.info(f"GuestWebhookView: Media download result: {media_data}")

                    if media_data and media_data.get('content'):
                        # Save the downloaded file to a ContentFile
                        media_file = ContentFile(media_data['content'], name=media_data['filename'])
                        # Update message_type based on downloaded file
                        message_type = media_data['message_type']
                        media_filename = media_data['filename']
                        logger.info(f"GuestWebhookView: Successfully downloaded WhatsApp media {media_id} as {message_type}: {media_filename}")
                    else:
                        logger.warning(f"GuestWebhookView: No content received for WhatsApp media {media_id}")
                        media_id = None
                        message_type = 'text'  # Fallback to text if media download fails
                except Exception as e:
                    logger.error(f"GuestWebhookView: Failed to download WhatsApp media {media_id}: {e}", exc_info=True)
                    # Continue without media but log the error
                    media_id = None
                    message_type = 'text'  # Fallback to text if media download fails
            # Also handle case where message_type indicates media but no media_id provided
            elif message_type in ['image', 'document', 'video', 'audio'] and not media_id:
                logger.warning(f"GuestWebhookView: Message type {message_type} but no media_id provided, falling back to text")
                message_type = 'text'

            logger.info(f"GuestWebhookView: Media processing complete - final message_type={message_type}, has_media_file={media_file is not None}")

            # Validate guest exists and has active stay
            try:
                logger.info(f"GuestWebhookView: Looking up guest with whatsapp_number: {whatsapp_number}")
                guest = Guest.objects.get(whatsapp_number=whatsapp_number)
                logger.info(f"GuestWebhookView: Found guest: {guest.id} - {guest.full_name}")

                active_stay = Stay.objects.filter(guest=guest, status='active').first()
                if not active_stay:
                    logger.error(f"GuestWebhookView: Guest {guest.id} has no active stay")
                    return create_response(
                        {'error': 'Guest does not have an active stay'},
                        status.HTTP_400_BAD_REQUEST
                    )
                logger.info(f"GuestWebhookView: Found active stay: {active_stay.id} at hotel {active_stay.hotel.name}")
            except Guest.DoesNotExist:
                logger.error(f"GuestWebhookView: Guest not found with whatsapp_number: {whatsapp_number}")
                return create_response(
                    {'error': 'Guest not found'},
                    status.HTTP_404_NOT_FOUND
                )

            hotel = active_stay.hotel
            logger.info(f"GuestWebhookView: Processing for hotel: {hotel.name}")

            # Always use 'service' as default conversation type
            conversation_type = 'service'
            logger.info(f"GuestWebhookView: Using conversation_type: {conversation_type}")

            # Handle conversation lookup vs creation
            if conversation_id:
                # Use existing conversation
                try:
                    logger.info(f"GuestWebhookView: Looking up existing conversation_id: {conversation_id}")
                    conversation = Conversation.objects.get(
                        id=conversation_id,
                        guest=guest,
                        hotel=hotel,
                        status='active'
                    )
                    department_type = conversation.department
                    logger.info(f"GuestWebhookView: Found existing conversation: {conversation.id} with department: {department_type}")
                except Conversation.DoesNotExist:
                    logger.error(f"GuestWebhookView: Conversation {conversation_id} not found or access denied")
                    return create_response(
                        {'error': 'Conversation not found or access denied'},
                        status.HTTP_404_NOT_FOUND
                    )
            else:
                # Create new conversation - department is required
                if not department_type:
                    logger.error(f"GuestWebhookView: Department is required when creating new conversation, but none provided")
                    return create_response(
                        {'error': 'Department is required when creating new conversation'},
                        status.HTTP_400_BAD_REQUEST
                    )
                logger.info(f"GuestWebhookView: Will create new conversation with department: {department_type}")

            # Handle message creation
            logger.info(f"GuestWebhookView: Starting message creation in transaction")
            with transaction.atomic():
                if conversation_id:
                    # Use existing conversation
                    logger.info(f"GuestWebhookView: Updating existing conversation {conversation.id}")
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
                        logger.info(f"GuestWebhookView: Using existing active conversation {existing_conversation.id}")
                        conversation = existing_conversation
                        conversation.update_last_message(message_content)
                        created = False
                    else:
                        # Create new conversation
                        logger.info(f"GuestWebhookView: Creating new conversation")
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
                        logger.info(f"GuestWebhookView: Created new conversation {conversation.id}")

                # Create message
                logger.info(f"GuestWebhookView: Creating message - type: {message_type}, has_media: {media_file is not None}")
                message = Message.objects.create(
                    conversation=conversation,
                    sender_type='guest',
                    message_type=message_type,
                    content=message_content,
                    media_file=media_file,
                    media_url=media_url,
                    media_filename=media_filename
                )
                logger.info(f"GuestWebhookView: Created message {message.id} successfully")

            # Broadcast message to department staff via WebSocket
            try:
                logger.info(f"GuestWebhookView: Broadcasting message to department group: {department_type}")
                channel_layer = get_channel_layer()
                department_group_name = f"department_{department_type}"

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

                logger.info(f"GuestWebhookView: Sending to WebSocket group: {department_group_name}")
                async_to_sync(channel_layer.group_send)(
                    department_group_name,
                    {
                        'type': 'chat_message',
                        'message': message_data
                    }
                )
                logger.info(f"GuestWebhookView: WebSocket broadcast completed successfully")
            except Exception as ws_error:
                logger.error(f"GuestWebhookView: Failed to broadcast to WebSocket: {ws_error}", exc_info=True)
                # Continue anyway - message was created successfully

            response_data = {
                'success': True,
                'message_id': message.id,
                'conversation_id': conversation.id,
                'department': department_type,
                'conversation_type': conversation_type,
                'conversation_created': created if not conversation_id else False
            }
            logger.info(f"GuestWebhookView: Successfully processed webhook - {response_data}")
            return create_response(response_data, status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"GuestWebhookView: Internal server error: {e}", exc_info=True)
            return create_response(
                {'error': 'Internal server error', 'details': str(e)},
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FlowWebhookView(views.APIView):
    """
    Simplified webhook endpoint for processing flow messages.
    Handles:
    1. Hotel validation flow (for /checkin-{hotel_id} commands) - SAVES messages
    2. Check-in flow (if check-in keywords detected) - SAVES messages and media files
    3. General response (for all other messages) - DOES NOT save messages
    
    Only saves messages that are part of flows or media files during flow processing.
    """
    permission_classes = [AllowAny]  # No authentication required for webhook

    def post(self, request):
        """
        Process flow messages with simple logic:
        - Check-in keywords → Check-in flow
        - Everything else → General response with media saving
        """
        logger.info(f"FlowWebhookView: Received webhook request")
        logger.info(f"Request body: {request.data}")

        try:
            # Validate incoming data
            serializer = FlowMessageSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"FlowWebhookView: Serializer validation failed: {serializer.errors}")
                return create_response(
                    {'error': 'Invalid data', 'details': serializer.errors},
                    status.HTTP_400_BAD_REQUEST
                )

            # Extract validated data
            whatsapp_number = normalize_phone_number(serializer.validated_data['whatsapp_number'])
            if not whatsapp_number:
                logger.error(f"FlowWebhookView: Invalid whatsapp number format")
                return create_response(
                    {'error': 'Invalid whatsapp number format'},
                    status.HTTP_400_BAD_REQUEST
                )

            message_content = serializer.validated_data['message']
            message_type = serializer.validated_data.get('message_type', 'text')
            flow_id = serializer.validated_data.get('flow_id', f"flow_{uuid.uuid4().hex[:12]}_{int(time.time())}")

            logger.info(f"FlowWebhookView: Processing message from {whatsapp_number}: {message_content[:50]}...")

            # Validate guest exists
            try:
                guest = Guest.objects.get(whatsapp_number=whatsapp_number)
                logger.info(f"FlowWebhookView: Found guest: {guest.id} - {guest.full_name}")
            except Guest.DoesNotExist:
                logger.error(f"FlowWebhookView: Guest not found with whatsapp_number: {whatsapp_number}")
                return create_response(
                    {'error': 'Guest not found'},
                    status.HTTP_404_NOT_FOUND
                )

            # Handle media processing
            media_id = request.data.get('media_id')
            media_file = None
            media_filename = None

            if media_id and message_type in ['image', 'document', 'video', 'audio']:
                try:
                    media_data = download_whatsapp_media(media_id)
                    if media_data and media_data.get('content'):
                        media_file = ContentFile(media_data['content'], name=media_data['filename'])
                        message_type = media_data['message_type']
                        media_filename = media_data['filename']
                        logger.info(f"FlowWebhookView: Downloaded media {media_id} as {message_type}")
                except Exception as e:
                    logger.error(f"FlowWebhookView: Failed to download media {media_id}: {e}")
                    message_type = 'text'

            # Check flow type based on message content
            message_lower = message_content.lower().strip()
            
            # Check for hotel ID validation command: /checkin-{hotel_id}
            if message_lower.startswith('/checkin-'):
                # Process hotel validation flow
                logger.info(f"FlowWebhookView: Processing hotel validation flow")
                flow_result = self._process_hotel_validation_flow(
                    flow_id=flow_id,
                    guest=guest,
                    message_content=message_content,
                    message_type=message_type,
                    media_file=media_file,
                    media_filename=media_filename
                )
            else:
                # Check for regular check-in keywords
                checkin_keywords = ['checkin', 'check in', 'check-in', 'check me in', 'check in please']
                is_checkin_request = any(keyword in message_lower for keyword in checkin_keywords)

                if is_checkin_request:
                    # Process through check-in flow
                    logger.info(f"FlowWebhookView: Processing check-in flow")
                    flow_result = self._process_checkin_flow(
                        flow_id=flow_id,
                        guest=guest,
                        message_content=message_content,
                        message_type=message_type,
                        media_file=media_file,
                        media_filename=media_filename,
                        request_data=request.data
                    )
                else:
                    # Save message and give general response
                    logger.info(f"FlowWebhookView: Processing general message")
                    flow_result = self._process_general_message(
                        flow_id=flow_id,
                        guest=guest,
                        message_content=message_content,
                        message_type=message_type,
                        media_file=media_file,
                        media_filename=media_filename
                    )

            return create_response(flow_result, status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"FlowWebhookView: Internal server error: {e}", exc_info=True)
            return create_response(
                {'error': 'Internal server error', 'details': str(e)},
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_general_message(self, flow_id, guest, message_content, message_type, media_file, media_filename):
        """
        Provide a simple response for non-flow messages without saving them
        """
        try:
            # Don't save messages that don't match any flow conditions
            # Just provide a simple response
            logger.info(f"FlowWebhookView: Non-flow message received, not saving: {message_content[:50]}...")
            
            # Simple general response
            response_text = "Thank you for your message! Our team will get back to you shortly."

            return {
                'success': True,
                'flow_id': flow_id,
                'flow_type': 'general',
                'step_id': 'message_received',
                'response': {
                    'response_type': 'text',
                    'text': response_text,
                },
                'status': 'completed',
                'is_complete': True,
                'message_saved': False,  # Indicate that message was not saved
            }

        except Exception as e:
            logger.error(f"FlowWebhookView: Error processing general message: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'general_message_error',
                'message': 'Error processing message',
                'flow_id': flow_id,
                'details': str(e)
            }

    def _process_hotel_validation_flow(self, flow_id, guest, message_content, message_type, media_file, media_filename):
        """
        Process hotel ID validation command: /checkin-{hotel_id}
        Validates hotel exists and then initiates check-in flow
        """
        try:
            # Extract hotel ID from message
            message_parts = message_content.strip().split()
            if len(message_parts) < 1:
                return {
                    'success': False,
                    'error': 'invalid_hotel_id_format',
                    'message': 'Please use the format: /checkin-{hotel_id}',
                    'flow_id': flow_id,
                    'flow_type': 'hotel_validation',
                    'details': 'Missing hotel ID parameter'
                }

            # Extract hotel_id from /checkin-{hotel_id} format
            hotel_command = message_parts[0]
            if not hotel_command.startswith('/checkin-') or len(hotel_command) <= 9:
                return {
                    'success': False,
                    'error': 'invalid_hotel_id_format',
                    'message': 'Please use the format: /checkin-{hotel_id}',
                    'flow_id': flow_id,
                    'flow_type': 'hotel_validation',
                    'details': 'Invalid hotel ID format'
                }

            hotel_id = hotel_command[9:]  # Remove '/checkin-' prefix
            logger.info(f"FlowWebhookView: Validating hotel ID: {hotel_id}")

            # Validate hotel ID and get hotel name
            try:
                hotel = Hotel.objects.get(id=hotel_id)
                hotel_name = hotel.name
                logger.info(f"FlowWebhookView: Found hotel: {hotel_name}")
            except Hotel.DoesNotExist:
                return {
                    'success': False,
                    'error': 'hotel_not_found',
                    'message': f'Hotel with ID {hotel_id} not found',
                    'flow_id': flow_id,
                    'flow_type': 'hotel_validation',
                    'details': f'No hotel found with ID {hotel_id}'
                }

            # Check if guest has an existing active stay at this hotel
            active_stay = Stay.objects.filter(
                guest=guest,
                hotel=hotel,
                status='active'
            ).first()

            if active_stay:
                response_text = f"You already have an active stay at {hotel.name} in room {active_stay.room.room_number}. How can we assist you?"
                return {
                    'success': True,
                    'flow_id': flow_id,
                    'flow_type': 'hotel_validation',
                    'step_id': 'existing_stay',
                    'response': {
                        'response_type': 'text',
                        'text': response_text,
                    },
                    'status': 'completed',
                    'is_complete': True,
                }

            # No existing stay - initiate check-in flow
            logger.info(f"FlowWebhookView: No existing stay found for guest {guest.id} at hotel {hotel.name}, initiating check-in flow")

            # Save the hotel validation message
            self._save_flow_message(
                guest=guest,
                message_content=message_content,
                message_type=message_type,
                media_file=media_file,
                media_filename=media_filename,
                flow_id=flow_id,
                flow_type='hotel_validation',
                flow_step='hotel_validated',
                flow_success=True,
                flow_data={'hotel_id': hotel_id, 'hotel_name': hotel.name}
            )

            # Initiate check-in flow with hotel context
            checkin_flow_result = self._process_checkin_flow(
                flow_id=f"checkin_{uuid.uuid4().hex[:12]}_{int(time.time())}",
                guest=guest,
                message_content="start_checkin",  # Trigger check-in flow
                message_type='text',
                media_file=None,
                media_filename=None,
                request_data={
                    'hotel_id': hotel_id,
                    'hotel_name': hotel_name,
                    'initiated_from': 'hotel_validation'
                }
            )

            # Return success with check-in flow initiation
            return {
                'success': True,
                'flow_id': flow_id,
                'flow_type': 'hotel_validation',
                'step_id': 'hotel_validated',
                'response': {
                    'response_type': 'text',
                    'text': f"Welcome to {hotel.name}! Let's start your check-in process.",
                },
                'status': 'completed',
                'is_complete': True,
                'next_flow': checkin_flow_result,  # Include check-in flow result
            }

        except Exception as e:
            logger.error(f"FlowWebhookView: Hotel validation flow error: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'hotel_validation_error',
                'message': 'Error in hotel validation flow processing',
                'flow_id': flow_id,
                'flow_type': 'hotel_validation',
                'details': str(e)
            }

    def _process_checkin_flow(self, flow_id, guest, message_content, message_type, media_file, media_filename, request_data):
        """
        Process check-in flow using existing checkin_flow.py logic
        """
        try:
            from ..flows.checkin_flow import check_in_flow

            # Prepare data for check_in_flow function
            incoming_data = {
                'message': message_content,
                'message_type': message_type,
                'media_data': media_file.read() if media_file else None,
            }

            # Get previous flow state if provided
            previous_flow_message = request_data.get('previous_flow_message')

            # Process through check-in flow
            flow_result = check_in_flow(
                flow_id=flow_id,
                incoming_data=incoming_data,
                previous_flow_message=previous_flow_message
            )

            # Save message with flow metadata
            self._save_flow_message(
                guest=guest,
                message_content=message_content,
                message_type=message_type,
                media_file=media_file,
                media_filename=media_filename,
                flow_id=flow_id,
                flow_type='checkin',
                flow_step=flow_result.get('step_id'),
                flow_success=flow_result.get('status') != 'error',
                flow_data=flow_result.get('flow_data', {})
            )

            # Return standardized flow response
            return {
                'success': True,
                'flow_id': flow_id,
                'flow_type': 'checkin',
                'step_id': flow_result.get('step_id'),
                'response': flow_result.get('response'),
                'status': flow_result.get('status'),
                'next_action': flow_result.get('next_action'),
                'flow_data': flow_result.get('flow_data'),
                'requires_input': flow_result.get('next_action') in ['await_user_input', 'await_media_upload'],
                'is_complete': flow_result.get('status') == 'completed',
            }

        except Exception as e:
            logger.error(f"FlowWebhookView: Check-in flow error: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'checkin_flow_error',
                'message': 'Error in check-in flow processing',
                'flow_id': flow_id,
                'flow_type': 'checkin',
                'details': str(e)
            }

    def _save_flow_message(self, guest, message_content, message_type, media_file, media_filename, flow_id, flow_type, flow_step, flow_success, flow_data):
        """
        Save a flow message to the database for logging and tracking purposes
        """
        try:
            # Find or create a conversation for this guest and hotel
            # For flow messages, we don't need a specific department
            conversation = None
            
            # Try to find existing conversation for this guest
            active_stay = Stay.objects.filter(guest=guest, status='active').first()
            if active_stay:
                conversation = Conversation.objects.filter(
                    guest=guest,
                    hotel=active_stay.hotel
                ).first()
            
            # Create conversation if not found
            if not conversation:
                if active_stay:
                    conversation = Conversation.objects.create(
                        guest=guest,
                        hotel=active_stay.hotel,
                        department='Reception',  # Default department
                        status='active'
                    )
                else:
                    # If no active stay, don't create conversation - just log the flow message
                    logger.info(f"FlowWebhookView: No active stay for guest {guest.id}, skipping message creation")
                    return None

            # Create message record
            message = Message.objects.create(
                conversation=conversation,
                sender_type='guest',
                sender=None,  # Guest message - no specific sender
                message_type=message_type,
                content=message_content,
                media_file=media_file,
                media_filename=media_filename,

                # Flow-specific fields
                is_flow=True,
                flow_id=flow_id,
                flow_step=flow_step,
                is_flow_step_success=flow_success,
            )

            logger.info(f"FlowWebhookView: Saved flow message {message.id} for flow {flow_id}")
            return message

        except Exception as e:
            logger.error(f"FlowWebhookView: Error saving flow message: {e}", exc_info=True)
            # Continue processing even if message saving fails
            return None