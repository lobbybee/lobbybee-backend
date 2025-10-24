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
from guest.models import Guest, Stay


User = get_user_model()

logger = logging.getLogger(__name__)





class GuestWebhookView(APIView):
    """
    Webhook endpoint for receiving messages from guest applications
    """
    permission_classes = []  # No authentication required for webhook

    def post(self, request):
        try:
            serializer = GuestMessageSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Invalid data', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            whatsapp_number = normalize_phone_number(serializer.validated_data['whatsapp_number'])
            if not whatsapp_number:
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

            # Validate guest exists and has active stay
            try:
                guest = Guest.objects.get(whatsapp_number=whatsapp_number)
                active_stay = Stay.objects.filter(guest=guest, status='active').first()
                if not active_stay:
                    return Response(
                        {'error': 'Guest does not have an active stay'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Guest.DoesNotExist:
                return Response(
                    {'error': 'Guest not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            hotel = active_stay.hotel

            # Always use 'service' as default conversation type
            conversation_type = 'service'
            
            # Handle conversation lookup vs creation
            if conversation_id:
                # Use existing conversation
                try:
                    conversation = Conversation.objects.get(
                        id=conversation_id,
                        guest=guest,
                        hotel=hotel,
                        status='active'
                    )
                    department_type = conversation.department
                except Conversation.DoesNotExist:
                    return Response(
                        {'error': 'Conversation not found or access denied'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                # Create new conversation - department is required
                if not department_type:
                    return Response(
                        {'error': 'Department is required when creating new conversation'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Handle message creation
            with transaction.atomic():
                if conversation_id:
                    # Use existing conversation
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
                        conversation = existing_conversation
                        conversation.update_last_message(message_content)
                        created = False
                    else:
                        # Create new conversation
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

                # Create message
                message = Message.objects.create(
                    conversation=conversation,
                    sender_type='guest',
                    message_type=message_type,
                    content=message_content,
                    media_url=media_url,
                    media_filename=media_filename
                )

            # Broadcast message to department staff via WebSocket
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
                'media_url': message.media_url,
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

            async_to_sync(channel_layer.group_send)(
                department_group_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )

            return Response({
                'success': True,
                'message_id': message.id,
                'conversation_id': conversation.id,
                'department': department_type,
                'conversation_type': conversation_type,
                'conversation_created': created if not conversation_id else False
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
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
                    'checkin_status': checkin_status
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
                    'checkin_status': checkin_status
                })
                
        except Guest.DoesNotExist:
            return Response(
                {'error': 'Guest not found with the provided phone number'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
