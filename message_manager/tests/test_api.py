from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from guest.models import Guest, Hotel, Room, Stay
from hotel.models import Department, RoomCategory
from message_manager.models import Conversation
from message_manager.serializers import ConversationListSerializer
from user.models import User
import datetime
from django.utils import timezone


class ConversationViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create test hotel
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            is_active=True
        )
        
        # Create test user (staff member) and associate with hotel
        self.staff_user = User.objects.create_user(
            username='teststaff',
            email='teststaff@example.com',
            password='testpass123',
            hotel=self.hotel,
            user_type='receptionist'
        )
        
        # Create test room category
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Standard Room",
            description="A standard hotel room",
            base_price=100.00,
            max_occupancy=2
        )
        
        # Create test room
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            floor=1,
            category=self.room_category
        )
        
        # Create test department
        self.department = Department.objects.create(
            hotel=self.hotel,
            name="Reception",
            department_type="reception",
            operating_hours_start="08:00:00",
            operating_hours_end="20:00:00"
        )
        
        # Create test guest
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            full_name="Test Guest"
        )
        
        # Create test stay
        now = timezone.now()
        self.stay = Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            status="active",
            check_in_date=now,
            check_out_date=now + datetime.timedelta(days=3)
        )
        
        # Create test conversation
        self.conversation = Conversation.objects.create(
            stay=self.stay,
            status='relay',
            department=self.department
        )

    def test_conversation_list_unauthenticated(self):
        """Test that unauthenticated users cannot access conversation list"""
        response = self.client.get('/api/message_manager/conversations/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_conversation_list_authenticated(self):
        """Test that authenticated staff can access conversation list"""
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get('/api/message_manager/conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_conversation_list_content(self):
        """Test that conversation list contains correct data"""
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get('/api/message_manager/conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that we get the conversation we created
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['stay_id'], self.stay.id)
        self.assertEqual(response.data['results'][0]['guest_name'], self.guest.full_name)
        self.assertEqual(response.data['results'][0]['room_number'], self.room.room_number)

    def test_conversation_detail(self):
        """Test that we can retrieve conversation details"""
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(f'/api/message_manager/conversations/{self.conversation.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check the detailed data
        self.assertEqual(response.data['stay_id'], self.stay.id)
        self.assertEqual(response.data['guest_name'], self.guest.full_name)
        self.assertEqual(response.data['room_number'], self.room.room_number)
        self.assertEqual(response.data['guest_phone'], self.guest.whatsapp_number)
        self.assertEqual(response.data['guest_phone'], self.guest.whatsapp_number)

    def test_conversation_messages(self):
        """Test that we can retrieve conversation messages"""
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(f'/api/message_manager/conversations/{self.conversation.id}/messages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])  # No messages yet

    def test_active_conversations(self):
        """Test that we can retrieve active conversations"""
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get('/api/message_manager/conversations/active_conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)