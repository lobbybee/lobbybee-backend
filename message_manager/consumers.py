import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Conversation, Message
import logging

# Import AnonymousUser inside functions to avoid AppRegistryNotReady error
# from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class StaffConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Import AnonymousUser here to avoid AppRegistryNotReady error
        from django.contrib.auth.models import AnonymousUser
        
        if self.scope["user"] == AnonymousUser():
            await self.close()
            return

        self.user_group = f"staff_{self.scope['user'].id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Leave all groups
        await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive_json(self, content):
        command = content.get('command')

        if command == 'subscribe_to_conversation':
            await self.subscribe_to_conversation(content['stay_id'])
        elif command == 'unsubscribe_from_conversation':
            await self.unsubscribe_from_conversation(content['stay_id'])
        elif command == 'send_message':
            await self.send_staff_message(content)

    async def subscribe_to_conversation(self, stay_id):
        conversation_group = f"conversation_{stay_id}"
        await self.channel_layer.group_add(conversation_group, self.channel_name)

    async def unsubscribe_from_conversation(self, stay_id):
        conversation_group = f"conversation_{stay_id}"
        await self.channel_layer.group_discard(conversation_group, self.channel_name)

    async def send_staff_message(self, content):
        stay_id = content['stay_id']
        message_text = content['text']

        # Save message to database
        await self.save_staff_message(stay_id, message_text)

        # Send to guest via WhatsApp (placeholder)
        await self.send_to_whatsapp(stay_id, message_text)

        # Broadcast to other staff in conversation
        await self.channel_layer.group_send(
            f"conversation_{stay_id}",
            {
                'type': 'new_message',
                'stay_id': stay_id,
                'content': message_text,
                'sender_type': 'staff',
                'sender_name': self.scope['user'].get_full_name(),
                'timestamp': timezone.now().isoformat()
            }
        )

    @database_sync_to_async
    def save_staff_message(self, stay_id, message_text):
        try:
            conversation = Conversation.objects.get(stay__id=stay_id)
            Message.objects.create(
                conversation=conversation,
                content=message_text,
                sender_type='staff',
                staff_sender=self.scope['user']
            )
            return True
        except Conversation.DoesNotExist:
            logger.error(f"Conversation for stay {stay_id} does not exist")
            return False

    async def send_to_whatsapp(self, stay_id, message_text):
        # Placeholder for WhatsApp API integration
        # This will be implemented in Phase 5
        logger.info(f"Sending message to WhatsApp for stay {stay_id}: {message_text}")

    async def new_message(self, event):
        await self.send_json(event)

    async def new_conversation(self, event):
        await self.send_json(event)