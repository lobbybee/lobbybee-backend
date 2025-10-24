import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from .models import Conversation, Message, ConversationParticipant
from .utils.phone_utils import normalize_phone_number, get_guest_group_name
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

        # Validate user is authenticated and is department staff
        if not self.user.is_authenticated:
            logger.error("Connection rejected: User not authenticated")
            await self.close()
            return

        if self.user.user_type != 'department_staff':
            logger.error(f"Connection rejected: Invalid user type '{self.user.user_type}', expected 'department_staff'")
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
        self.department_group_names = [f"department_{dept}" for dept in self.departments]
        logger.info(f"Department group names: {self.department_group_names}")

        # Add user to all department groups
        for group_name in self.department_group_names:
            await self.channel_layer.group_add(
                group_name,
                self.channel_name
            )
        logger.info(f"User {self.user.username} added to groups: {self.department_group_names}")

        await self.accept()
        logger.info(f"WebSocket connection accepted for user {self.user.username} in departments: {self.departments}")

        # Send connection confirmation to all departments
        for department_name in self.departments:
            group_name = f"department_{department_name}"
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
                department_name = group_name.replace('department_', '')

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

        # Broadcast to relevant department group based on conversation department
        conversation_department = message_data.get('department_name', conversation.department.lower())
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

    async def handle_mark_read(self, data):
        """Handle mark as read request"""
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return

        conversation = await self.get_conversation(conversation_id)
        if conversation and await self.validate_conversation_access(conversation):
            await self.mark_conversation_read(conversation)

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
            'type': 'new_conversation',
            'data': notification
        }))

    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message
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

        # Send confirmation
        await self.send(text_data=json.dumps({
            'type': 'subscribed',
            'data': {
                'conversation_id': conversation_id,
                'message': 'Successfully subscribed to conversation'
            }
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

        # Send confirmation
        await self.send(text_data=json.dumps({
            'type': 'unsubscribed',
            'data': {
                'conversation_id': conversation_id,
                'message': 'Successfully unsubscribed from conversation'
            }
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

        # Update conversation status to closed
        success = await self.close_conversation(conversation)
        if success:
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

            # Send confirmation to the user who closed it
            await self.send(text_data=json.dumps({
                'type': 'conversation_closed',
                'data': {
                    'conversation_id': conversation_id,
                    'message': 'Conversation closed successfully'
                }
            }))
        else:
            await self.send_error('Failed to close conversation')

    @database_sync_to_async
    def get_user_departments(self):
        """Get all departments for the user"""
        # Return user's department list or empty list
        return self.user.department or []

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
        """Close a conversation by setting status to 'closed'"""
        try:
            conversation.status = 'closed'
            conversation.save(update_fields=['status'])
            return True
        except Exception:
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
        
        # Send to relevant department group
        relevant_group = f"department_{conversation.department.lower()}"
        
        # This would be called from outside the consumer when a new conversation is created
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
