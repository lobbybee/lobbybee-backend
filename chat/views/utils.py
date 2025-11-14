"""
Utility views and functions for chat functionality.
"""

from .base import (
    APIView, status, Response, logger, User, transaction, timezone,
    TypingIndicatorSerializer, Conversation, ConversationParticipant,
    async_to_sync, get_channel_layer
)


def send_typing_indicator(request):
    """
    Send typing indicator to conversation participants
    """
    if request.method != 'POST':
        return Response(
            {'error': 'Method not allowed'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

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

        # Broadcast typing indicator via WebSocket
        try:
            channel_layer = get_channel_layer()
            conversation_group_name = f"conversation_{conversation_id}"
            
            async_to_sync(channel_layer.group_send)(
                conversation_group_name,
                {
                    'type': 'typing_indicator',
                    'data': {
                        'conversation_id': conversation_id,
                        'user_id': user.id,
                        'user_name': user.get_full_name() or user.username,
                        'is_typing': is_typing,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )

            return Response({
                'success': True,
                'conversation_id': conversation_id,
                'is_typing': is_typing,
                'timestamp': timezone.now().isoformat()
            })

        except Exception as ws_error:
            logger.error(f"send_typing_indicator: Failed to broadcast typing indicator: {ws_error}")
            return Response(
                {'error': 'Failed to send typing indicator'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Conversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"send_typing_indicator: Error sending typing indicator: {e}", exc_info=True)
        return Response(
            {'error': 'Internal server error', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )