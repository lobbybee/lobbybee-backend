"""
Conversation-related views for managing chat conversations.
"""

from rest_framework.permissions import IsAuthenticated
from . import (
    APIView, status, Response, logger, User, transaction, timezone,
    ConversationSerializer, MessageSerializer, ConversationCreateSerializer,
    MessageReadSerializer, TypingIndicatorSerializer, Conversation, 
    Message, ConversationParticipant, Guest, Stay, notify_new_conversation_to_department,
    notify_conversation_update_to_department
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

        try:
            with transaction.atomic():
                # Check if conversation already exists
                existing_conversation = Conversation.objects.filter(
                    guest=guest,
                    hotel=user.hotel,
                    department=department_type,
                    conversation_type='service',
                    status='active'
                ).first()

                if existing_conversation:
                    return Response({
                        'success': False,
                        'error': 'Conversation already exists',
                        'conversation_id': existing_conversation.id
                    }, status=status.HTTP_409_CONFLICT)

                # Create new conversation
                conversation = Conversation.objects.create(
                    guest=guest,
                    hotel=user.hotel,
                    department=department_type,
                    conversation_type='service',
                    status='active',
                    last_message_at=timezone.now(),
                    last_message_preview='New conversation started'
                )

                # Add staff as participant
                ConversationParticipant.objects.get_or_create(
                    conversation=conversation,
                    staff=user,
                    defaults={'is_active': True}
                )

                # Notify department staff
                notify_new_conversation_to_department(conversation)

                return Response({
                    'success': True,
                    'conversation_id': conversation.id,
                    'guest_name': guest.full_name,
                    'department': department_type
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"CreateConversationView: Error creating conversation: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CloseConversationView(APIView):
    """
    Close a conversation
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
                {'error': 'conversation_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                conversation = Conversation.objects.get(id=conversation_id)

                # Validate user can access this conversation
                user_departments = user.department or []
                if (conversation.hotel != user.hotel or
                    conversation.department not in user_departments):
                    return Response(
                        {'error': 'Access denied to this conversation'},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Update conversation status
                conversation.status = 'closed'
                conversation.save(update_fields=['status'])

                # Update participant status
                ConversationParticipant.objects.filter(
                    conversation=conversation,
                    staff=user
                ).update(is_active=False)

                # Notify department staff
                notify_conversation_update_to_department(conversation)

                return Response({
                    'success': True,
                    'conversation_id': conversation.id,
                    'status': 'closed'
                })

        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"CloseConversationView: Error closing conversation: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GuestConversationTypeView(APIView):
    """
    Get the type of conversation for a guest (new or existing)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        guest_whatsapp_number = request.GET.get('guest_whatsapp_number')

        if not guest_whatsapp_number:
            return Response(
                {'error': 'guest_whatsapp_number parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.user_type != 'department_staff':
            return Response(
                {'error': 'Access denied. Only department staff can check conversation types.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            # Normalize phone number
            normalized_number = normalize_phone_number(guest_whatsapp_number)
            if not normalized_number:
                return Response(
                    {'error': 'Invalid phone number format'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get guest
            guest = Guest.objects.get(whatsapp_number=normalized_number)

            # Check for existing active conversations
            conversations = Conversation.objects.filter(
                guest=guest,
                hotel=user.hotel,
                status='active'
            ).select_related('guest', 'hotel')

            if conversations.exists():
                # Guest has existing conversations
                conversation_list = []
                for conv in conversations:
                    conversation_list.append({
                        'id': conv.id,
                        'department': conv.department,
                        'conversation_type': conv.conversation_type,
                        'last_message_at': conv.last_message_at,
                        'last_message_preview': conv.last_message_preview,
                        'created_at': conv.created_at
                    })

                return Response({
                    'guest_exists': True,
                    'has_conversations': True,
                    'conversations': conversation_list,
                    'guest_info': {
                        'id': guest.id,
                        'full_name': guest.full_name,
                        'email': guest.email,
                        'whatsapp_number': guest.whatsapp_number,
                        'status': guest.status
                    }
                })

            else:
                # Guest exists but no active conversations
                return Response({
                    'guest_exists': True,
                    'has_conversations': False,
                    'conversations': [],
                    'guest_info': {
                        'id': guest.id,
                        'full_name': guest.full_name,
                        'email': guest.email,
                        'whatsapp_number': guest.whatsapp_number,
                        'status': guest.status
                    }
                })

        except Guest.DoesNotExist:
            # Guest doesn't exist
            return Response({
                'guest_exists': False,
                'has_conversations': False,
                'conversations': [],
                'guest_info': None
            })

        except Exception as e:
            logger.error(f"GuestConversationTypeView: Error checking conversation type: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )