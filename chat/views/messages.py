"""
Message-related views for handling chat messages.
"""

from rest_framework.permissions import IsAuthenticated
from .base import (
    APIView, status, Response, logger, User, transaction, timezone,
    MessageSerializer, MessageReadSerializer, Conversation, 
    Message, ConversationParticipant, async_to_sync, get_channel_layer
)


class MarkMessagesReadView(APIView):
    """
    Mark messages as read for a conversation
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Allow access for receptionist, management, and department staff
        allowed_user_types = ['department_staff', 'receptionist', 'manager', 'hotel_admin']
        if user.user_type not in allowed_user_types:
            return Response(
                {'error': 'Access denied. Only staff members can mark messages as read.'},
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
            with transaction.atomic():
                # Validate conversation access
                conversation = Conversation.objects.get(id=conversation_id)
                
                departments = user.department or []
                
                # Ensure departments is always a list
                if isinstance(departments, str):
                    user_departments = [departments]
                elif isinstance(departments, list):
                    user_departments = departments
                else:
                    user_departments = []
                    
                if (conversation.hotel != user.hotel or
                    conversation.department not in user_departments):
                    return Response(
                        {'error': 'Access denied to this conversation'},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Add/update participant
                participant, created = ConversationParticipant.objects.get_or_create(
                    conversation=conversation,
                    staff=user,
                    defaults={'is_active': True}
                )

                if not created and not participant.is_active:
                    participant.is_active = True
                    participant.save()

                # Mark messages as read
                if message_ids:
                    # Mark specific messages
                    messages = Message.objects.filter(
                        id__in=message_ids,
                        conversation=conversation,
                        sender_type='guest',
                        is_read=False
                    )
                    count = messages.count()
                    messages.update(is_read=True, read_at=timezone.now())
                else:
                    # Mark all unread messages in conversation
                    messages = Message.objects.filter(
                        conversation=conversation,
                        sender_type='guest',
                        is_read=False
                    )
                    count = messages.count()
                    messages.update(is_read=True, read_at=timezone.now())

                # Update participant's last read time
                participant.mark_conversation_read()

                # Broadcast read status update via WebSocket
                try:
                    channel_layer = get_channel_layer()
                    conversation_group_name = f"conversation_{conversation_id}"
                    
                    async_to_sync(channel_layer.group_send)(
                        conversation_group_name,
                        {
                            'type': 'messages_read',
                            'data': {
                                'conversation_id': conversation_id,
                                'staff_id': user.id,
                                'staff_name': user.get_full_name() or user.username,
                                'marked_read_count': count,
                                'timestamp': timezone.now().isoformat()
                            }
                        }
                    )
                except Exception as ws_error:
                    logger.error(f"MarkMessagesReadView: Failed to broadcast read status: {ws_error}")

                return Response({
                    'message': 'Messages marked as read successfully',
                    'conversation_id': conversation_id,
                    'messages_marked_read': count,
                    'message_ids': message_ids if message_ids else None
                })

        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"MarkMessagesReadView: Error marking messages as read: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )