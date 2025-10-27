import asyncio
import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Conversation, Message, ConversationParticipant
from .serializers import (
    ConversationSerializer, MessageSerializer, GuestMessageSerializer,
    ConversationCreateSerializer, MessageReadSerializer, TypingIndicatorSerializer
)
from .consumers import notify_new_conversation_to_department, notify_conversation_update_to_department
from .utils.phone_utils import normalize_phone_number
from .utils.whatsapp_utils import download_whatsapp_media
from .utils.pydub import convert_audio_for_whatsapp
from guest.models import Guest, Stay


User = get_user_model()

logger = logging.getLogger(__name__)





class GuestWebhookView(APIView):
    """
    Webhook endpoint for receiving messages from guest applications
    """
    permission_classes = []  # No authentication required for webhook

    def post(self, request):
        logger.info(f"GuestWebhookView: Received webhook request")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Request body: {request.data}")
        
        try:
            serializer = GuestMessageSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"GuestWebhookView: Serializer validation failed: {serializer.errors}")
                return Response(
                    {'error': 'Invalid data', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            whatsapp_number = normalize_phone_number(serializer.validated_data['whatsapp_number'])
            if not whatsapp_number:
                logger.error(f"GuestWebhookView: Invalid whatsapp number format: {serializer.validated_data['whatsapp_number']}")
                return Response(
                    {'error': 'Invalid whatsapp number format'},
                    status=status.HTTP_400_BAD_REQUEST
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
                        from django.core.files.base import ContentFile
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
                    return Response(
                        {'error': 'Guest does not have an active stay'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                logger.info(f"GuestWebhookView: Found active stay: {active_stay.id} at hotel {active_stay.hotel.name}")
            except Guest.DoesNotExist:
                logger.error(f"GuestWebhookView: Guest not found with whatsapp_number: {whatsapp_number}")
                return Response(
                    {'error': 'Guest not found'},
                    status=status.HTTP_404_NOT_FOUND
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
                    return Response(
                        {'error': 'Conversation not found or access denied'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                # Create new conversation - department is required
                if not department_type:
                    logger.error(f"GuestWebhookView: Department is required when creating new conversation, but none provided")
                    return Response(
                        {'error': 'Department is required when creating new conversation'},
                        status=status.HTTP_400_BAD_REQUEST
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
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"GuestWebhookView: Internal server error: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConversationListView(APIView):
    """
    Get conversations for the authenticated user's department
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.user_type != 'department_staff':
            return Response(
                {'error': 'Access denied. Only department staff can view conversations.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get conversations for user's departments
        user_departments = user.department or []
        conversations = Conversation.objects.filter(
            hotel=user.hotel,
            department__in=user_departments,
            status='active'
        ).select_related('guest', 'hotel').order_by('-last_message_at')

        serializer = ConversationSerializer(conversations, many=True, context={'request': request})
        return Response(serializer.data)


class ConversationDetailView(APIView):
    """
    Get details and messages for a specific conversation
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        user = request.user

        if user.user_type != 'department_staff':
            return Response(
                {'error': 'Access denied. Only department staff can view conversations.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            conversation = Conversation.objects.select_related(
                'guest', 'hotel'
            ).get(id=conversation_id)

            # Validate user can access this conversation
            user_departments = user.department or []
            if (conversation.hotel != user.hotel or
                conversation.department not in user_departments):
                return Response(
                    {'error': 'Access denied to this conversation'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get messages
            messages = conversation.messages.select_related('sender').order_by('created_at')

            # Add user as participant if not already
            with transaction.atomic():
                participant, created = ConversationParticipant.objects.get_or_create(
                    conversation=conversation,
                    staff=user,
                    defaults={'is_active': True}
                )

                if not created and not participant.is_active:
                    participant.is_active = True
                    participant.save()

            conversation_data = ConversationSerializer(conversation, context={'request': request}).data
            messages_data = MessageSerializer(messages, many=True, context={'request': request}).data

            return Response({
                'conversation': conversation_data,
                'messages': messages_data
            })

        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class CreateConversationView(APIView):
    """
    Create a new conversation for a guest
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.user_type != 'department_staff':
            return Response(
                {'error': 'Access denied. Only department staff can create conversations.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ConversationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        guest = serializer.validated_data['guest_whatsapp_number']
        department_type = serializer.validated_data['department_type']

        # Close all existing active conversations for this guest
        with transaction.atomic():
            # Close all existing active conversations for this guest across all departments
            old_conversations = Conversation.objects.filter(
                guest=guest,
                hotel=user.hotel,
                status='active'
            )
            
            # Update old conversations to closed status
            old_conversations.update(
                status='closed',
                updated_at=timezone.now()
            )

            # Create new conversation
            conversation = Conversation.objects.create(
                guest=guest,
                hotel=user.hotel,
                department=department_type.title(),
                status='active'
            )

            # Add creator as participant
            ConversationParticipant.objects.create(
                conversation=conversation,
                staff=user,
                is_active=True
            )

        serializer = ConversationSerializer(conversation, context={'request': request})
        
        # Send WebSocket notification to department members
        try:
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(notify_new_conversation_to_department(conversation))
            loop.close()
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")
        
        return Response({
            'success': True,
            'conversation': serializer.data
        }, status=status.HTTP_201_CREATED)


class MarkMessagesReadView(APIView):
    """
    Mark messages as read for a conversation
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.user_type != 'department_staff':
            return Response(
                {'error': 'Access denied. Only department staff can mark messages as read.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = MessageReadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        conversation_id = serializer.validated_data['conversation_id']
        message_ids = serializer.validated_data.get('message_ids')

        try:
            conversation = Conversation.objects.get(id=conversation_id)

            # Validate user can access this conversation
            user_departments = user.department or []
            if (conversation.hotel != user.hotel or
                conversation.department not in user_departments):
                return Response(
                    {'error': 'Access denied to this conversation'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Mark messages as read
            if message_ids:
                # Mark specific messages
                updated_count = Message.objects.filter(
                    conversation=conversation,
                    sender_type='guest',
                    is_read=False,
                    id__in=message_ids
                ).update(is_read=True, read_at=timezone.now())
            else:
                # Mark all unread messages in conversation
                updated_count = Message.objects.filter(
                    conversation=conversation,
                    sender_type='guest',
                    is_read=False
                ).update(is_read=True, read_at=timezone.now())

            # Update participant's last read time
            participant, created = ConversationParticipant.objects.get_or_create(
                conversation=conversation,
                staff=user,
                defaults={'is_active': True, 'last_read_at': timezone.now()}
            )

            if not created:
                participant.last_read_at = timezone.now()
                participant.save()

            return Response({
                'success': True,
                'messages_marked': updated_count
            })

        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class CloseConversationView(APIView):
    """
    Close a conversation by setting its status to 'closed'
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.user_type != 'department_staff':
            return Response(
                {'error': 'Access denied. Only department staff can close conversations.'},
                status=status.HTTP_403_FORBIDDEN
            )

        conversation_id = request.data.get('conversation_id')
        if not conversation_id:
            return Response(
                {'error': 'Conversation ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            conversation = Conversation.objects.get(id=conversation_id)

            # Validate user can access this conversation
            user_departments = user.department or []
            if (conversation.hotel != user.hotel or
                conversation.department not in user_departments):
                return Response(
                    {'error': 'Access denied to this conversation'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Update conversation status to closed
            conversation.status = 'closed'
            conversation.save(update_fields=['status'])

            # Send WebSocket notification to department members
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(notify_conversation_update_to_department(conversation, 'closed'))
                loop.close()
            except Exception as e:
                logger.error(f"Failed to send WebSocket notification: {e}")

            return Response({
                'success': True,
                'message': 'Conversation closed successfully',
                'conversation_id': conversation_id
            })

        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )


def send_typing_indicator(request):
    """
    Send typing indicator to conversation participants
    """
    if request.method != 'POST':
        return Response({'error': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    user = request.user

    if user.user_type != 'department_staff':
        return Response(
            {'error': 'Access denied. Only department staff can send typing indicators.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = TypingIndicatorSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    conversation_id = serializer.validated_data['conversation_id']
    is_typing = serializer.validated_data['is_typing']

    try:
        conversation = Conversation.objects.get(id=conversation_id)

        # Validate user can access this conversation
        user_departments = user.department or []
        if (conversation.hotel != user.hotel or
            conversation.department not in user_departments):
            return Response(
                {'error': 'Access denied to this conversation'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Send typing indicator via WebSocket
        channel_layer = get_channel_layer()
        conversation_department = conversation.department.lower()
        relevant_group = f"department_{conversation_department}"
        
        async_to_sync(channel_layer.group_send)(
            relevant_group,
            {
                'type': 'typing_indicator',
                'message': {
                    'conversation_id': conversation_id,
                    'user_id': user.id,
                    'user_name': user.get_full_name() or user.username,
                    'is_typing': is_typing
                }
            }
        )

        return Response({'success': True})

    except Conversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )


class GuestConversationTypeView(APIView):
    """
    Get the conversation type and last conversation timing for a guest based on phone number
    """
    permission_classes = []  # No authentication required for guest conversation type lookup

    def get(self, request):
        phone_number = request.query_params.get('phone_number')
        
        if not phone_number:
            return Response(
                {'error': 'phone_number parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Normalize the phone number
            normalized_phone = normalize_phone_number(phone_number)
            if not normalized_phone:
                return Response(
                    {'error': 'Invalid phone number format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Find the guest by phone number
            guest = Guest.objects.get(whatsapp_number=normalized_phone)
            
            # Get the last active conversation for this guest, ordered by last_message_at or created_at
            last_conversation = Conversation.objects.filter(
                guest=guest,
                status='active'
            ).order_by('-last_message_at', '-created_at').first()
            
            if last_conversation:
                # Determine simplified checkin status
                if guest.status == 'checked_in':
                    checkin_status = 'checked_in'
                elif guest.status == 'checked_out':
                    checkin_status = 'checked_out'
                else:
                    checkin_status = None
                
                return Response({
                    'conversation_type': last_conversation.conversation_type,
                    'last_conversation_timing': last_conversation.last_message_at or last_conversation.created_at,
                    'guest_name': guest.full_name,
                    'hotel_id': last_conversation.hotel.id,
                    'department': last_conversation.department,
                    'checkin_status': checkin_status,
                    'is_anonymous': False
                })
            else:
                # No conversation found, return 'general' as default
                # Determine simplified checkin status
                if guest.status == 'checked_in':
                    checkin_status = 'checked_in'
                elif guest.status == 'checked_out':
                    checkin_status = 'checked_out'
                else:
                    checkin_status = None
                
                return Response({
                    'conversation_type': 'general',
                    'last_conversation_timing': None,
                    'guest_name': guest.full_name,
                    'hotel_id': None,
                    'department': None,
                    'checkin_status': checkin_status,
                    'is_anonymous': False
                })
                
        except Guest.DoesNotExist:
            # Return anonymous user information instead of 404
            return Response({
                'conversation_type': None,
                'last_conversation_timing': None,
                'guest_name': None,
                'hotel_id': None,
                'department': None,
                'checkin_status': None,
                'is_anonymous': True
            })
        except Exception as e:
            return Response(
                {'error': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatMediaUploadView(APIView):
    """
    API endpoint for uploading media files for chat messages
    Handles file uploads from department staff with validation and access control
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle media file upload for chat messages"""
        logger.info(f"ChatMediaUploadView: Received upload request from user {request.user.username}")
        
        try:
            # Validate required fields
            conversation_id = request.data.get('conversation_id')
            caption = request.data.get('caption', '')
            
            if not conversation_id:
                logger.error("ChatMediaUploadView: Missing conversation_id")
                return Response(
                    {'error': 'conversation_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if 'file' not in request.FILES:
                logger.error("ChatMediaUploadView: No file provided")
                return Response(
                    {'error': 'file is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            uploaded_file = request.FILES['file']
            logger.info(f"ChatMediaUploadView: Processing file {uploaded_file.name} for conversation {conversation_id}")
            
            # Validate file size (10MB limit)
            max_size = 10 * 1024 * 1024  # 10MB
            if uploaded_file.size > max_size:
                logger.error(f"ChatMediaUploadView: File too large: {uploaded_file.size} bytes")
                return Response(
                    {'error': 'File size exceeds 10MB limit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf', 
                           'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                           'video/mp4', 'video/avi', 'video/mov', 'audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/webm', 'audio/ogg']
            
            if uploaded_file.content_type not in allowed_types:
                logger.error(f"ChatMediaUploadView: Unsupported file type: {uploaded_file.content_type}")
                return Response(
                    {'error': f'File type {uploaded_file.content_type} is not supported'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate conversation exists and user has access
            try:
                conversation = Conversation.objects.get(id=conversation_id)
                
                # Check if user is department staff and has access to this conversation's department
                if request.user.user_type != 'department_staff':
                    logger.error(f"ChatMediaUploadView: User {request.user.username} is not department staff")
                    return Response(
                        {'error': 'Only department staff can upload files'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Check if user has access to the conversation's department
                if not hasattr(request.user, 'department') or not request.user.department:
                    logger.error(f"ChatMediaUploadView: User {request.user.username} has no department assigned")
                    return Response(
                        {'error': 'User has no department assigned'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Handle department field which can be either list or string
                if isinstance(request.user.department, list):
                    user_departments = [str(dept).strip() for dept in request.user.department if str(dept).strip()]
                else:
                    user_departments = [dept.strip() for dept in request.user.department.split(',') if dept.strip()]
                if conversation.department not in user_departments:
                    logger.error(f"ChatMediaUploadView: User {request.user.username} department {user_departments} not in conversation department {conversation.department}")
                    return Response(
                        {'error': 'Access denied to this conversation'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                logger.info(f"ChatMediaUploadView: User {request.user.username} validated for conversation {conversation_id}")
                
            except Conversation.DoesNotExist:
                logger.error(f"ChatMediaUploadView: Conversation {conversation_id} not found")
                return Response(
                    {'error': 'Conversation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Determine message type based on file content type
            message_type_mapping = {
                'image/jpeg': 'image',
                'image/png': 'image', 
                'image/gif': 'image',
                'application/pdf': 'document',
                'text/plain': 'document',
                'application/msword': 'document',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'document',
                'video/mp4': 'video',
                'video/avi': 'video',
                'video/mov': 'video',
                'audio/mpeg': 'audio',
                'audio/wav': 'audio',
                'audio/mp3': 'audio',
                'audio/webm': 'audio',
                'audio/ogg': 'audio'
            }
            
            message_type = message_type_mapping.get(uploaded_file.content_type, 'document')
            
            # Convert WebM audio to OGG if needed
            processed_file = uploaded_file
            filename = uploaded_file.name
            
            if uploaded_file.content_type == 'audio/webm':
                logger.info(f"ChatMediaUploadView: Converting WebM audio to OGG for file {uploaded_file.name}")
                
                # Read the WebM file data
                webm_data = uploaded_file.read()
                
                # Convert to OGG format
                ogg_data = convert_audio_for_whatsapp(webm_data, uploaded_file.content_type)
                
                if ogg_data:
                    # Create a new file-like object with the converted OGG data
                    from django.core.files.uploadedfile import SimpleUploadedFile
                    processed_file = SimpleUploadedFile(
                        name=f"{uploaded_file.name.rsplit('.', 1)[0]}.ogg",
                        content=ogg_data,
                        content_type='audio/ogg'
                    )
                    filename = processed_file.name
                    logger.info(f"ChatMediaUploadView: Successfully converted WebM to OGG: {filename}")
                else:
                    logger.warning(f"ChatMediaUploadView: Failed to convert WebM to OGG, using original file")
                    # Reset file pointer since we read it
                    uploaded_file.seek(0)
            
            # Create temporary message to trigger file upload (this will be saved by WebSocket)
            temp_message = Message(
                conversation=conversation,
                sender_type='staff',
                sender=request.user,
                message_type=message_type,
                content=caption or filename,
                media_file=processed_file,
                media_filename=filename
            )
            
            # Trigger the save to upload the file, but don't save to database yet
            # We'll create the actual message via WebSocket
            temp_message.media_file.save(filename, processed_file)
            file_url = temp_message.media_file.url
            
            # Clean up the temporary model instance (but keep the uploaded file)
            temp_message.media_file = None
            del temp_message
            
            logger.info(f"ChatMediaUploadView: Successfully uploaded file {uploaded_file.name} to {file_url}")
            
            # Return success response with file information
            return Response({
                'success': True,
                'file_url': file_url,
                'filename': filename,
                'file_type': message_type,
                'file_size': processed_file.size,
                'caption': caption,
                'conversation_id': conversation_id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"ChatMediaUploadView: Error uploading file: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to upload file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
