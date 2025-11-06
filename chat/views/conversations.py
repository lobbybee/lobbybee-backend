"""
Conversation-related views for managing chat conversations.
"""

from rest_framework.permissions import IsAuthenticated
from .base import (
    APIView,
    status,
    Response,
    logger,
    User,
    transaction,
    ConversationSerializer,
    MessageSerializer,
    ConversationCreateSerializer,
    MessageReadSerializer,
    TypingIndicatorSerializer,
    Conversation,
    Message,
    ConversationParticipant,
    Guest,
    Stay,
    notify_new_conversation_to_department,
    notify_conversation_update_to_department,
    normalize_phone_number,
)
from ..utils.whatsapp_flow_utils import (
    is_conversation_expired,
    extract_whatsapp_message_data,
    get_message_type_info,
    generate_department_menu_payload,
    generate_error_text_payload,
    validate_department_selection,
    find_active_department_conversation
)
from datetime import datetime,timezone
class ConversationListView(APIView):
    """
    Get conversations for the authenticated user's department
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.user_type != "department_staff":
            return Response(
                {
                    "error": "Access denied. Only department staff can view conversations."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get conversations for user's departments
        user_departments = user.department or []
        conversations = (
            Conversation.objects.filter(
                hotel=user.hotel, department__in=user_departments, status="active"
            )
            .select_related("guest", "hotel")
            .order_by("-last_message_at")
        )

        serializer = ConversationSerializer(
            conversations, many=True, context={"request": request}
        )
        return Response(serializer.data)


class ConversationDetailView(APIView):
    """
    Get details and messages for a specific conversation
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        user = request.user

        if user.user_type != "department_staff":
            return Response(
                {
                    "error": "Access denied. Only department staff can view conversations."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            conversation = Conversation.objects.select_related("guest", "hotel").get(
                id=conversation_id
            )

            # Validate user can access this conversation
            user_departments = user.department or []
            if (
                conversation.hotel != user.hotel
                or conversation.department not in user_departments
            ):
                return Response(
                    {"error": "Access denied to this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get messages
            messages = conversation.messages.select_related("sender").order_by(
                "created_at"
            )

            # Add user as participant if not already
            with transaction.atomic():
                participant, created = ConversationParticipant.objects.get_or_create(
                    conversation=conversation, staff=user, defaults={"is_active": True}
                )

                if not created and not participant.is_active:
                    participant.is_active = True
                    participant.save()

            conversation_data = ConversationSerializer(
                conversation, context={"request": request}
            ).data
            messages_data = MessageSerializer(
                messages, many=True, context={"request": request}
            ).data

            return Response(
                {"conversation": conversation_data, "messages": messages_data}
            )

        except Conversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )


class CreateConversationView(APIView):
    """
    Create a new conversation for a guest
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.user_type != "department_staff":
            return Response(
                {
                    "error": "Access denied. Only department staff can create conversations."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ConversationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        guest = serializer.validated_data["guest_whatsapp_number"]
        department_type = serializer.validated_data["department_type"]

        try:
            with transaction.atomic():
                # Check if conversation already exists
                existing_conversation = Conversation.objects.filter(
                    guest=guest,
                    hotel=user.hotel,
                    department=department_type,
                    conversation_type="service",
                    status="active",
                ).first()

                if existing_conversation:
                    return Response(
                        {
                            "success": False,
                            "error": "Conversation already exists",
                            "conversation_id": existing_conversation.id,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                # Create new conversation
                conversation = Conversation.objects.create(
                    guest=guest,
                    hotel=user.hotel,
                    department=department_type,
                    conversation_type="service",
                    status="active",
                    last_message_at=timezone.now(),
                    last_message_preview="New conversation started",
                )

                # Add staff as participant
                ConversationParticipant.objects.get_or_create(
                    conversation=conversation, staff=user, defaults={"is_active": True}
                )

                # Notify department staff
                notify_new_conversation_to_department(conversation)

                return Response(
                    {
                        "success": True,
                        "conversation_id": conversation.id,
                        "guest_name": guest.full_name,
                        "department": department_type,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            logger.error(
                f"CreateConversationView: Error creating conversation: {e}",
                exc_info=True,
            )
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CloseConversationView(APIView):
    """
    Close a conversation
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.user_type != "department_staff":
            return Response(
                {
                    "error": "Access denied. Only department staff can close conversations."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        conversation_id = request.data.get("conversation_id")
        if not conversation_id:
            return Response(
                {"error": "conversation_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                conversation = Conversation.objects.get(id=conversation_id)

                # Validate user can access this conversation
                user_departments = user.department or []
                if (
                    conversation.hotel != user.hotel
                    or conversation.department not in user_departments
                ):
                    return Response(
                        {"error": "Access denied to this conversation"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # Update conversation status
                conversation.status = "closed"
                conversation.save(update_fields=["status"])

                # Update participant status
                ConversationParticipant.objects.filter(
                    conversation=conversation, staff=user
                ).update(is_active=False)

                # Notify department staff
                notify_conversation_update_to_department(conversation)

                return Response(
                    {
                        "success": True,
                        "conversation_id": conversation.id,
                        "status": "closed",
                    }
                )

        except Conversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(
                f"CloseConversationView: Error closing conversation: {e}", exc_info=True
            )
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GuestConversationTypeView(APIView):
    """
    Get the type of conversation for a guest and determine routing action
    Supports both GET (legacy) and POST (with webhook data) methods
    """

    permission_classes = []

    def get(self, request):
        """Legacy GET method - returns conversation info only"""
        user = request.user
        guest_whatsapp_number = request.GET.get("guest_whatsapp_number")

        if not guest_whatsapp_number:
            return Response(
                {"error": "guest_whatsapp_number parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get base conversation info
        base_response = self._get_guest_conversation_info(user, guest_whatsapp_number)

        if base_response.status_code != 200:
            return base_response

        response_data = base_response.data
        
        # Add default values for compatibility with GuestWebhookView
        response_data['message_type_info'] = None
        response_data['message'] = {
            'message': '',
            'message_type': 'text'
        }
        response_data['action'] = 'relay'

        return Response(response_data)

    def post(self, request):
        """
        POST method - includes webhook data for enhanced routing logic
        Body: {
            "guest_whatsapp_number": "918589878253",
            "webhook_body": {...}  # WhatsApp webhook data
        }
        """
        user = request.user
        guest_whatsapp_number = request.data.get("guest_whatsapp_number")
        webhook_body = request.data.get("webhook_body")

        # Validate required parameters
        if not guest_whatsapp_number:
            return Response(
                {"error": "guest_whatsapp_number parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get base conversation info
        base_response = self._get_guest_conversation_info(user, guest_whatsapp_number)

        if base_response.status_code != 200:
            return base_response

        response_data = base_response.data

        # If no webhook body provided, return basic info (legacy behavior)
        if not webhook_body:
            response_data['action'] = 'relay'
            response_data['message_type_info'] = None
            response_data['message'] = {
                'message': '',
                'message_type': 'text'
            }
            return Response(response_data)

        # Extract and validate webhook message data
        message_data, error = extract_whatsapp_message_data(webhook_body)
        if error:
            logger.warning(f"Webhook parsing error: {error}")
            return Response(
                {
                    "error": "Invalid webhook data",
                    "details": error,
                    "fallback_action": "relay"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get message type information
        message_type_info = get_message_type_info(message_data)
        response_data['message_type_info'] = message_type_info

        # Extract message content based on type
        message_content = self._extract_message_content(message_data, message_type_info)
        response_data['message'] = message_content

        # Determine routing action
        routing_result = self._determine_routing_action(
            response_data,
            message_data,
            message_type_info
        )

        return Response(routing_result)

    def _get_guest_conversation_info(self, user, guest_whatsapp_number):
        """
        Core logic to fetch guest and conversation information
        Returns Response object
        """
        try:
            # Normalize phone number
            normalized_number = normalize_phone_number(guest_whatsapp_number)
            if not normalized_number:
                return Response(
                    {"error": "Invalid phone number format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get guest
            try:
                guest = Guest.objects.get(whatsapp_number=normalized_number)
            except Guest.DoesNotExist:
                # Guest doesn't exist
                return Response(
                    {
                        "guest_exists": False,
                        "has_conversations": False,
                        "conversations": [],
                        "guest_info": None,
                        "guest_status": "anonymous",
                    }
                )

            # Check for existing active conversations
            if user.is_authenticated and hasattr(user, 'hotel'):
                conversations = Conversation.objects.filter(
                    guest=guest, hotel=user.hotel, status="active"
                ).select_related("guest", "hotel")
            else:
                conversations = Conversation.objects.filter(
                    guest=guest, status="active"
                ).select_related("guest", "hotel")

            # Order by most recent first
            conversations_list = list(conversations.order_by('-last_message_at'))

            # Build conversation data with expiry status
            conversations_data = []
            current_time = datetime.now(timezone.utc)

            for conv in conversations_list:
                is_expired = is_conversation_expired(conv.last_message_at)
                conversation_data = {
                    "id": conv.id,
                    "department": conv.department,
                    "conversation_type": conv.conversation_type,
                    "last_message_at": conv.last_message_at,
                    "is_expired": is_expired,
                    "last_message_preview": conv.last_message_preview,
                    "created_at": conv.created_at,
                    "is_request_fulfilled": conv.is_request_fulfilled,
                    "fulfilled_at": conv.fulfilled_at,
                    "fulfillment_notes": conv.fulfillment_notes,
                    "fulfillment_status": conv.get_fulfillment_status_display(),
                }
                conversations_data.append(conversation_data)

            # Determine guest status
            guest_status = self._determine_guest_status(guest)

            # Guest info
            guest_info = {
                "id": guest.id,
                "full_name": guest.full_name,
                "email": guest.email,
                "whatsapp_number": guest.whatsapp_number,
                "status": guest.status,
            }

            return Response(
                {
                    "guest_exists": True,
                    "has_conversations": bool(conversations_data),
                    "conversations": conversations_data,
                    "guest_info": guest_info,
                    "guest_status": guest_status,
                }
            )

        except Exception as e:
            logger.error(
                f"GuestConversationTypeView: Error checking conversation type: {e}",
                exc_info=True,
            )
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _determine_guest_status(self, guest):
        """
        Determine guest status based on guest's current status

        Returns:
        - 'active_guest' for guests with status 'checked_in' or 'pending_checkin'
        - 'old_guest' for guests with status 'checked_out'
        - 'anonymous' for guests that don't exist (handled in caller)
        """
        if guest.status in ['checked_in', 'pending_checkin']:
            return 'active_guest'
        elif guest.status == 'checked_out':
            return 'old_guest'
        else:
            # Fallback for any other status
            return 'old_guest'

    def _determine_routing_action(self, guest_data, message_data, message_type_info):
        """
        Determine what action to take based on conversation state and message type
        """
        guest_exists = guest_data.get('guest_exists', False)
        has_conversations = guest_data.get('has_conversations', False)
        conversations = guest_data.get('conversations', [])
        guest_info = guest_data.get('guest_info')
        guest_status = guest_data.get('guest_status')

        recipient_number = message_data.get('from')
        guest_name = guest_info.get('full_name', 'Guest') if guest_info else 'Guest'

        # Check if guest is allowed to use service
        if guest_status in ['old_guest', 'anonymous']:
            return {
                **guest_data,
                'action': 'access_denied',
                'reason': 'guest_not_active',
                'whatsapp_payload': generate_error_text_payload(
                    recipient_number,
                    f"Hi {guest_name}, it looks like you're not currently checked in. "
                    "Please contact reception if you need assistance."
                ) if guest_status == 'old_guest' else generate_error_text_payload(
                    recipient_number,
                    "We couldn't find your guest profile. Please contact reception for assistance."
                )
            }

        # Handle list reply (department selection)
        if message_type_info.get('is_list_reply'):
            return self._handle_department_selection(
                guest_data, message_type_info, recipient_number, guest_name, conversations
            )

        # Check most recent conversation only (optimization)
        if has_conversations and conversations:
            most_recent_conv = conversations[0]

            # If most recent conversation is expired, show menu
            if most_recent_conv.get('is_expired', False):
                return {
                    **guest_data,
                    'action': 'show_menu',
                    'whatsapp_payload': generate_department_menu_payload(
                        recipient_number,
                        guest_name
                    )
                }

            # Use the most recent active conversation
            return {
                **guest_data,
                'action': 'relay',
                'target_conversation': self._format_target_conversation(
                    most_recent_conv, use_existing=True
                )
            }

        # New guest with no conversations - show menu
        if guest_exists and not has_conversations:
            return {
                **guest_data,
                'action': 'show_menu',
                'whatsapp_payload': generate_department_menu_payload(
                    recipient_number,
                    guest_name
                )
            }

        # Fallback (shouldn't reach here)
        logger.warning(f"Unexpected routing state for guest {guest_name}")
        return {
            **guest_data,
            'action': 'relay',
            'target_conversation': None
        }

    def _handle_department_selection(self, guest_data, message_type_info,
                                     recipient_number, guest_name, conversations):
        """
        Handle department selection from interactive list
        """
        list_reply_id = message_type_info.get('list_reply_id')
        is_valid, dept_name = validate_department_selection(list_reply_id)

        if not is_valid:
            return {
                **guest_data,
                'action': 'invalid_selection',
                'whatsapp_payload': generate_error_text_payload(
                    recipient_number,
                    "Sorry, that's not a valid selection. Please use the department menu to start a conversation."
                )
            }

        # Re-verify guest is still active (edge case protection)
        if guest_data.get('guest_status') != 'active_guest':
            return {
                **guest_data,
                'action': 'access_denied',
                'reason': 'guest_status_changed',
                'whatsapp_payload': generate_error_text_payload(
                    recipient_number,
                    f"Hi {guest_name}, we couldn't process your request. Please contact reception for assistance."
                )
            }

        # Find existing non-expired conversation for this department
        existing_conv = find_active_department_conversation(conversations, dept_name)

        if existing_conv:
            # Use existing conversation
            return {
                **guest_data,
                'action': 'relay',
                'selected_department': list_reply_id,
                'target_conversation': self._format_target_conversation(
                    existing_conv, use_existing=True
                )
            }
        else:
            # Create new conversation
            return {
                **guest_data,
                'action': 'relay',
                'selected_department': list_reply_id,
                'target_conversation': {
                    'id': None,
                    'department': dept_name,
                    'conversation_type': 'service',
                    'use_existing': False,
                    'create_new': True
                }
            }

    def _format_target_conversation(self, conversation, use_existing=True):
        """
        Format conversation data consistently for target_conversation field
        """
        return {
            'id': conversation.get('id'),
            'department': conversation.get('department'),
            'conversation_type': conversation.get('conversation_type'),
            'use_existing': use_existing,
            'create_new': not use_existing,
            'last_message_at': conversation.get('last_message_at'),
            'is_expired': conversation.get('is_expired', False)
        }

    def _extract_message_content(self, message_data, message_type_info):
        """
        Extract message content based on message type for GuestWebhookView compatibility
        
        Returns a dictionary with 'message' and 'message_type' fields that match
        what GuestWebhookView expects
        """
        if not message_data or not message_type_info:
            return {
                'message': '',
                'message_type': 'text'
            }
        
        msg_type = message_data.get('type')
        
        # For text messages, return the text body
        if msg_type == 'text':
            return {
                'message': message_data.get('text', ''),
                'message_type': 'text'
            }
        
        # For interactive messages (button replies, list replies), treat as text
        elif msg_type == 'interactive':
            interactive_data = message_data.get('interactive', {})
            interactive_type = interactive_data.get('type')
            
            if interactive_type == 'button_reply':
                button_reply = interactive_data.get('button_reply', {})
                return {
                    'message': button_reply.get('title', ''),
                    'message_type': 'text'
                }
            elif interactive_type == 'list_reply':
                list_reply = interactive_data.get('list_reply', {})
                return {
                    'message': list_reply.get('title', ''),
                    'message_type': 'text'
                }
            else:
                # Other interactive types, treat as text
                return {
                    'message': 'Interactive message received',
                    'message_type': 'text'
                }
        
        # For media messages, return the type name and a descriptive message
        elif msg_type in ['image', 'document', 'video', 'audio']:
            return {
                'message': f'{msg_type.capitalize()} message received',
                'message_type': msg_type
            }
        
        # Fallback for unknown types
        else:
            return {
                'message': 'Message received',
                'message_type': 'text'
            }
