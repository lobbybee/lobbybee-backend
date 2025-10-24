from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock, AsyncMock
import json
import asyncio
from datetime import timedelta

from user.models import User
from guest.models import Guest, Stay
from hotel.models import Hotel, Room, RoomCategory
from chat.models import Conversation, Message, ConversationParticipant
from chat.consumers import ChatConsumer, GuestChatConsumer

User = get_user_model()


class ChatConsumerLogicTest(TestCase):
    """Test cases for ChatConsumer logic without full WebSocket setup"""

    def setUp(self):
        """Set up test data"""
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            address="Test Address",
            city="Test City",
            state="Test State",
            country="Test Country",
            pincode="123456",
            phone="+1234567890",
            email="test@hotel.com"
        )
        
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Standard Room",
            description="A standard room",
            base_price=100.00,
            max_occupancy=2
        )
        
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            category=self.room_category,
            floor=1
        )
        
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            full_name="Test Guest",
            email="guest@test.com"
        )
        
        self.stay = Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            check_in_date=timezone.now(),
            check_out_date=timezone.now() + timedelta(days=3),
            status='active'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='department_staff',
            hotel=self.hotel,
            department=['Reception']
        )
        
        self.conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception'
        )

    @database_sync_to_async
    def get_consumer_instance(self, department_name='Reception'):
        """Get consumer instance for testing"""
        consumer = ChatConsumer()
        consumer.department_name = department_name
        consumer.user = self.user
        consumer.channel_name = 'test_channel'
        consumer.department_group_name = f"department_{department_name}"
        return consumer

    async def test_validate_department_access_success(self):
        """Test successful department access validation"""
        consumer = await self.get_consumer_instance()
        
        # User has access to Reception
        has_access = await consumer.validate_department_access()
        self.assertTrue(has_access)

    async def test_validate_department_access_failure(self):
        """Test failed department access validation"""
        consumer = await self.get_consumer_instance('Housekeeping')
        
        # User doesn't have access to Housekeeping
        has_access = await consumer.validate_department_access()
        self.assertFalse(has_access)

    async def test_get_conversation_success(self):
        """Test successful conversation retrieval"""
        consumer = await self.get_consumer_instance()
        
        conversation = await consumer.get_conversation(self.conversation.id)
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.id, self.conversation.id)

    async def test_get_conversation_not_found(self):
        """Test conversation retrieval when not found"""
        consumer = await self.get_consumer_instance()
        
        conversation = await consumer.get_conversation(99999)
        self.assertIsNone(conversation)

    async def test_validate_conversation_access_success(self):
        """Test successful conversation access validation"""
        consumer = await self.get_consumer_instance()
        
        has_access = await consumer.validate_conversation_access(self.conversation)
        self.assertTrue(has_access)

    async def test_validate_conversation_access_wrong_hotel(self):
        """Test conversation access validation with wrong hotel"""
        other_hotel = Hotel.objects.create(
            name="Other Hotel",
            address="Other Address",
            city="Other City",
            state="Other State",
            country="Other Country",
            pincode="654321",
            phone="+0987654321",
            email="other@hotel.com"
        )
        
        other_conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=other_hotel,
            department='Reception'
        )
        
        consumer = await self.get_consumer_instance()
        
        has_access = await consumer.validate_conversation_access(other_conversation)
        self.assertFalse(has_access)

    async def test_validate_conversation_access_wrong_department(self):
        """Test conversation access validation with wrong department"""
        other_conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Housekeeping'
        )
        
        consumer = await self.get_consumer_instance()
        
        has_access = await consumer.validate_conversation_access(other_conversation)
        self.assertFalse(has_access)

    async def test_create_message(self):
        """Test message creation"""
        consumer = await self.get_consumer_instance()
        
        message = await consumer.create_message(
            self.conversation,
            'Test message content',
            'text'
        )
        
        self.assertIsNotNone(message)
        self.assertEqual(message.conversation, self.conversation)
        self.assertEqual(message.sender_type, 'staff')
        self.assertEqual(message.sender, self.user)
        self.assertEqual(message.content, 'Test message content')
        self.assertEqual(message.message_type, 'text')
        
        # Check conversation was updated
        await database_sync_to_async(self.conversation.refresh_from_db)()
        self.assertEqual(self.conversation.last_message_preview, 'Test message content')
        self.assertIsNotNone(self.conversation.last_message_at)

    async def test_add_participant(self):
        """Test adding user as conversation participant"""
        consumer = await self.get_consumer_instance()
        
        await consumer.add_participant(self.conversation)
        
        participant = await database_sync_to_async(
            ConversationParticipant.objects.get
        )(conversation=self.conversation, staff=self.user)
        
        self.assertIsNotNone(participant)
        self.assertTrue(participant.is_active)

    async def test_mark_conversation_read(self):
        """Test marking conversation as read"""
        consumer = await self.get_consumer_instance()
        
        # Create unread message
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Unread message'
        )
        
        await consumer.mark_conversation_read(self.conversation)
        
        # Check message was marked as read
        await database_sync_to_async(message.refresh_from_db)()
        self.assertTrue(message.is_read)
        
        # Check participant was created/updated
        participant = await database_sync_to_async(
            ConversationParticipant.objects.get
        )(conversation=self.conversation, staff=self.user)
        self.assertIsNotNone(participant.last_read_at)

    async def test_serialize_message(self):
        """Test message serialization"""
        consumer = await self.get_consumer_instance()
        
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='Test message'
        )
        
        serialized = await consumer.serialize_message(message)
        
        self.assertEqual(serialized['id'], message.id)
        self.assertEqual(serialized['conversation_id'], self.conversation.id)
        self.assertEqual(serialized['sender_type'], 'staff')
        self.assertEqual(serialized['sender_name'], self.user.get_full_name() or self.user.username)
        self.assertEqual(serialized['content'], 'Test message')
        self.assertEqual(serialized['message_type'], 'text')
        self.assertFalse(serialized['is_read'])
        self.assertIn('guest_info', serialized)
        self.assertEqual(serialized['guest_info']['id'], self.guest.id)
        self.assertEqual(serialized['guest_info']['name'], self.guest.full_name)


class GuestChatConsumerLogicTest(TestCase):
    """Test cases for GuestChatConsumer logic without full WebSocket setup"""

    def setUp(self):
        """Set up test data"""
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            address="Test Address",
            city="Test City",
            state="Test State",
            country="Test Country",
            pincode="123456",
            phone="+1234567890",
            email="test@hotel.com"
        )
        
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Standard Room",
            description="A standard room",
            base_price=100.00,
            max_occupancy=2
        )
        
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            category=self.room_category,
            floor=1
        )
        
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            full_name="Test Guest",
            email="guest@test.com"
        )
        
        self.stay = Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            check_in_date=timezone.now(),
            check_out_date=timezone.now() + timedelta(days=3),
            status='active'
        )

    @database_sync_to_async
    def get_consumer_instance(self, whatsapp_number='+1234567890'):
        """Get consumer instance for testing"""
        consumer = GuestChatConsumer()
        consumer.whatsapp_number = whatsapp_number
        consumer.guest_group_name = f"guest_{whatsapp_number}"
        return consumer

    async def test_validate_guest_success(self):
        """Test successful guest validation"""
        consumer = await self.get_consumer_instance()
        
        is_valid = await consumer.validate_guest()
        self.assertTrue(is_valid)

    async def test_validate_guest_not_found(self):
        """Test guest validation when guest not found"""
        consumer = await self.get_consumer_instance('+9999999999')
        
        is_valid = await consumer.validate_guest()
        self.assertFalse(is_valid)

    async def test_validate_guest_no_active_stay(self):
        """Test guest validation when no active stay"""
        # Delete active stay
        await database_sync_to_async(self.stay.delete)()
        
        consumer = await self.get_consumer_instance()
        
        is_valid = await consumer.validate_guest()
        self.assertFalse(is_valid)


class WebSocketIntegrationTest(TestCase):
    """Integration tests for WebSocket functionality using mocked components"""

    def setUp(self):
        """Set up test data"""
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            address="Test Address",
            city="Test City",
            state="Test State",
            country="Test Country",
            pincode="123456",
            phone="+1234567890",
            email="test@hotel.com"
        )
        
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Standard Room",
            description="A standard room",
            base_price=100.00,
            max_occupancy=2
        )
        
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            category=self.room_category,
            floor=1
        )
        
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            full_name="Test Guest",
            email="guest@test.com"
        )
        
        self.stay = Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            check_in_date=timezone.now(),
            check_out_date=timezone.now() + timedelta(days=3),
            status='active'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='department_staff',
            hotel=self.hotel,
            department=['Reception']
        )
        
        self.conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception'
        )

    @patch('chat.consumers.get_channel_layer')
    async def test_message_broadcast_flow(self, mock_get_layer):
        """Test complete message broadcast flow"""
        mock_channel_layer = AsyncMock()
        mock_get_layer.return_value = mock_channel_layer
        
        consumer = ChatConsumer()
        consumer.department_name = 'Reception'
        consumer.user = self.user
        consumer.channel_name = 'test_channel'
        consumer.department_group_name = 'department_Reception'
        
        # Mock group_add
        mock_channel_layer.group_add = AsyncMock()
        
        # Test message handling
        message_data = {
            'type': 'text',
            'content': 'Hello from staff',
            'conversation_id': self.conversation.id
        }
        
        # Mock the group_send calls
        mock_channel_layer.group_send = AsyncMock()
        
        # Process the message
        await consumer.handle_text_message(message_data)
        
        # Verify message was created
        messages = await database_sync_to_async(
            lambda: list(Message.objects.all())
        )()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, 'Hello from staff')
        self.assertEqual(messages[0].sender_type, 'staff')
        self.assertEqual(messages[0].sender, self.user)
        
        # Verify broadcasts were called
        self.assertTrue(mock_channel_layer.group_send.called)

    @patch('chat.consumers.get_channel_layer')
    async def test_typing_indicator_broadcast(self, mock_get_layer):
        """Test typing indicator broadcast"""
        mock_channel_layer = AsyncMock()
        mock_get_layer.return_value = mock_channel_layer
        
        consumer = ChatConsumer()
        consumer.department_name = 'Reception'
        consumer.user = self.user
        consumer.channel_name = 'test_channel'
        consumer.department_group_name = 'department_Reception'
        
        # Mock group_add
        mock_channel_layer.group_add = AsyncMock()
        mock_channel_layer.group_send = AsyncMock()
        
        # Test typing indicator
        message_data = {
            'type': 'typing',
            'conversation_id': self.conversation.id,
            'is_typing': True
        }
        
        await consumer.handle_typing_indicator(message_data)
        
        # Verify broadcast was called
        mock_channel_layer.group_send.assert_called()
        call_args = mock_channel_layer.group_send.call_args
        self.assertEqual(call_args[0][0], 'department_Reception')
        self.assertEqual(call_args[0][1]['type'], 'typing_indicator')

    async def test_error_handling_invalid_json(self):
        """Test error handling for invalid JSON"""
        consumer = ChatConsumer()
        consumer.channel_name = 'test_channel'
        
        # Mock send_error method
        consumer.send_error = AsyncMock()
        
        # Test invalid JSON handling
        await consumer.receive('invalid json data')
        
        # Verify error was sent
        consumer.send_error.assert_called_once_with('Invalid JSON format')

    async def test_error_handling_invalid_message_type(self):
        """Test error handling for invalid message type"""
        consumer = ChatConsumer()
        consumer.channel_name = 'test_channel'
        
        # Mock send_error method
        consumer.send_error = AsyncMock()
        
        # Test invalid message type
        message_data = {
            'type': 'invalid_type',
            'content': 'Test message'
        }
        
        await consumer.receive(json.dumps(message_data))
        
        # Verify error was sent
        consumer.send_error.assert_called_once_with('Invalid message type')

    async def test_error_handling_empty_message(self):
        """Test error handling for empty message content"""
        consumer = ChatConsumer()
        consumer.channel_name = 'test_channel'
        consumer.user = self.user
        
        # Mock send_error method and validation methods
        consumer.send_error = AsyncMock()
        consumer.get_conversation = AsyncMock(return_value=self.conversation)
        consumer.validate_conversation_access = AsyncMock(return_value=True)
        
        # Test empty message
        message_data = {
            'type': 'text',
            'content': '',
            'conversation_id': self.conversation.id
        }
        
        await consumer.receive(json.dumps(message_data))
        
        # Verify error was sent
        consumer.send_error.assert_called_once_with('Message content cannot be empty')

    async def test_error_handling_missing_conversation_id(self):
        """Test error handling for missing conversation ID"""
        consumer = ChatConsumer()
        consumer.channel_name = 'test_channel'
        consumer.user = self.user
        
        # Mock send_error method
        consumer.send_error = AsyncMock()
        
        # Test missing conversation_id
        message_data = {
            'type': 'text',
            'content': 'Test message'
        }
        
        await consumer.receive(json.dumps(message_data))
        
        # Verify error was sent
        consumer.send_error.assert_called_once_with('Conversation ID is required')


class ConsumerPermissionTest(TestCase):
    """Test consumer permission logic"""

    def setUp(self):
        """Set up test data"""
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            address="Test Address",
            city="Test City",
            state="Test State",
            country="Test Country",
            pincode="123456",
            phone="+1234567890",
            email="test@hotel.com"
        )
        
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Standard Room",
            description="A standard room",
            base_price=100.00,
            max_occupancy=2
        )
        
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            category=self.room_category,
            floor=1
        )
        
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            full_name="Test Guest",
            email="guest@test.com"
        )
        
        self.stay = Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            check_in_date=timezone.now(),
            check_out_date=timezone.now() + timedelta(days=3),
            status='active'
        )

    async def test_department_staff_permissions(self):
        """Test department staff user permissions"""
        user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='testpass123',
            user_type='department_staff',
            hotel=self.hotel,
            department=['Reception', 'Housekeeping']
        )
        
        consumer = ChatConsumer()
        consumer.user = user
        consumer.department_name = 'Reception'
        
        # Should have access to Reception
        has_access = await consumer.validate_department_access()
        self.assertTrue(has_access)
        
        # Should have access to Housekeeping
        consumer.department_name = 'Housekeeping'
        has_access = await consumer.validate_department_access()
        self.assertTrue(has_access)
        
        # Should not have access to Management
        consumer.department_name = 'Management'
        has_access = await consumer.validate_department_access()
        self.assertFalse(has_access)

    async def test_non_department_staff_permissions(self):
        """Test non-department staff user permissions"""
        user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='testpass123',
            user_type='hotel_admin',
            hotel=self.hotel
        )
        
        consumer = ChatConsumer()
        consumer.user = user
        consumer.department_name = 'Reception'
        
        # Should not have access
        has_access = await consumer.validate_department_access()
        self.assertFalse(has_access)

    async def test_unauthenticated_user_permissions(self):
        """Test unauthenticated user permissions"""
        user = User()
        user.is_authenticated = False
        
        consumer = ChatConsumer()
        consumer.user = user
        consumer.department_name = 'Reception'
        
        # Should not have access
        has_access = await consumer.validate_department_access()
        self.assertFalse(has_access)