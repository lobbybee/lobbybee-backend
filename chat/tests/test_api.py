from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock
import json
from datetime import timedelta

from user.models import User
from guest.models import Guest, Stay
from hotel.models import Hotel, Room, RoomCategory
from chat.models import Conversation, Message, ConversationParticipant

User = get_user_model()


class GuestWebhookViewTest(APITestCase):
    """Test cases for GuestWebhookView"""

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
            email="guest@test.com",
            status='checked_in'
        )
        
        self.stay = Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            check_in_date=timezone.now(),
            check_out_date=timezone.now() + timedelta(days=3),
            status='active'
        )
        
        self.webhook_url = reverse('chat:guest-webhook')

    def test_webhook_creates_conversation_for_new_guest(self):
        """Test webhook creates new conversation for guest"""
        data = {
            'whatsapp_number': '+1234567890',
            'message': 'Hello, I need help',
            'department': 'Reception'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Conversation.objects.count(), 1)
        
        conversation = Conversation.objects.first()
        self.assertEqual(conversation.guest, self.guest)
        self.assertEqual(conversation.hotel, self.hotel)
        self.assertEqual(conversation.department, 'Reception')
        self.assertEqual(conversation.conversation_type, 'service')  # checked_in guest
        self.assertEqual(conversation.status, 'active')
        
        # Check message was created
        self.assertEqual(Message.objects.count(), 1)
        message = Message.objects.first()
        self.assertEqual(message.conversation, conversation)
        self.assertEqual(message.sender_type, 'guest')
        self.assertEqual(message.content, 'Hello, I need help')

    def test_webhook_uses_existing_conversation(self):
        """Test webhook uses existing conversation"""
        # Create existing conversation
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception',
            conversation_type='service'
        )
        
        data = {
            'whatsapp_number': '+1234567890',
            'message': 'Follow up message',
            'department': 'Reception'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Conversation.objects.count(), 1)  # No new conversation
        
        # Check message was added to existing conversation
        self.assertEqual(Message.objects.count(), 1)
        message = Message.objects.first()
        self.assertEqual(message.conversation, conversation)
        self.assertEqual(message.content, 'Follow up message')

    def test_webhook_with_conversation_id(self):
        """Test webhook with conversation_id parameter"""
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception',
            conversation_type='service'
        )
        
        data = {
            'whatsapp_number': '+1234567890',
            'message': 'Reply to specific conversation',
            'conversation_id': conversation.id,
            'department': 'Reception'  # Still need department for webhook logic
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        message = Message.objects.first()
        self.assertEqual(message.conversation, conversation)
        self.assertEqual(message.content, 'Reply to specific conversation')

    def test_webhook_conversation_type_logic(self):
        """Test conversation type determination based on guest status"""
        # Test pending_checkin guest
        self.guest.status = 'pending_checkin'
        self.guest.save()
        
        data = {
            'whatsapp_number': '+1234567890',
            'message': 'I want to check in',
            'department': 'Reception'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        
        conversation = Conversation.objects.first()
        self.assertEqual(conversation.conversation_type, 'checkin')
        
        # Test checked_out guest
        self.guest.status = 'checked_out'
        self.guest.save()
        
        data['message'] = 'Post stay feedback'
        response = self.client.post(self.webhook_url, data, format='json')
        
        # Should create new conversation with general type
        self.assertEqual(Conversation.objects.count(), 2)
        general_conversation = Conversation.objects.last()
        self.assertEqual(general_conversation.conversation_type, 'general')

    def test_webhook_with_media_message(self):
        """Test webhook with media message"""
        data = {
            'whatsapp_number': '+1234567890',
            'message': 'Here is an image',
            'message_type': 'image',
            'media_url': 'https://example.com/image.jpg',
            'media_filename': 'image.jpg',
            'department': 'Reception'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        message = Message.objects.first()
        self.assertEqual(message.message_type, 'image')
        self.assertEqual(message.media_url, 'https://example.com/image.jpg')
        self.assertEqual(message.media_filename, 'image.jpg')

    def test_webhook_invalid_guest(self):
        """Test webhook with invalid guest number"""
        data = {
            'whatsapp_number': '+9999999999',
            'message': 'Test message',
            'department': 'Reception'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)

    def test_webhook_missing_required_fields(self):
        """Test webhook with missing required fields"""
        # Missing whatsapp_number
        data = {
            'message': 'Test message',
            'department': 'Reception'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing message
        data = {
            'whatsapp_number': '+1234567890',
            'department': 'Reception'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_webhook_invalid_department(self):
        """Test webhook with invalid department"""
        data = {
            'whatsapp_number': '+1234567890',
            'message': 'Test message',
            'department': 'Invalid Department'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('chat.views.async_to_sync')
    @patch('chat.views.get_channel_layer')
    def test_webhook_broadcasts_to_websocket(self, mock_get_channel_layer, mock_async_to_sync):
        """Test webhook broadcasts to WebSocket for service conversations"""
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        mock_async_to_sync.return_value = MagicMock()
        
        data = {
            'whatsapp_number': '+1234567890',
            'message': 'Service request',
            'department': 'Reception'
        }
        
        response = self.client.post(self.webhook_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Should broadcast to department group
        mock_async_to_sync.assert_called()


class ConversationListViewTest(APITestCase):
    """Test cases for ConversationListView"""

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
        
        # Create some messages
        Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Guest message'
        )
        
        Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='Staff reply'
        )
        
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')
        self.url = reverse('chat:conversation-list')

    def test_list_conversations_authenticated(self):
        """Test listing conversations when authenticated"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        
        conversation_data = response.data[0]
        self.assertEqual(conversation_data['id'], self.conversation.id)
        self.assertEqual(conversation_data['guest_info']['full_name'], self.guest.full_name)
        self.assertEqual(conversation_data['department'], 'Reception')
        self.assertEqual(conversation_data['unread_count'], 1)  # One unread guest message

    def test_list_conversations_unauthenticated(self):
        """Test listing conversations when not authenticated"""
        self.client.credentials()  # Remove auth
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_conversations_filtered_by_department(self):
        """Test filtering conversations by department"""
        # Create conversation in different department
        other_conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Housekeeping'
        )
        
        response = self.client.get(self.url)
        
        # Should only return Reception conversations
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['department'], 'Reception')

    def test_list_conversations_with_last_message(self):
        """Test conversation list includes last message details"""
        response = self.client.get(self.url)
        
        conversation_data = response.data[0]
        self.assertIn('last_message', conversation_data)
        self.assertIsNotNone(conversation_data['last_message'])
        self.assertEqual(conversation_data['last_message']['content'], 'Staff reply')

    def test_list_conversations_empty(self):
        """Test listing conversations when user has no conversations"""
        # Delete conversation
        self.conversation.delete()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class ConversationDetailViewTest(APITestCase):
    """Test cases for ConversationDetailView"""

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
        
        # Create messages
        self.message1 = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Guest message 1'
        )
        
        self.message2 = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='Staff reply 1'
        )
        
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')
        self.url = reverse('chat:conversation-detail', kwargs={'conversation_id': self.conversation.id})

    def test_get_conversation_details(self):
        """Test getting conversation details"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['conversation']['id'], self.conversation.id)
        self.assertEqual(data['conversation']['guest_info']['full_name'], self.guest.full_name)
        self.assertEqual(data['conversation']['department'], 'Reception')
        self.assertEqual(len(data['messages']), 2)
        
        # Check message details
        messages = data['messages']
        self.assertEqual(messages[0]['content'], 'Guest message 1')
        self.assertEqual(messages[0]['sender_type'], 'guest')
        self.assertEqual(messages[1]['content'], 'Staff reply 1')
        self.assertEqual(messages[1]['sender_type'], 'staff')

    def test_get_conversation_unauthorized(self):
        """Test getting conversation from different department"""
        # Create user from different department
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123',
            user_type='department_staff',
            hotel=self.hotel,
            department=['Housekeeping']
        )
        
        token = RefreshToken.for_user(other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_conversation_not_found(self):
        """Test getting non-existent conversation"""
        url = reverse('chat:conversation-detail', kwargs={'conversation_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_conversation_unauthenticated(self):
        """Test getting conversation without authentication"""
        self.client.credentials()  # Remove auth
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CreateConversationViewTest(APITestCase):
    """Test cases for CreateConversationView"""

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
        
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')
        self.url = reverse('chat:conversation-create')

    def test_create_conversation_success(self):
        """Test successful conversation creation"""
        data = {
            'guest_whatsapp_number': '+1234567890',
            'department_type': 'Reception'
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Conversation.objects.count(), 1)
        
        conversation = Conversation.objects.first()
        self.assertEqual(conversation.guest, self.guest)
        self.assertEqual(conversation.hotel, self.hotel)
        self.assertEqual(conversation.department, 'Reception')
        # Note: conversation_type defaults to 'general' when created via API
        self.assertEqual(conversation.conversation_type, 'general')

    def test_create_conversation_invalid_guest(self):
        """Test creating conversation with invalid guest"""
        data = {
            'guest_whatsapp_number': '+9999999999',
            'department_type': 'Reception'
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Guest not found', str(response.data))

    def test_create_conversation_guest_no_active_stay(self):
        """Test creating conversation for guest without active stay"""
        # Delete the stay
        self.stay.delete()
        
        data = {
            'guest_whatsapp_number': '+1234567890',
            'department_type': 'Reception'
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('does not have an active stay', str(response.data))

    def test_create_conversation_unauthenticated(self):
        """Test creating conversation without authentication"""
        self.client.credentials()  # Remove auth
        
        data = {
            'guest_whatsapp_number': '+1234567890',
            'department_type': 'Reception'
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_conversation_invalid_department(self):
        """Test creating conversation with invalid department"""
        data = {
            'guest_whatsapp_number': '+1234567890',
            'department_type': 'Invalid Department'
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MarkMessagesReadViewTest(APITestCase):
    """Test cases for MarkMessagesReadView"""

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
        
        # Create unread messages
        self.message1 = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Guest message 1'
        )
        
        self.message2 = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Guest message 2'
        )
        
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')
        self.url = reverse('chat:mark-messages-read')

    def test_mark_all_messages_read(self):
        """Test marking all messages as read in conversation"""
        # Verify messages are initially unread
        self.assertEqual(Message.objects.filter(is_read=False).count(), 2)
        
        data = {
            'conversation_id': self.conversation.id
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All messages should be marked as read
        self.assertEqual(Message.objects.filter(is_read=False).count(), 0)
        
        # Check participant was created/updated
        participant = ConversationParticipant.objects.get(
            conversation=self.conversation,
            staff=self.user
        )
        self.assertIsNotNone(participant.last_read_at)

    def test_mark_specific_messages_read(self):
        """Test marking specific messages as read"""
        # Create additional message
        message3 = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Guest message 3'
        )
        
        data = {
            'conversation_id': self.conversation.id,
            'message_ids': [self.message1.id, message3.id]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check specific messages are marked as read
        self.message1.refresh_from_db()
        message3.refresh_from_db()
        self.message2.refresh_from_db()
        
        self.assertTrue(self.message1.is_read)
        self.assertTrue(message3.is_read)
        self.assertFalse(self.message2.is_read)  # Should remain unread

    def test_mark_messages_unauthorized_conversation(self):
        """Test marking messages in unauthorized conversation"""
        # Create conversation in different department
        other_conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Housekeeping'
        )
        
        data = {
            'conversation_id': other_conversation.id
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mark_messages_invalid_conversation(self):
        """Test marking messages for non-existent conversation"""
        data = {
            'conversation_id': 99999
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_messages_unauthenticated(self):
        """Test marking messages without authentication"""
        self.client.credentials()  # Remove auth
        
        data = {
            'conversation_id': self.conversation.id
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TypingIndicatorViewTest(APITestCase):
    """Test cases for typing indicator view"""

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
        
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')
        self.url = reverse('chat:send-typing-indicator')

    @patch('chat.views.async_to_sync')
    @patch('chat.views.get_channel_layer')
    def test_send_typing_indicator_started(self, mock_get_channel_layer, mock_async_to_sync):
        """Test sending typing indicator started"""
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        mock_async_to_sync.return_value = MagicMock()
        
        data = {
            'conversation_id': self.conversation.id,
            'is_typing': True
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should broadcast to department group
        mock_async_to_sync.assert_called()

    @patch('chat.views.async_to_sync')
    @patch('chat.views.get_channel_layer')
    def test_send_typing_indicator_stopped(self, mock_get_channel_layer, mock_async_to_sync):
        """Test sending typing indicator stopped"""
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        mock_async_to_sync.return_value = MagicMock()
        
        data = {
            'conversation_id': self.conversation.id,
            'is_typing': False
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should broadcast to department group
        mock_async_to_sync.assert_called()

    def test_typing_indicator_unauthorized_conversation(self):
        """Test typing indicator for unauthorized conversation"""
        # Create conversation in different department
        other_conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Housekeeping'
        )
        
        data = {
            'conversation_id': other_conversation.id,
            'is_typing': True
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_typing_indicator_invalid_conversation(self):
        """Test typing indicator for non-existent conversation"""
        data = {
            'conversation_id': 99999,
            'is_typing': True
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_typing_indicator_unauthenticated(self):
        """Test typing indicator without authentication"""
        self.client.credentials()  # Remove auth
        
        data = {
            'conversation_id': self.conversation.id,
            'is_typing': True
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_typing_indicator_missing_fields(self):
        """Test typing indicator with missing required fields"""
        # Missing conversation_id
        data = {
            'is_typing': True
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing is_typing
        data = {
            'conversation_id': self.conversation.id
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)