import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from .models import Conversation, Message, ConversationParticipant
from .utils.phone_utils import normalize_phone_number, get_guest_group_name
from .utils.whatsapp_utils import send_whatsapp_message_with_media, send_whatsapp_media_with_link, send_whatsapp_button_message
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for department-based chat system
    Handles real-time communication between hotel staff and guests
    """

    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']

        # Debug logging
        logger.info(f"WebSocket connection attempt - User: {self.user}")
        logger.info(f"Is authenticated: {self.user.is_authenticated}")
        logger.info(f"User type: {getattr(self.user, 'user_type', 'NOT_SET')}")
        logger.info(f"User departments: {getattr(self.user, 'department', 'NOT_SET')}")

        # Validate user is authenticated and is staff member
        if not self.user.is_authenticated:
            logger.error("Connection rejected: User not authenticated")
            await self.close()
            return

        # Allow access for receptionist, management, and department staff
        allowed_user_types = ['department_staff', 'receptionist', 'manager', 'hotel_admin']
        if self.user.user_type not in allowed_user_types:
            logger.error(f"Connection rejected: Invalid user type '{self.user.user_type}', allowed types: {allowed_user_types}")
            await self.close()
            return

        # Get user departments from model
        self.departments = await self.get_user_departments()
        if not self.departments:
            logger.error("Connection rejected: User has no departments assigned")
            await self.close()
            return

        logger.info(f"User departments: {self.departments}")

        # Create list of department group names
        self.department_group_names = [f"department_{dept.lower()}" for dept in self.departments]
        logger.info(f"Department group names: {self.department_group_names}")

        # Add user to all department groups
        for group_name in self.department_group_names:
            await self.channel_layer.group_add(
                group_name,
                self.channel_name
            )
            logger.info(f"User {self.user.username} added to group: {group_name}")
        logger.info(f"User {self.user.username} added to all groups: {self.department_group_names}")

        await self.accept()
        logger.info(f"WebSocket connection accepted for user {self.user.username} in departments: {self.departments}")

        # Send connection confirmation to all departments
        for department_name in self.departments:
            group_name = f"department_{department_name.lower()}"
            await self.channel_layer.group_send(
                group_name,
                {
                    'type': 'user_status',
                    'message': {
                        'type': 'user_connected',
                        'user_id': self.user.id,
                        'user_name': self.user.get_full_name() or self.user.username,
                        'department': department_name
                    }
                }
            )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'department_group_names'):
            # Remove user from all department groups
            for group_name in self.department_group_names:
                await self.channel_layer.group_discard(
                    group_name,
                    self.channel_name
                )

                # Extract department name from group name
                department_name = group_name.replace('department_', '').lower()

                # Notify other users about disconnection
                await self.channel_layer.group_send(
                    group_name,
                    {
                        'type': 'user_status',
                        'message': {
                            'type': 'user_disconnected',
                            'user_id': self.user.id,
                            'user_name': self.user.get_full_name() or self.user.username,
                            'department': department_name
                        }
                    }
                )

        # Note: Conversation-specific groups are automatically cleaned up when
        # the WebSocket disconnects, so no manual cleanup needed

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'text')

            if message_type == 'text':
                await self.handle_text_message(data)
            elif message_type == 'media':
                await self.handle_media_message(data)
            elif message_type == 'mark_read':
                await self.handle_mark_read(data)
            elif message_type == 'typing':
                await self.handle_typing_indicator(data)
            elif message_type == 'subscribe_conversation':
                await self.handle_subscribe_conversation(data)
            elif message_type == 'unsubscribe_conversation':
                await self.handle_unsubscribe_conversation(data)
            elif message_type == 'close_conversation':
                await self.handle_close_conversation(data)
            elif message_type == 'reopen-temporary':
                await self.handle_reopen_temporary(data)
            else:
                await self.send_error('Invalid message type')

        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            await self.send_error(f'Error processing message: {str(e)}')

    async def handle_text_message(self, data):
        """Handle text message from staff"""
        content = data.get('content', '').strip()
        conversation_id = data.get('conversation_id')

        if not content:
            await self.send_error('Message content cannot be empty')
            return

        if not conversation_id:
            await self.send_error('Conversation ID is required')
            return

        # Validate conversation and permissions
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            await self.send_error('Conversation not found')
            return

        if not await self.validate_conversation_access(conversation):
            await self.send_error('Access denied to this conversation')
            return

        # Create message
        message = await self.create_message(conversation, content, 'text')

        # Add user as participant if not already
        await self.add_participant(conversation)

        # Serialize message
        message_data = await self.serialize_message(message)

        # Send WhatsApp message for 'service' conversation types
        if conversation.conversation_type == 'service':
            await self.send_whatsapp_message(conversation, content, 'text')

        # Broadcast to relevant department group based on conversation department
        conversation_department = conversation.department.lower()
        relevant_group = f"department_{conversation_department}"
        
        await self.channel_layer.group_send(
            relevant_group,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )

        # Also send conversation update notification to department members
        # who are not subscribed to this specific conversation
        await self.channel_layer.group_send(
            relevant_group,
            {
                'type': 'conversation_notification',
                'notification': {
                    'type': 'new_message',
                    'data': {
                        'conversation_id': conversation_id,
                        'guest_name': message_data['guest_info']['name'],
                        'department': conversation_department,
                        'last_message_preview': content[:50],
                        'last_message_at': message_data['created_at'],
                        'message_from': message_data['sender_name']
                    }
                }
            }
        )

        # Broadcast to guest group (use normalized number for consistency)
        guest_group_name = get_guest_group_name(conversation.guest.whatsapp_number)
        await self.channel_layer.group_send(
            guest_group_name,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )

        # Send acknowledgment to the sender
        await self.send_acknowledgment(message_data, 'received')

    async def handle_media_message(self, data):
        """Handle media message from staff"""
        conversation_id = data.get('conversation_id')
        file_url = data.get('file_url')
        filename = data.get('filename')
        file_type = data.get('file_type')
        caption = data.get('caption', '')

        if not conversation_id:
            await self.send_error('Conversation ID is required for media messages')
            return

        if not file_url:
            await self.send_error('File URL is required for media messages')
            return

        if not filename:
            await self.send_error('Filename is required for media messages')
            return

        if not file_type:
            await self.send_error('File type is required for media messages')
            return

        # Validate conversation and permissions
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            await self.send_error('Conversation not found')
            return

        if not await self.validate_conversation_access(conversation):
            await self.send_error('Access denied to this conversation')
            return

        # Validate message type
        valid_types = ['image', 'document', 'video', 'audio']
        if file_type not in valid_types:
            await self.send_error(f'Invalid file type. Must be one of: {valid_types}')
            return

        # Create message with media file from URL
        message_content = caption or filename
        message = await self.create_media_message(conversation, message_content, file_type, file_url, filename)

        # Add user as participant if not already
        await self.add_participant(conversation)

        # Serialize message
        message_data = await self.serialize_message(message)

        # Send WhatsApp message for 'service' conversation types using direct link
        if conversation.conversation_type == 'service':
            await self.send_whatsapp_media_with_link(conversation, message_content, file_type, file_url, filename)

        # Broadcast to relevant department group based on conversation department
        conversation_department = conversation.department.lower()
        relevant_group = f"department_{conversation_department}"
            
        await self.channel_layer.group_send(
            relevant_group,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )

        # Also send conversation update notification to department members
        # who are not subscribed to this specific conversation
        await self.channel_layer.group_send(
            relevant_group,
            {
                'type': 'conversation_notification',
                'notification': {
                    'type': 'new_message',
                    'data': {
                        'conversation_id': conversation_id,
                        'guest_name': message_data['guest_info']['name'],
                        'department': conversation_department,
                        'last_message_preview': f"[{file_type.upper()}] {filename[:30]}",
                        'last_message_at': message_data['created_at'],
                        'message_from': message_data['sender_name']
                    }
                }
            }
        )

        # Broadcast to guest group (use normalized number for consistency)
        guest_group_name = get_guest_group_name(conversation.guest.whatsapp_number)
        await self.channel_layer.group_send(
            guest_group_name,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )

        # Send acknowledgment to the sender
        await self.send_acknowledgment(message_data, 'received')

    async def handle_mark_read(self, data):
        """Handle mark as read request"""
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            await self.send_error('Conversation ID is required for mark_read')
            return

        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            await self.send_error('Conversation not found')
            return

        if not await self.validate_conversation_access(conversation):
            await self.send_error('Access denied to this conversation')
            return

        await self.mark_conversation_read(conversation)
        
        # Send acknowledgment for successful mark as read
        await self.send(text_data=json.dumps({
            'type': 'acknowledgment',
            'status': 'marked_read',
            'conversation_id': conversation_id,
            'timestamp': timezone.now().isoformat()
        }))

    async def handle_typing_indicator(self, data):
        """Handle typing indicator"""
        conversation_id = data.get('conversation_id')
        is_typing = data.get('is_typing', False)

        if not conversation_id:
            return

        conversation = await self.get_conversation(conversation_id)
        if conversation and await self.validate_conversation_access(conversation):
            # Send to the specific department group for this conversation
            conversation_department = conversation.department.lower()
            relevant_group = f"department_{conversation_department}"
            
            await self.channel_layer.group_send(
                relevant_group,
                {
                    'type': 'typing_indicator',
                    'message': {
                        'conversation_id': conversation_id,
                        'user_id': self.user.id,
                        'user_name': self.user.get_full_name() or self.user.username,
                        'is_typing': is_typing
                    }
                }
            )

    async def chat_message(self, event):
        """Handle chat message broadcast"""
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': message
        }))

    async def user_status(self, event):
        """Handle user status updates"""
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'data': message
        }))

    async def typing_indicator(self, event):
        """Handle typing indicator broadcasts"""
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'data': message
        }))

    async def conversation_notification(self, event):
        """Handle conversation update notifications"""
        notification = event['notification']
        await self.send(text_data=json.dumps({
            'type': 'conversation_update',
            'data': notification
        }))

    async def new_conversation_notification(self, event):
        """Handle new conversation notifications"""
        notification = event['notification']
        await self.send(text_data=json.dumps({
            'type': notification.get('type', 'new_conversation'),
            'data': notification.get('data', notification)
        }))

    async def new_checkin_notification(self, event):
        """Handle new check-in notifications"""
        notification = event['notification']

        # Only send to staff members of the same hotel
        # The notification includes hotel_id to verify
        notification_data = notification['data']

        # Check if user's hotel matches the notification's hotel
        # Use database_sync_to_async to safely access the hotel field
        @database_sync_to_async
        def get_user_hotel_id():
            if hasattr(self.user, 'hotel') and self.user.hotel:
                return str(self.user.hotel.id)
            return None

        user_hotel_id = await get_user_hotel_id()

        if user_hotel_id:
            notification_hotel_id = notification_data.get('hotel_id')
            if notification_hotel_id == user_hotel_id:
                # User is from the same hotel, send the notification
                await self.send(text_data=json.dumps({
                    'type': 'new_checkin',
                    'data': notification_data
                }))
                logger.info(f"Sent new check-in notification to user {self.user.username} for hotel {user_hotel_id}")
            else:
                # User is from a different hotel, don't send
                logger.info(f"Filtered out new check-in notification for hotel {notification_hotel_id} from user {self.user.username} at hotel {user_hotel_id}")
        else:
            # User doesn't have a hotel assigned, don't send
            logger.warning(f"User {self.user.username} has no hotel assigned, filtering out new check-in notification")

    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message
        }))

    async def send_acknowledgment(self, message_data, status='received'):
        """Send acknowledgment message to client"""
        await self.send(text_data=json.dumps({
            'type': 'acknowledgment',
            'status': status,
            'message_id': message_data['id'],
            'timestamp': message_data['created_at'],
            'conversation_id': message_data['conversation_id']
        }))

    async def handle_subscribe_conversation(self, data):
        """Handle subscription to a specific conversation"""
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            await self.send_error('Conversation ID is required')
            return

        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            await self.send_error('Conversation not found')
            return

        if not await self.validate_conversation_access(conversation):
            await self.send_error('Access denied to this conversation')
            return

        # Add user to conversation-specific group
        conversation_group = f"conversation_{conversation_id}"
        await self.channel_layer.group_add(
            conversation_group,
            self.channel_name
        )

        # Send acknowledgment for successful subscription
        await self.send(text_data=json.dumps({
            'type': 'acknowledgment',
            'status': 'subscribed',
            'conversation_id': conversation_id,
            'timestamp': timezone.now().isoformat()
        }))

    async def handle_unsubscribe_conversation(self, data):
        """Handle unsubscription from a specific conversation"""
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return

        # Remove user from conversation-specific group
        conversation_group = f"conversation_{conversation_id}"
        await self.channel_layer.group_discard(
            conversation_group,
            self.channel_name
        )

        # Send acknowledgment for successful unsubscription
        await self.send(text_data=json.dumps({
            'type': 'acknowledgment',
            'status': 'unsubscribed',
            'conversation_id': conversation_id,
            'timestamp': timezone.now().isoformat()
        }))

    async def handle_close_conversation(self, data):
        """Handle closing a conversation"""
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            await self.send_error('Conversation ID is required')
            return

        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            await self.send_error('Conversation not found')
            return

        if not await self.validate_conversation_access(conversation):
            await self.send_error('Access denied to this conversation')
            return

        # Update conversation status to closed and set fulfillment tracking
        success = await self.close_conversation(conversation)
        if success:
            # Send WhatsApp fulfillment feedback message for 'service' conversation types
            if conversation.conversation_type == 'service':
                try:
                    await self.send_fulfillment_feedback_message(conversation)
                except Exception as e:
                    logger.error(f"Error sending fulfillment feedback for conversation {conversation_id}: {e}")

            # Notify all relevant department members about the conversation update
            conversation_department = conversation.department.lower()
            relevant_group = f"department_{conversation_department}"
            
            await self.channel_layer.group_send(
                relevant_group,
                {
                    'type': 'conversation_notification',
                    'notification': {
                        'type': 'conversation_closed',
                        'conversation_id': conversation_id,
                        'department': conversation_department,
                        'updated_by': self.user.get_full_name() or self.user.username,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )
            
            # Send acknowledgment to the user who closed the conversation
            await self.send(text_data=json.dumps({
                'type': 'acknowledgment',
                'status': 'conversation_closed',
                'conversation_id': conversation_id,
                'timestamp': timezone.now().isoformat()
            }))
        else:
            await self.send_error('Failed to close conversation - database update failed')

    async def handle_reopen_temporary(self, data):
        """Handle sending a WhatsApp button message to reopen a conversation temporarily"""
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            await self.send_error('Conversation ID is required')
            return

        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            await self.send_error('Conversation not found')
            return

        if not await self.validate_conversation_access(conversation):
            await self.send_error('Access denied to this conversation')
            return

        # Only send WhatsApp button message for 'service' conversation types
        if conversation.conversation_type != 'service':
            await self.send_error('WhatsApp button messages are only supported for service conversations')
            return

        # Get guest's WhatsApp number
        guest_whatsapp_number = conversation.guest.whatsapp_number
        if not guest_whatsapp_number:
            await self.send_error('Guest has no WhatsApp number')
            return

        # Get current department name for the message
        current_department = conversation.department.capitalize() if conversation.department else 'service'

        # Create the WhatsApp button message
        message_text = f"There is an update to your {current_department} conversation, do you want to continue?"
        buttons = [
            {
                "type": "reply",
                "reply": {
                    "id": f"accept_reopen_conversation_conv#{conversation_id}",
                    "title": "Continue"
                }
            }
        ]

        try:
            # Run the sync function in a thread to avoid blocking the async consumer
            import asyncio
            loop = asyncio.get_event_loop()
            
            def send_button_message():
                try:
                    response = send_whatsapp_button_message(
                        recipient_number=guest_whatsapp_number,
                        message_text=message_text,
                        buttons=buttons
                    )
                    logger.info(f"WhatsApp button message sent successfully for conversation {conversation.id}: {response}")
                    return True, response
                except Exception as e:
                    logger.error(f"Failed to send WhatsApp button message: {e}")
                    return False, str(e)
            
            success, result = await loop.run_in_executor(None, send_button_message)
            
            if success:
                # Send acknowledgment to the staff member
                await self.send(text_data=json.dumps({
                    'type': 'acknowledgment',
                    'status': 'reopen_button_sent',
                    'conversation_id': conversation_id,
                    'timestamp': timezone.now().isoformat()
                }))
            else:
                await self.send_error(f'Failed to send WhatsApp button message: {result}')
                
        except Exception as e:
            logger.error(f"Error in handle_reopen_temporary: {e}", exc_info=True)
            await self.send_error(f'Error sending WhatsApp button message: {str(e)}')

    @database_sync_to_async
    def get_user_departments(self):
        """Get all departments for the user"""
        # Ensure department is always returned as a list
        departments = self.user.department or []
        
        # If department is a string, convert it to a list
        if isinstance(departments, str):
            return [departments]
        elif isinstance(departments, list):
            return departments
        else:
            return []

    @database_sync_to_async
    def get_conversation(self, conversation_id):
        """Get conversation by ID"""
        try:
            return Conversation.objects.select_related(
                'guest', 'hotel'
            ).get(id=conversation_id)
        except ObjectDoesNotExist:
            return None

    @database_sync_to_async
    def validate_conversation_access(self, conversation):
        """Validate user can access this conversation"""
        return (
            conversation.hotel == self.user.hotel and
            conversation.department.lower() in [dept.lower() for dept in self.departments]
        )

    @database_sync_to_async
    def create_message(self, conversation, content, message_type='text'):
        """Create a new message"""
        message = Message.objects.create(
            conversation=conversation,
            sender_type='staff',
            sender=self.user,
            message_type=message_type,
            content=content
        )
        
        # Update conversation's last message
        conversation.update_last_message(content)
        return message

    @database_sync_to_async
    def create_media_message(self, conversation, content, message_type, file_url, filename):
        """Create a new media message with file attachment using direct URL"""
        message = Message.objects.create(
            conversation=conversation,
            sender_type='staff',
            sender=self.user,
            message_type=message_type,
            content=content,
            media_url=file_url,
            media_filename=filename
        )
        
        # Update conversation's last message
        conversation.update_last_message(content)
        return message

    @database_sync_to_async
    def add_participant(self, conversation):
        """Add user as conversation participant"""
        participant, created = ConversationParticipant.objects.get_or_create(
            conversation=conversation,
            staff=self.user,
            defaults={'is_active': True}
        )

        if not created and not participant.is_active:
            participant.is_active = True
            participant.save()

    @database_sync_to_async
    def mark_conversation_read(self, conversation):
        """Mark conversation as read for this user"""
        try:
            participant = ConversationParticipant.objects.get(
                conversation=conversation,
                staff=self.user
            )
            participant.mark_conversation_read()
        except ObjectDoesNotExist:
            pass

    @database_sync_to_async
    def serialize_message(self, message):
        """Serialize message for WebSocket transmission"""
        return {
            'id': message.id,
            'conversation_id': message.conversation.id,
            'sender_type': message.sender_type,
            'sender_name': message.get_sender_display_name(),
            'sender_id': message.sender.id if message.sender else None,
            'message_type': message.message_type,
            'content': message.content,
            'media_url': message.media_url,
            'media_filename': message.media_filename,
            'is_read': message.is_read,
            'created_at': message.created_at.isoformat(),
            'updated_at': message.updated_at.isoformat(),
            'guest_info': {
                'id': message.conversation.guest.id,
                'name': message.conversation.guest.full_name,
                'whatsapp_number': message.conversation.guest.whatsapp_number,
                'room_number': message.conversation.guest.stays.filter(
                    status='active'
                ).first().room.room_number if message.conversation.guest.stays.filter(status='active').exists() else None
            },
            'department_name': message.conversation.department.lower()
        }

    @database_sync_to_async
    def close_conversation(self, conversation):
        """Close a conversation by setting status to 'closed' and initializing fulfillment tracking"""
        try:
            conversation.status = 'closed'
            # Initialize fulfillment tracking when conversation is closed
            update_fields = ['status']
            if not conversation.is_request_fulfilled:
                # Only set these if not already fulfilled
                conversation.fulfilled_at = None
                conversation.fulfillment_notes = None
                update_fields.extend(['fulfilled_at', 'fulfillment_notes'])
            
            conversation.save(update_fields=update_fields)
            logger.info(f"Successfully closed conversation {conversation.id}")
            return True
        except Exception as e:
            logger.error(f"Error closing conversation {conversation.id}: {e}", exc_info=True)
            return False

    async def send_whatsapp_message(self, conversation, content, message_type='text'):
        """Send WhatsApp message to guest for 'service' conversation types"""
        try:
            # Only send WhatsApp messages for 'service' conversation types
            if conversation.conversation_type != 'service':
                logger.info(f"Skipping WhatsApp message for conversation type: {conversation.conversation_type}")
                return True

            # Get guest's WhatsApp number
            guest_whatsapp_number = conversation.guest.whatsapp_number
            if not guest_whatsapp_number:
                logger.warning(f"Guest {conversation.guest.id} has no WhatsApp number")
                return False

            # Send WhatsApp message using the utility function
            logger.info(f"Sending WhatsApp message to {guest_whatsapp_number} for conversation {conversation.id}")
            
            # Run the sync function in a thread to avoid blocking the async consumer
            import asyncio
            loop = asyncio.get_event_loop()
            
            def send_message():
                try:
                    response = send_whatsapp_message_with_media(
                        recipient_number=guest_whatsapp_number,
                        message_content=content,
                        media_id=None,
                        media_file=None
                    )
                    logger.info(f"WhatsApp message sent successfully: {response}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to send WhatsApp message: {e}")
                    return False
            
            result = await loop.run_in_executor(None, send_message)
            return result
            
        except Exception as e:
            logger.error(f"Error in send_whatsapp_message: {e}", exc_info=True)
            return False

    async def send_whatsapp_media_with_link(self, conversation, content, media_type, media_url, filename=None):
        """Send WhatsApp media message to guest using direct link"""
        try:
            # Only send WhatsApp messages for 'service' conversation types
            if conversation.conversation_type != 'service':
                logger.info(f"Skipping WhatsApp media message for conversation type: {conversation.conversation_type}")
                return True

            # Get guest's WhatsApp number
            guest_whatsapp_number = conversation.guest.whatsapp_number
            if not guest_whatsapp_number:
                logger.warning(f"Guest {conversation.guest.id} has no WhatsApp number")
                return False

            # Send WhatsApp media message using the utility function
            logger.info(f"Sending WhatsApp media message to {guest_whatsapp_number} for conversation {conversation.id}")
            
            # Run the sync function in a thread to avoid blocking the async consumer
            import asyncio
            loop = asyncio.get_event_loop()
            
            def send_media():
                try:
                    response = send_whatsapp_media_with_link(
                        recipient_number=guest_whatsapp_number,
                        media_url=media_url,
                        media_type=media_type,
                        caption=content,
                        filename=filename
                    )
                    logger.info(f"WhatsApp media message sent successfully: {response}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to send WhatsApp media message: {e}")
                    return False
            
            result = await loop.run_in_executor(None, send_media)
            return result
            
        except Exception as e:
            logger.error(f"Error in send_whatsapp_media_with_link: {e}", exc_info=True)
            return False

    async def send_fulfillment_feedback_message(self, conversation):
        """Send WhatsApp message with fulfillment feedback buttons"""
        try:
            # Only send WhatsApp messages for 'service' conversation types
            if conversation.conversation_type != 'service':
                logger.info(f"Skipping fulfillment feedback message for conversation type: {conversation.conversation_type}")
                return True

            # Get guest's WhatsApp number
            guest_whatsapp_number = conversation.guest.whatsapp_number
            if not guest_whatsapp_number:
                logger.warning(f"Guest {conversation.guest.id} has no WhatsApp number")
                return False

            # Create the fulfillment feedback message
            message_text = "The conversation is successfully closed, were your request fulfilled?"
            buttons = [
                {
                    "type": "reply",
                    "reply": {
                        "id": f"req_fulfilled_conv#{conversation.id}",
                        "title": "Yes"
                    }
                },
                {
                    "type": "reply", 
                    "reply": {
                        "id": f"req_unfulfilled_conv#{conversation.id}",
                        "title": "No"
                    }
                }
            ]

            # Run the sync function in a thread to avoid blocking the async consumer
            import asyncio
            loop = asyncio.get_event_loop()
            
            def send_feedback_message():
                try:
                    response = send_whatsapp_button_message(
                        recipient_number=guest_whatsapp_number,
                        message_text=message_text,
                        buttons=buttons
                    )
                    logger.info(f"Fulfillment feedback message sent successfully for conversation {conversation.id}: {response}")
                    return True, response
                except Exception as e:
                    logger.error(f"Failed to send fulfillment feedback message: {e}")
                    return False, str(e)
            
            success, result = await loop.run_in_executor(None, send_feedback_message)
            return success
            
        except Exception as e:
            logger.error(f"Error in send_fulfillment_feedback_message: {e}", exc_info=True)
            return False

    @database_sync_to_async
    def notify_new_conversation(self, conversation):
        """Notify department members about new conversation"""
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
        
        # This would be called from outside the consumer when a new conversation is created
        # The actual group sending happens in the calling code
        return conversation_data


# Utility functions for sending notifications from outside consumers
async def notify_new_conversation_to_department(conversation):
    """
    Send notification to all connected staff in a department about a new conversation
    This function can be called from views or signals when a new conversation is created
    """
    from channels.layers import get_channel_layer
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
    
    # Send to relevant department group
    relevant_group = f"department_{conversation.department.lower()}"
    
    await channel_layer.group_send(
        relevant_group,
        {
            'type': 'new_conversation_notification',
            'notification': {
                'type': 'new_conversation',
                'data': conversation_data
            }
        }
    )


async def notify_conversation_update_to_department(conversation, update_type='updated'):
    """
    Send notification to all connected staff in a department about conversation updates
    This function can be called from views when a conversation is updated
    Only sends to users who are not subscribed to the specific conversation
    """
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    
    conversation_data = {
        'id': conversation.id,
        'guest_name': conversation.guest.full_name,
        'department': conversation.department.lower(),
        'conversation_type': conversation.conversation_type,
        'status': conversation.status,
        'updated_at': conversation.updated_at.isoformat(),
        'last_message_preview': conversation.last_message_preview,
        'last_message_at': conversation.last_message_at.isoformat() if conversation.last_message_at else None
    }
    
    # Send to relevant department group
    relevant_group = f"department_{conversation.department.lower()}"
    
    await channel_layer.group_send(
        relevant_group,
        {
            'type': 'conversation_notification',
            'notification': {
                'type': update_type,
                'data': conversation_data,
                'message': f'Conversation {update_type}'
            }
        }
    )


class GuestChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for guest connections
    Guests connect via their WhatsApp number
    """

    async def connect(self):
        """Handle guest WebSocket connection"""
        raw_whatsapp_number = self.scope['url_route']['kwargs']['whatsapp_number']
        self.whatsapp_number = normalize_phone_number(raw_whatsapp_number)
        
        # If normalization fails, close connection
        if not self.whatsapp_number:
            logger.error(f"Invalid WhatsApp number format: {raw_whatsapp_number}")
            await self.close()
            return

        # Create guest group name (WebSocket-safe)
        self.guest_group_name = get_guest_group_name(self.whatsapp_number)
        if not self.guest_group_name:
            logger.error(f"Failed to create guest group name for: {self.whatsapp_number}")
            await self.close()
            return

        # Validate guest exists and has active stay
        if not await self.validate_guest():
            await self.close()
            return

        # Add guest to their group
        await self.channel_layer.group_add(
            self.guest_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Handle guest disconnection"""
        if hasattr(self, 'guest_group_name'):
            await self.channel_layer.group_discard(
                self.guest_group_name,
                self.channel_name
            )

    async def chat_message(self, event):
        """Handle incoming chat messages"""
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': message
        }))

    @database_sync_to_async
    def validate_guest(self):
        """Validate guest exists and has active stay"""
        try:
            from guest.models import Guest, Stay
            guest = Guest.objects.get(whatsapp_number=self.whatsapp_number)
            return Stay.objects.filter(guest=guest, status='active').exists()
        except ObjectDoesNotExist:
            return False
