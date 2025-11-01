"""
Webhook views for handling incoming messages from various sources.
"""

from .base import (
    views, status, response, AllowAny, User, transaction, timezone,
    async_to_sync, get_channel_layer, normalize_phone_number,
    download_whatsapp_media, GuestMessageSerializer, Conversation, 
    Message, Guest, Stay, logger, create_response
)


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
    Webhook endpoint for processing non-service messages through flows
    """
    permission_classes = [AllowAny]  # No authentication required for webhook

    def post(self, request):
        """
        Process non-service messages through appropriate flows
        
        Handles:
        - Check-in flow
        - General conversation flow
        - Demo flow
        - Other custom flows
        """
        logger.info(f"FlowWebhookView: Received webhook request")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Request body: {request.data}")
        
        try:
            # Validate incoming data
            serializer = GuestMessageSerializer(data=request.data)
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
            media_url = serializer.validated_data.get('media_url')
            media_filename = serializer.validated_data.get('media_filename')
            
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

            # Determine flow type
            flow_type = self._detect_flow_type(request.data, message_content, guest)
            logger.info(f"FlowWebhookView: Detected flow type: {flow_type}")

            # Handle media processing similar to GuestWebhookView
            media_id = request.data.get('media_id')
            media_file = None
            
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

            # Process through appropriate flow handler
            flow_result = self._process_flow(
                flow_type=flow_type,
                guest=guest,
                message_content=message_content,
                message_type=message_type,
                media_file=media_file,
                media_filename=media_filename,
                request_data=request.data
            )

            return create_response(flow_result, status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"FlowWebhookView: Internal server error: {e}", exc_info=True)
            return create_response(
                {'error': 'Internal server error', 'details': str(e)},
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _detect_flow_type(self, request_data, message_content, guest):
        """
        Determine which flow should handle this message
        """
        # Check for explicit flow_type parameter
        explicit_flow_type = request_data.get('flow_type')
        if explicit_flow_type and explicit_flow_type != 'service':
            return explicit_flow_type
        
        # Check for check-in keywords
        checkin_keywords = ['checkin', 'check in', 'check-in', 'check me in', 'check in please']
        message_lower = message_content.lower().strip()
        
        if any(keyword in message_lower for keyword in checkin_keywords):
            return 'checkin'
        
        # Check guest context
        active_stay = Stay.objects.filter(guest=guest, status='active').first()
        if active_stay:
            return 'checked_in'  # Guest is already checked in
        else:
            return 'general'  # Default for general conversation

    def _process_flow(self, flow_type, guest, message_content, message_type, media_file, media_filename, request_data):
        """
        Process message through the appropriate flow handler
        """
        # Generate flow ID if not provided
        flow_id = request_data.get('flow_id') or f"flow_{uuid.uuid4().hex[:12]}_{int(time.time())}"
        
        try:
            if flow_type == 'checkin':
                return self._process_checkin_flow(
                    flow_id, guest, message_content, message_type, 
                    media_file, media_filename, request_data
                )
            elif flow_type == 'general':
                return self._process_general_flow(
                    flow_id, guest, message_content, message_type,
                    media_file, media_filename, request_data
                )
            elif flow_type == 'checked_in':
                return self._process_checkedin_flow(
                    flow_id, guest, message_content, message_type,
                    media_file, media_filename, request_data
                )
            else:
                # Default to general flow for unknown types
                logger.warning(f"FlowWebhookView: Unknown flow type '{flow_type}', defaulting to general")
                return self._process_general_flow(
                    flow_id, guest, message_content, message_type,
                    media_file, media_filename, request_data
                )
                
        except Exception as e:
            logger.error(f"FlowWebhookView: Error processing {flow_type} flow: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'flow_processing_error',
                'message': f'Error processing {flow_type} flow',
                'flow_id': flow_id,
                'flow_type': flow_type,
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

    def _process_general_flow(self, flow_id, guest, message_content, message_type, media_file, media_filename, request_data):
        """
        Process general conversation flow
        """
        try:
            # For general flow, we just save the message and create a simple response
            self._save_flow_message(
                guest=guest,
                message_content=message_content,
                message_type=message_type,
                media_file=media_file,
                media_filename=media_filename,
                flow_id=flow_id,
                flow_type='general',
                flow_step='message_received',
                flow_success=True,
                flow_data={}
            )
            
            # Simple auto-response for general messages
            response_text = f"Thank you for your message, {guest.full_name or 'Guest'}! Our team will get back to you shortly."
            
            return {
                'success': True,
                'flow_id': flow_id,
                'flow_type': 'general',
                'step_id': 'message_received',
                'response': {
                    'response_type': 'text',
                    'text': response_text,
                    'options': []
                },
                'status': 'completed',
                'next_action': 'end_flow',
                'flow_data': {},
                'requires_input': False,
                'is_complete': True,
            }
            
        except Exception as e:
            logger.error(f"FlowWebhookView: General flow error: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'general_flow_error',
                'message': 'Error in general flow processing',
                'flow_id': flow_id,
                'flow_type': 'general',
                'details': str(e)
            }

    def _process_checkedin_flow(self, flow_id, guest, message_content, message_type, media_file, media_filename, request_data):
        """
        Process messages from already checked-in guests
        """
        try:
            # For checked-in guests, we create service-like conversations
            self._save_flow_message(
                guest=guest,
                message_content=message_content,
                message_type=message_type,
                media_file=media_file,
                media_filename=media_filename,
                flow_id=flow_id,
                flow_type='checked_in',
                flow_step='guest_request',
                flow_success=True,
                flow_data={}
            )
            
            # Response for checked-in guests
            response_text = f"Hello {guest.full_name or 'Guest'}! How can we assist you during your stay?"
            
            return {
                'success': True,
                'flow_id': flow_id,
                'flow_type': 'checked_in',
                'step_id': 'guest_request',
                'response': {
                    'response_type': 'text',
                    'text': response_text,
                    'options': []
                },
                'status': 'in_progress',
                'next_action': 'await_user_input',
                'flow_data': {},
                'requires_input': True,
                'is_complete': False,
            }
            
        except Exception as e:
            logger.error(f"FlowWebhookView: Checked-in flow error: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'checkedin_flow_error',
                'message': 'Error in checked-in flow processing',
                'flow_id': flow_id,
                'flow_type': 'checked_in',
                'details': str(e)
            }

    def _save_flow_message(self, guest, message_content, message_type, media_file, media_filename, flow_id, flow_type, flow_step, flow_success, flow_data):
        """
        Save message with flow metadata
        """
        try:
            # Get or create active stay for hotel information
            active_stay = Stay.objects.filter(guest=guest, status='active').first()
            if not active_stay:
                logger.warning(f"FlowWebhookView: No active stay found for guest {guest.id}, using default hotel")
                # Fallback to first hotel or create logic for this case
                from hotel.models import Hotel
                hotel = Hotel.objects.first()
            else:
                hotel = active_stay.hotel

            # Get or create conversation for this flow
            conversation, created = Conversation.objects.get_or_create(
                guest=guest,
                hotel=hotel,
                department='Reception',  # Default department for flows
                conversation_type=flow_type,
                status='active',
                defaults={
                    'last_message_at': timezone.now(),
                    'last_message_preview': message_content[:255],
                }
            )

            if not created:
                conversation.update_last_message(message_content)

            # Create message with flow metadata
            message = Message.objects.create(
                conversation=conversation,
                sender_type='guest',
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