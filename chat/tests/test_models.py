from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from unittest.mock import patch, MagicMock
from user.models import User
from guest.models import Guest, Stay
from hotel.models import Hotel, Room, RoomCategory
from chat.models import Conversation, Message, ConversationParticipant


class ConversationModelTest(TestCase):
    """Test cases for Conversation model"""

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

    def test_conversation_creation(self):
        """Test basic conversation creation"""
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception',
            conversation_type='service'
        )
        
        self.assertEqual(conversation.guest, self.guest)
        self.assertEqual(conversation.hotel, self.hotel)
        self.assertEqual(conversation.department, 'Reception')
        self.assertEqual(conversation.conversation_type, 'service')
        self.assertEqual(conversation.status, 'active')
        self.assertIsNone(conversation.last_message_at)
        self.assertEqual(conversation.last_message_preview, '')

    def test_conversation_string_representation(self):
        """Test conversation __str__ method"""
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Housekeeping',
            conversation_type='service'
        )
        
        expected = f"Conversation: {self.guest.full_name} -> Housekeeping (Service)"
        self.assertEqual(str(conversation), expected)

    def test_conversation_default_values(self):
        """Test default field values"""
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel
        )
        
        self.assertEqual(conversation.department, 'Reception')
        self.assertEqual(conversation.conversation_type, 'general')
        self.assertEqual(conversation.status, 'active')

    def test_conversation_choices(self):
        """Test all choice fields work correctly"""
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Room Service',
            conversation_type='checkin',
            status='closed'
        )
        
        self.assertEqual(conversation.department, 'Room Service')
        self.assertEqual(conversation.conversation_type, 'checkin')
        self.assertEqual(conversation.status, 'closed')

    def test_conversation_unique_together_constraint(self):
        """Test unique_together constraint"""
        Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception',
            conversation_type='service',
            status='active'
        )
        
        # Try to create duplicate
        with self.assertRaises(Exception):  # Should raise IntegrityError
            Conversation.objects.create(
                guest=self.guest,
                hotel=self.hotel,
                department='Reception',
                conversation_type='service',
                status='active'
            )

    def test_update_last_message_method(self):
        """Test update_last_message method"""
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception'
        )
        
        # Test with short message
        conversation.update_last_message("Hello world")
        conversation.refresh_from_db()
        
        self.assertIsNotNone(conversation.last_message_at)
        self.assertEqual(conversation.last_message_preview, "Hello world")
        
        # Test with long message (should be truncated to 255 characters)
        long_message = "This is a very long message that should be truncated to 255 characters " * 10
        conversation.update_last_message(long_message)
        conversation.refresh_from_db()
        
        self.assertEqual(len(conversation.last_message_preview), 255)
        # The message is just truncated, doesn't necessarily end with "..."
        self.assertEqual(conversation.last_message_preview, long_message[:255])

    def test_conversation_indexes(self):
        """Test that indexes are properly defined"""
        # This test checks that the model has the expected indexes
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception'
        )
        
        # Test that we can query efficiently using indexed fields
        # (This is more of a smoke test - actual index testing would require DB inspection)
        conversations_by_guest = Conversation.objects.filter(guest=self.guest, status='active')
        self.assertIn(conversation, conversations_by_guest)
        
        conversations_by_hotel = Conversation.objects.filter(hotel=self.hotel, department='Reception', status='active')
        self.assertIn(conversation, conversations_by_hotel)


class MessageModelTest(TestCase):
    """Test cases for Message model"""

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

    def test_message_creation_guest_sender(self):
        """Test message creation with guest sender"""
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Hello, I need help'
        )
        
        self.assertEqual(message.conversation, self.conversation)
        self.assertEqual(message.sender_type, 'guest')
        self.assertIsNone(message.sender)
        self.assertEqual(message.content, 'Hello, I need help')
        self.assertEqual(message.message_type, 'text')
        self.assertFalse(message.is_read)
        self.assertIsNone(message.read_at)

    def test_message_creation_staff_sender(self):
        """Test message creation with staff sender"""
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='How can I help you?'
        )
        
        self.assertEqual(message.sender_type, 'staff')
        self.assertEqual(message.sender, self.user)
        self.assertEqual(message.content, 'How can I help you?')

    def test_message_string_representation(self):
        """Test message __str__ method"""
        # Test with guest message
        guest_message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Hello from guest'
        )
        expected = f"guest: Hello from guest"
        self.assertEqual(str(guest_message), expected)
        
        # Test with staff message
        staff_message = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='Hello from staff'
        )
        expected = f"{self.user.get_full_name()}: Hello from staff"
        self.assertEqual(str(staff_message), expected)
        
        # Test with long content
        long_message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='This is a very long message that should be truncated in the string representation'
        )
        expected = "Guest: This is a very long message that should be truncated in the string..."
        self.assertEqual(str(long_message), expected)

    def test_message_media_fields(self):
        """Test message media fields"""
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            message_type='image',
            content='Image message',
            media_url='https://example.com/image.jpg',
            media_filename='image.jpg'
        )
        
        self.assertEqual(message.message_type, 'image')
        self.assertEqual(message.media_url, 'https://example.com/image.jpg')
        self.assertEqual(message.media_filename, 'image.jpg')

    def test_mark_as_read_method(self):
        """Test mark_as_read method"""
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Test message'
        )
        
        # Initially unread
        self.assertFalse(message.is_read)
        self.assertIsNone(message.read_at)
        
        # Mark as read
        message.mark_as_read()
        message.refresh_from_db()
        
        self.assertTrue(message.is_read)
        self.assertIsNotNone(message.read_at)
        
        # Test marking already read message (should not change read_at)
        original_read_at = message.read_at
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = timezone.now() + timedelta(hours=1)
            message.mark_as_read()
            message.refresh_from_db()
        
        # read_at should not have changed
        self.assertEqual(message.read_at, original_read_at)

    def test_get_sender_display_name(self):
        """Test get_sender_display_name method"""
        # Test guest message
        guest_message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Guest message'
        )
        self.assertEqual(guest_message.get_sender_display_name(), 'Test Guest')
        
        # Test staff message with full name
        self.user.first_name = 'John'
        self.user.last_name = 'Doe'
        self.user.save()
        
        staff_message = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='Staff message'
        )
        self.assertEqual(staff_message.get_sender_display_name(), 'John Doe')
        
        # Test staff message without full name
        self.user.first_name = ''
        self.user.last_name = ''
        self.user.save()
        staff_message = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='Staff message'
        )
        self.assertEqual(staff_message.get_sender_display_name(), 'testuser')

    def test_message_choices(self):
        """Test all choice fields work correctly"""
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            message_type='document',
            content='Document message'
        )
        
        self.assertEqual(message.sender_type, 'staff')
        self.assertEqual(message.message_type, 'document')

    def test_message_indexes(self):
        """Test that indexes are properly defined"""
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Test message'
        )
        
        # Test efficient queries using indexed fields
        messages_by_conversation = Message.objects.filter(conversation=self.conversation).order_by('-created_at')
        self.assertIn(message, messages_by_conversation)
        
        messages_by_sender = Message.objects.filter(sender_type='guest', is_read=False)
        self.assertIn(message, messages_by_sender)


class ConversationParticipantModelTest(TestCase):
    """Test cases for ConversationParticipant model"""

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

    def test_participant_creation(self):
        """Test basic participant creation"""
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation,
            staff=self.user
        )
        
        self.assertEqual(participant.conversation, self.conversation)
        self.assertEqual(participant.staff, self.user)
        self.assertTrue(participant.is_active)
        self.assertIsNotNone(participant.joined_at)
        self.assertIsNone(participant.last_read_at)

    def test_participant_string_representation(self):
        """Test participant __str__ method"""
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation,
            staff=self.user
        )
        
        expected = f"{self.user.get_full_name()} in {self.conversation}"
        self.assertEqual(str(participant), expected)

    def test_participant_unique_together_constraint(self):
        """Test unique_together constraint"""
        ConversationParticipant.objects.create(
            conversation=self.conversation,
            staff=self.user
        )
        
        # Try to create duplicate
        with self.assertRaises(Exception):  # Should raise IntegrityError
            ConversationParticipant.objects.create(
                conversation=self.conversation,
                staff=self.user
            )

    def test_mark_conversation_read_method(self):
        """Test mark_conversation_read method"""
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation,
            staff=self.user
        )
        
        # Create some unread messages
        Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Unread message 1'
        )
        Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Unread message 2'
        )
        
        # Initially no read time and messages are unread
        self.assertIsNone(participant.last_read_at)
        
        # Mark conversation as read
        participant.mark_conversation_read()
        participant.refresh_from_db()
        
        # Check participant read time
        self.assertIsNotNone(participant.last_read_at)
        
        # Check all messages are marked as read
        unread_messages = self.conversation.messages.filter(is_read=False)
        self.assertEqual(unread_messages.count(), 0)

    def test_participant_indexes(self):
        """Test that indexes are properly defined"""
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation,
            staff=self.user
        )
        
        # Test efficient queries using indexed fields
        participants_by_staff = ConversationParticipant.objects.filter(staff=self.user, is_active=True)
        self.assertIn(participant, participants_by_staff)
        
        participants_by_conversation = ConversationParticipant.objects.filter(conversation=self.conversation, is_active=True)
        self.assertIn(participant, participants_by_conversation)


class ModelRelationshipsTest(TestCase):
    """Test cases for model relationships and cascading behavior"""

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

    def test_conversation_message_relationship(self):
        """Test conversation-message relationship"""
        message1 = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Message 1'
        )
        message2 = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='Message 2'
        )
        
        # Test conversation messages
        messages = self.conversation.messages.all()
        self.assertEqual(messages.count(), 2)
        self.assertIn(message1, messages)
        self.assertIn(message2, messages)
        
        # Test message conversation
        self.assertEqual(message1.conversation, self.conversation)
        self.assertEqual(message2.conversation, self.conversation)

    def test_conversation_participant_relationship(self):
        """Test conversation-participant relationship"""
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation,
            staff=self.user
        )
        
        # Test conversation participants
        participants = self.conversation.participants.all()
        self.assertEqual(participants.count(), 1)
        self.assertIn(participant, participants)
        
        # Test participant conversation
        self.assertEqual(participant.conversation, self.conversation)

    def test_cascade_delete_behavior(self):
        """Test cascade delete behavior"""
        # Create related objects
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Test message'
        )
        
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation,
            staff=self.user
        )
        
        # Verify objects exist
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(ConversationParticipant.objects.count(), 1)
        
        # Delete conversation (should cascade delete messages and participants)
        self.conversation.delete()
        
        # Verify cascade deletion
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(ConversationParticipant.objects.count(), 0)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_user_delete_behavior(self):
        """Test user deletion behavior (SET_NULL)"""
        # Create message with staff sender
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='staff',
            sender=self.user,
            content='Staff message'
        )
        
        # Create participant
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation,
            staff=self.user
        )
        
        # Delete user
        self.user.delete()
        
        # Check message sender is set to NULL
        message.refresh_from_db()
        self.assertIsNone(message.sender)
        
        # Participant should be deleted (CASCADE)
        self.assertEqual(ConversationParticipant.objects.count(), 0)

    def test_guest_delete_behavior(self):
        """Test guest deletion behavior (CASCADE)"""
        # Create conversation with guest
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            content='Guest message'
        )
        
        # Delete guest
        self.guest.delete()
        
        # Conversation should be deleted (CASCADE)
        self.assertEqual(Conversation.objects.count(), 0)
        
        # Message should be deleted (CASCADE through conversation)
        self.assertEqual(Message.objects.count(), 0)