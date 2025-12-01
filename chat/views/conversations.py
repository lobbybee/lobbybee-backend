"""
Conversation-related views for managing chat conversations.
"""
from .flow_processsor import handle_incoming_whatsapp_message
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
    generate_success_text_payload,
    validate_department_selection,
    find_active_department_conversation,
)
from ..utils.webhook_deduplication import (
    check_and_create_webhook_attempt,
    update_webhook_attempt,
)
from .webhooks import process_guest_webhook
from ..utils.whatsapp_payload_utils import convert_flow_response_to_whatsapp_payload
from datetime import datetime,timezone
class ConversationListView(APIView):
    """
    Get conversations for the authenticated user's department
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Allow access for receptionist, management, and department staff
        allowed_user_types = ["department_staff", "receptionist", "manager", "hotel_admin"]
        if user.user_type not in allowed_user_types:
            return Response(
                {
                    "error": "Access denied. Only staff members can view conversations."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get conversations for user's departments
        departments = user.department or []
        
        # Ensure departments is always a list
        if isinstance(departments, str):
            user_departments = [departments]
        elif isinstance(departments, list):
            user_departments = departments
        else:
            user_departments = []
            
        conversations = (
            Conversation.objects.filter(
                hotel=user.hotel, department__in=user_departments, status="active"
            )
            .exclude(conversation_type__in=['feedback', 'checkin', 'checked_in'])
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

        # Allow access for receptionist, management, and department staff
        allowed_user_types = ["department_staff", "receptionist", "manager", "hotel_admin"]
        if user.user_type not in allowed_user_types:
            return Response(
                {
                    "error": "Access denied. Only staff members can view conversations."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            conversation = Conversation.objects.select_related("guest", "hotel").get(
                id=conversation_id
            )

            # Validate user can access this conversation
            departments = user.department or []
            
            # Ensure departments is always a list
            if isinstance(departments, str):
                user_departments = [departments]
            elif isinstance(departments, list):
                user_departments = departments
            else:
                user_departments = []
                
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

        # Allow access for receptionist, management, and department staff
        allowed_user_types = ["department_staff", "receptionist", "manager", "hotel_admin"]
        if user.user_type not in allowed_user_types:
            return Response(
                {
                    "error": "Access denied. Only staff members can create conversations."
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

        # Allow access for receptionist, management, and department staff
        allowed_user_types = ["department_staff", "receptionist", "manager", "hotel_admin"]
        if user.user_type not in allowed_user_types:
            return Response(
                {
                    "error": "Access denied. Only staff members can close conversations."
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
                departments = user.department or []
                
                # Ensure departments is always a list
                if isinstance(departments, str):
                    user_departments = [departments]
                elif isinstance(departments, list):
                    user_departments = departments
                else:
                    user_departments = []
                    
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
    Process incoming WhatsApp messages and determine routing action
    POST method only - includes webhook data for enhanced routing logic
    """

    permission_classes = []

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
        incoming_guest_whatsapp_number = request.data.get("guest_whatsapp_number")

        if not webhook_body:
            return Response(
                {"error": "webhook_body parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract and validate webhook message data first
        message_data, error = extract_whatsapp_message_data(webhook_body)
        if error:
            logger.warning(f"Webhook parsing error: {error}")
            return Response(
                {
                    "error": "Invalid webhook data",
                    "details": error,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract WhatsApp message ID for deduplication
        whatsapp_message_id = message_data.get('id')
        if not whatsapp_message_id:
            return Response(
                {"error": "Missing WhatsApp message ID in webhook data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for duplicates using WebhookAttempt model
        webhook_attempt, is_duplicate, is_new = check_and_create_webhook_attempt(
            webhook_type='guest',
            whatsapp_message_id=whatsapp_message_id,
            whatsapp_number=guest_whatsapp_number,
            request_data=request.data
        )

        if is_duplicate:
            # Return existing webhook attempt data
            existing_data = webhook_attempt.response_data or {}
            return Response({
                'success': True,
                'duplicate_message': True,
                'original_attempt_id': webhook_attempt.id,
                **existing_data
            }, status=status.HTTP_200_OK)

        # If we reach here, it's a new message, continue with processing
        logger.info(f"Processing new WhatsApp message {whatsapp_message_id} from {guest_whatsapp_number}")

        # Get base conversation info
        base_response = self._get_guest_conversation_info(user, guest_whatsapp_number)

        if base_response.status_code != 200:
            # Update webhook attempt with error
            update_webhook_attempt(
                webhook_attempt,
                'processing_failed',
                error_message=f"Failed to get guest conversation info: {base_response.data}"
            )
            return base_response

        response_data = base_response.data

        # Store guest_whatsapp_number for use in flow webhook preparation
        response_data['guest_whatsapp_number'] = guest_whatsapp_number

        # Get message type information
        message_type_info = get_message_type_info(message_data)
        response_data['message_type_info'] = message_type_info

        # Extract message content based on type
        message_content = self._extract_message_content(message_data, message_type_info)
        response_data['message'] = message_content

        # Handle special button reply interactions
        button_result = self._handle_button_reply_interactions(
            message_data,
            message_type_info,
            response_data
        )

        if button_result:
            # Button was handled, return the result directly
            update_webhook_attempt(
                webhook_attempt,
                'success',
                response_data=button_result,
                message_id=button_result.get('message_id'),
                conversation_id=button_result.get('conversation_id')
            )
            return Response(button_result)

        # Determine routing action
        routing_result = self._determine_routing_action(
            response_data,
            message_data,
            message_type_info
        )

        # Execute webhook if needed and merge result
        routing_result = self._execute_webhook_and_merge_result(
            routing_result=routing_result,
            guest_data=routing_result,
            message_data=message_data,
            webhook_body=webhook_body,
            guest_whatsapp_number=incoming_guest_whatsapp_number
        )

        # Update webhook attempt with success
        # Clean response data for JSON serialization
        import json
        from datetime import datetime

        def clean_json_data(obj):
            """Recursively clean data to make JSON serializable"""
            if isinstance(obj, datetime):
                return obj.isoformat()  # Convert datetime to ISO string
            elif isinstance(obj, dict):
                return {k: clean_json_data(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_json_data(item) for item in obj]
            else:
                return obj

        try:
            # Test JSON serialization and clean if needed
            json.dumps(routing_result)
            clean_response_data = routing_result
        except (TypeError, ValueError):
            # If serialization fails, clean the data
            clean_response_data = clean_json_data(routing_result)

        update_webhook_attempt(
            webhook_attempt,
            'success',
            response_data=clean_response_data,
            message_id=routing_result.get('message_id'),
            conversation_id=routing_result.get('conversation_id')
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
        - 'active_guest' for guests with status 'checked_in' only
        - 'pending_guest' for guests with status 'pending_checkin' (need to complete checkin)
        - 'old_guest' for guests with status 'checked_out'
        - 'anonymous' for guests that don't exist (handled in caller)
        """
        if guest.status == 'checked_in':
            return 'active_guest'
        elif guest.status == 'pending_checkin':
            return 'pending_guest'
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

        logger.info(f"Conversation routing: guest_exists={guest_exists}, has_conversations={has_conversations}, guest_status={guest_status}")

        # SIMPLIFIED LOGIC: Single guest status check
        is_checked_in_guest = guest_status == 'active_guest'
        
        # Any message from non-checked-in guest goes to flow logic
        if not is_checked_in_guest:
            logger.info(f"Non-checked-in guest {guest_name} (status: {guest_status}), routing to flow webhook")
            return {
                **guest_data,
                'action': 'flow'
            }

        # At this point, we only deal with CHECKED-IN guests
        logger.info(f"Checked-in guest {guest_name}, processing message")

        # Note: Access_denied logic removed since we now handle all messages through unified webhook system

        # Check most recent conversation (if it exists, it's already sorted by last_message_at)
        if has_conversations and conversations:
            most_recent_conv = conversations[0]
            logger.info(f"Most recent conversation: {most_recent_conv}, is_expired: {most_recent_conv.get('is_expired', False)}")

            # If most recent conversation is expired, all conversations will be expired
            if most_recent_conv.get('is_expired', False):
                logger.info("Conversation is expired, showing menu for checked-in guest")
                
                # Handle list reply to create new conversation with selected department
                if message_type_info.get('is_list_reply'):
                    return self._handle_department_selection(
                        guest_data, message_type_info, recipient_number, guest_name, conversations
                    )
                else:
                    # Show department menu (guest is already confirmed as checked-in)
                    return {
                        **guest_data,
                        'action': 'show_menu',
                        'whatsapp_payload': generate_department_menu_payload(
                            recipient_number,
                            guest_name
                        )
                    }

            # Most recent conversation is active, handle based on message type
            logger.info("Conversation is active, checking message type")
            # Handle list reply (department selection)
            if message_type_info.get('is_list_reply'):
                logger.info("List reply detected, handling department selection")
                return self._handle_department_selection(
                    guest_data, message_type_info, recipient_number, guest_name, conversations
                )

            # Use the most recent active conversation for other message types
            logger.info(f"Using existing conversation: {most_recent_conv.get('id')}")
            return {
                **guest_data,
                'action': 'relay',
                'target_conversation': self._format_target_conversation(
                    most_recent_conv, use_existing=True
                )
            }

        # New checked-in guest with no conversations - show menu
        if is_checked_in_guest and not has_conversations:
            logger.info(f"New checked-in guest with no conversations: {guest_name}")

            # Check for department selection (list reply) first
            if message_type_info.get('is_list_reply'):
                logger.info(f"Department selection detected for guest with no conversations: {guest_name}")
                return self._handle_department_selection(
                    guest_data, message_type_info, recipient_number, guest_name, []
                )
            
            # Show department menu
            logger.info(f"Showing menu for checked-in guest: {guest_name}")
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
            'action': 'flow'  # Default to flow webhook
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

        # Note: Guest status verification removed since we now handle all messages through unified webhook system

        # Find existing non-expired conversation for this department
        existing_conv = find_active_department_conversation(conversations, dept_name)

        # Generate success message payload
        success_payload = generate_success_text_payload(recipient_number, dept_name, guest_name)

        if existing_conv:
            # Use existing conversation
            return {
                **guest_data,
                'action': 'relay',
                'selected_department': list_reply_id,
                'target_conversation': self._format_target_conversation(
                    existing_conv, use_existing=True
                ),
                'whatsapp_payload': success_payload
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
                },
                'whatsapp_payload': success_payload
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
                    'message': button_reply.get('id', ''),
                    'message_type': 'text'
                }
            elif interactive_type == 'list_reply':
                list_reply = interactive_data.get('list_reply', {})
                return {
                    'message': list_reply.get('id', ''),
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
            # Extract media ID from the media object
            media_id = None
            media_obj = message_data.get(msg_type, {})
            if media_obj:
                media_id = media_obj.get('id')

            return {
                'message': f'{msg_type.capitalize()} message received',
                'message_type': msg_type,
                'media_id': media_id
            }

        # Fallback for unknown types
        else:
            return {
                'message': 'Message received',
                'message_type': 'text'
            }

    def _handle_button_reply_interactions(self, message_data, message_type_info, response_data):
        """
        Handle special button reply interactions for conversation management

        Returns dict with response data if button was handled, None otherwise
        """
        msg_type = message_data.get('type')

        if msg_type != 'interactive':
            return None

        interactive_data = message_data.get('interactive', {})
        interactive_type = interactive_data.get('type')

        if interactive_type != 'button_reply':
            return None

        button_reply = interactive_data.get('button_reply', {})
        button_id = button_reply.get('id', '')

        # Check if this is a special button ID we need to handle
        if button_id.startswith('accept_reopen_conversation_conv#'):
            return self._handle_accept_reopen_conversation(button_id, response_data)
        elif button_id.startswith('req_fulfilled_conv#'):
            return self._handle_fulfillment_response(button_id, True, response_data)
        elif button_id.startswith('req_unfulfilled_conv#'):
            return self._handle_fulfillment_response(button_id, False, response_data)

        return None

    def _handle_accept_reopen_conversation(self, button_id, response_data):
        """Handle accept_reopen_conversation button click"""
        try:
            # Extract conversation ID
            conversation_id = button_id.split('#', 1)[1]

            # Verify conversation exists
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                logger.warning(f"Conversation {conversation_id} not found for reopen request")
                return {
                    'success': False,
                    'error': 'Conversation not found',
                    'message': 'The conversation you are trying to reopen could not be found.'
                }

            # Create a new message from guest to reactivate conversation
            guest_name = conversation.guest.full_name or 'Guest'
            guest_message = Message.objects.create(
                conversation=conversation,
                sender_type='guest',
                content=guest_name + " has reopened the conversation",
                message_type='text'
            )

            # Update conversation's last message timestamp and preview
            conversation.update_last_message(guest_message.content)

            # Broadcast the "guest reopened conversation" message to staff via WebSocket
            try:
                from .base import async_to_sync, get_channel_layer
                channel_layer = get_channel_layer()
                department_group_name = f"department_{conversation.department.lower()}"

                # Get guest stay info
                from guest.models import Stay
                active_stay = Stay.objects.filter(guest=conversation.guest, status='active').first()

                message_data = {
                    'id': guest_message.id,
                    'conversation_id': conversation.id,
                    'sender_type': 'guest',
                    'sender_name': guest_name,
                    'sender_id': None,
                    'message_type': guest_message.message_type,
                    'content': guest_message.content,
                    'media_url': guest_message.get_media_url,
                    'media_filename': guest_message.media_filename,
                    'is_read': guest_message.is_read,
                    'created_at': guest_message.created_at.isoformat(),
                    'updated_at': guest_message.updated_at.isoformat(),
                    'guest_info': {
                        'id': conversation.guest.id,
                        'name': conversation.guest.full_name,
                        'whatsapp_number': conversation.guest.whatsapp_number,
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
                logger.info(f"Broadcasted guest reopened conversation message to {department_group_name}")
            except Exception as ws_error:
                logger.error(f"Failed to broadcast reopened conversation message: {ws_error}", exc_info=True)

            # Send WhatsApp response
            try:
                from ..utils.whatsapp_utils import send_whatsapp_message_with_media
                send_whatsapp_message_with_media(
                    recipient_number=conversation.guest.whatsapp_number,
                    message_content="You are connected. Please type your message."
                )
                logger.info(f"Sent reconnection message to {conversation.guest.whatsapp_number}")
            except Exception as e:
                logger.error(f"Failed to send reconnection message: {e}")

            logger.info(f"Conversation {conversation_id} reopened by guest")

            return {
                'success': True,
                'message': 'Conversation reopened successfully',
                'conversation_id': conversation.id,
                'message_id': guest_message.id,
                'action': 'conversation_reopened'
            }

        except Exception as e:
            logger.error(f"Error handling accept_reopen_conversation: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Failed to reopen conversation',
                'message': 'An error occurred while reopening the conversation.'
            }

    def _handle_fulfillment_response(self, button_id, is_fulfilled, response_data):
        """Handle req_fulfilled_conv and req_unfulfilled_conv button clicks"""
        try:
            # Extract conversation ID
            conversation_id = button_id.split('#', 1)[1]

            # Verify conversation exists
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                logger.warning(f"Conversation {conversation_id} not found for fulfillment response")
                return {
                    'success': False,
                    'error': 'Conversation not found',
                    'message': 'The conversation could not be found.'
                }

            # Update conversation fulfillment status
            if is_fulfilled:
                conversation.mark_fulfilled(True)
                feedback_text = "fulfilled"
            else:
                conversation.mark_fulfilled(False)
                feedback_text = "not fulfilled"

            # Send WhatsApp feedback confirmation
            try:
                from ..utils.whatsapp_utils import send_whatsapp_message_with_media
                send_whatsapp_message_with_media(
                    recipient_number=conversation.guest.whatsapp_number,
                    message_content="Your feedback has been recorded"
                )
                logger.info(f"Sent feedback confirmation to {conversation.guest.whatsapp_number}")
            except Exception as e:
                logger.error(f"Failed to send feedback confirmation: {e}")

            logger.info(f"Conversation {conversation_id} marked as {feedback_text} by guest")

            return {
                'success': True,
                'message': f'Feedback recorded - request marked as {feedback_text}',
                'conversation_id': conversation.id,
                'action': 'feedback_recorded',
                'is_fulfilled': is_fulfilled
            }

        except Exception as e:
            logger.error(f"Error handling fulfillment response: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Failed to record feedback',
                'message': 'An error occurred while recording your feedback.'
            }

    def _prepare_guest_webhook_data(self, guest_data, message_data, webhook_body=None, target_conversation=None):
        """
        Prepare data for process_guest_webhook function

        Returns a dictionary compatible with GuestMessageSerializer
        """
        guest_info = guest_data.get('guest_info')
        if not guest_info:
            return None

        message_data = guest_data.get('message', {})

        # Prepare webhook data
        webhook_data = {
            'whatsapp_number': guest_info.get('whatsapp_number'),
            'message': message_data.get('message', ''),
            'message_type': message_data.get('message_type', 'text'),
        }

        # Add WhatsApp message ID for deduplication
        if webhook_body and 'entry' in webhook_body:
            try:
                entry = webhook_body.get('entry', [])
                if entry and len(entry) > 0:
                    changes = entry[0].get('changes', [])
                    if changes and len(changes) > 0:
                        value = changes[0].get('value', {})
                        messages = value.get('messages', [])
                        if messages and len(messages) > 0:
                            message = messages[0]
                            webhook_data['whatsapp_message_id'] = message.get('id')
                            # Extract media_id for media messages
                            message_type = message.get('type')
                            if message_type in ['image', 'document', 'video', 'audio']:
                                media_content = message.get(message_type, {})
                                if media_content:
                                    webhook_data['media_id'] = media_content.get('id')
            except Exception as e:
                logger.warning(f"GuestConversationTypeView: Error extracting WhatsApp message ID: {e}")

        # Add conversation info if provided
        if target_conversation:
            if target_conversation.get('use_existing', True) and target_conversation.get('id'):
                # Use existing conversation
                webhook_data['conversation_id'] = target_conversation['id']
            else:
                # Create new conversation - need department
                webhook_data['department'] = target_conversation.get('department')

        # Add media info if present
        if message_data.get('message_type') in ['image', 'document', 'video', 'audio']:
            webhook_data['media_url'] = message_data.get('media_url')
            webhook_data['media_filename'] = message_data.get('media_filename')

        return webhook_data

    def _prepare_flow_webhook_data(self, guest_data, message_data, guest_whatsapp_number=None):
        """
        Prepare data for process_flow_webhook function

        Returns a dictionary compatible with FlowMessageSerializer
        """
        # Use the guest_whatsapp_number parameter that was passed to this method
        whatsapp_number = guest_whatsapp_number

        if not whatsapp_number:
            logger.error("GuestConversationTypeView: No whatsapp number available for flow webhook")
            return None

        # Use the already extracted message from guest_data
        extracted_message = guest_data.get('message', {})
        message_content = extracted_message.get('message', '')
        message_type = extracted_message.get('message_type', 'text')

        logger.info(f"GuestConversationTypeView: Preparing flow webhook - message_content: {message_content}, message_type: {message_type}")

        # Prepare webhook data
        webhook_data = {
            'whatsapp_number': whatsapp_number,
            'message': message_content,
            'message_type': message_type,
        }

        # Add media info if present
        if message_type in ['image', 'document', 'video', 'audio']:
            webhook_data['media_url'] = message_data.get('media_url')
            webhook_data['media_filename'] = message_data.get('media_filename')
            # Include media_id for downloading
            if 'media_id' in extracted_message:
                webhook_data['media_id'] = extracted_message['media_id']

        return webhook_data

    def _execute_webhook_and_merge_result(self, routing_result, guest_data, message_data, webhook_body=None, guest_whatsapp_number=None):
        """
        Execute the appropriate webhook function and merge its result with routing_result

        Args:
            routing_result: The current routing result from _determine_routing_action
            guest_data: Guest information for preparing webhook data
            message_data: Message data from WhatsApp
            webhook_body: Original webhook body for extracting media ID

        Returns:
            Updated routing_result with webhook execution result
        """
        try:
            action = routing_result.get('action')
            logger.info(f"GuestConversationTypeView: Executing webhook with action: {action}")

            if action == 'flow':
                # Handle flow action with flow webhook for automated flows
                logger.info(f"GuestConversationTypeView: Processing flow action")
                logger.info(f"GuestConversationTypeView: guest_whatsapp_number available: {guest_whatsapp_number is not None}")
                if guest_whatsapp_number:
                    logger.info(f"GuestConversationTypeView: Using whatsapp_number: {guest_whatsapp_number}")

                # Prepare flow webhook data
                logger.info(f"GuestConversationTypeView: Preparing flow webhook data")
                flow_webhook_data = self._prepare_flow_webhook_data(
                    guest_data=guest_data,
                    message_data=message_data,
                    guest_whatsapp_number=guest_whatsapp_number
                )
                logger.info(f"GuestConversationTypeView: Flow webhook data prepared: {flow_webhook_data is not None}")

                if flow_webhook_data:
                    logger.info(f"GuestConversationTypeView: Calling handle_incoming_whatsapp_message")
                    logger.info(f"GuestConversationTypeView: DEBUG - whatsapp_number value: {repr(guest_whatsapp_number)}")
                    logger.info(f"GuestConversationTypeView: DEBUG - flow_webhook_data: {flow_webhook_data}")
                    media_id = webhook_body.get('media_id') if webhook_body else None
                    try:
                        logger.info(f"GuestConversationTypeView: About to call handle_incoming_whatsapp_message")
                        flow_response, status_code = handle_incoming_whatsapp_message(
                            guest_whatsapp_number,
                            flow_webhook_data
                        )
                        logger.info(f"GuestConversationTypeView: handle_incoming_whatsapp_message completed with status: {status_code}")
                    except Exception as e:
                        logger.error(f"GuestConversationTypeView: Error in handle_incoming_whatsapp_message: {e}", exc_info=True)
                        logger.error(f"GuestConversationTypeView: DEBUG - guest_whatsapp_number type: {type(guest_whatsapp_number)}")
                        logger.error(f"GuestConversationTypeView: DEBUG - guest_whatsapp_number value: {repr(guest_whatsapp_number)}")
                        raise

                    # Merge flow webhook result into routing result
                    # flow_response is now always a properly formatted WhatsApp payload
                    routing_result.update({
                        'webhook_executed': True,
                        'webhook_result': flow_response,
                        'webhook_status_code': status_code,
                        'whatsapp_payload': flow_response
                    })

            elif action == 'relay':
                # Handle relay action with guest webhook
                webhook_data = self._prepare_guest_webhook_data(
                    guest_data=guest_data,
                    message_data=message_data,
                    webhook_body=webhook_body,
                    target_conversation=routing_result.get('target_conversation')
                )

                if webhook_data:
                    media_id = webhook_body.get('media_id') if webhook_body else None
                    webhook_response, status_code = process_guest_webhook(
                        request_data=webhook_data,
                        media_id=media_id
                    )

                    # Merge webhook result into routing result
                    if webhook_response.get('success'):
                        routing_result.update({
                            'webhook_executed': True,
                            'webhook_result': webhook_response,
                            'webhook_status_code': status_code,
                            'message_id': webhook_response.get('message_id'),
                            'conversation_id': webhook_response.get('conversation_id'),
                            'department': webhook_response.get('department'),
                            'conversation_created': webhook_response.get('conversation_created', False)
                        })
                    else:
                        routing_result.update({
                            'webhook_executed': True,
                            'webhook_error': webhook_response,
                            'webhook_status_code': status_code
                        })

            else:
                # For non-relay actions, we could process through flow webhook if needed
                # For now, the WhatsApp payload is already prepared in the routing result
                # These are typically interactive menu responses
                pass

            return routing_result

        except Exception as e:
            logger.error(f"GuestConversationTypeView: Error executing webhook: {e}", exc_info=True)
            logger.error(f"GuestConversationTypeView: Error type: {type(e).__name__}")
            routing_result.update({
                'webhook_executed': False,
                'webhook_error': str(e)
            })
            return routing_result
