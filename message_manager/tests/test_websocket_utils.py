from django.test import TestCase
from unittest.mock import patch, MagicMock, AsyncMock
from guest.models import Guest, Hotel, Room, Stay
from hotel.models import Department, RoomCategory
from message_manager.models import Conversation
from message_manager.services.websocket_utils import notify_department_new_conversation
import datetime
from django.utils import timezone


class WebSocketUtilsTestCase(TestCase):
    def setUp(self):
        # Create test hotel
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            is_active=True
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
            status="pending",
            check_in_date=now,
            check_out_date=now + datetime.timedelta(days=3)
        )
        
        # Create test conversation
        self.conversation = Conversation.objects.create(
            stay=self.stay,
            status='relay',
            department=self.department
        )

    @patch('message_manager.services.websocket_utils.get_channel_layer')
    def test_notify_department_new_conversation(self, mock_get_channel_layer):
        """Test that notify_department_new_conversation sends a message to the channel layer"""
        # Mock the channel layer with an async mock
        mock_channel_layer = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        
        # Call the function
        notify_department_new_conversation(self.conversation)
        
        # Verify that group_send was called
        mock_channel_layer.group_send.assert_called_once()
        
        # Verify the arguments passed to group_send
        args, kwargs = mock_channel_layer.group_send.call_args
        group_name = args[0]
        message_data = args[1]
        
        # Check that the group name is correct
        self.assertEqual(group_name, f"department_{self.department.id}")
        
        # Check that the message contains the expected data
        self.assertEqual(message_data["type"], "new_conversation")
        self.assertEqual(message_data["stay_id"], str(self.stay.id))
        self.assertEqual(message_data["conversation_id"], str(self.conversation.id))

    def test_notify_department_new_conversation_no_department(self):
        """Test that notify_department_new_conversation handles conversations without departments"""
        # Create a new stay for this test
        now = timezone.now()
        new_stay = Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            status="active",
            check_in_date=now,
            check_out_date=now + datetime.timedelta(days=2)
        )
        
        # Create a conversation without a department
        conversation_no_dept = Conversation.objects.create(
            stay=new_stay,
            status='relay',
            department=None
        )
        
        # This should not raise an exception
        try:
            notify_department_new_conversation(conversation_no_dept)
            success = True
        except Exception:
            success = False
            
        # The function should complete without error
        self.assertTrue(success)