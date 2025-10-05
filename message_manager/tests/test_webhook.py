from django.test import TestCase, Client
from django.utils import timezone
from guest.models import Guest, Hotel, Room, Stay
from hotel.models import Department, RoomCategory
from message_manager.models import Conversation
import datetime


class WhatsAppWebhookTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.webhook_url = '/api/message_manager/webhook/whatsapp/'
        
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
        
        # Create test stay with required dates
        now = timezone.now()
        self.stay = Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            status="pending",
            check_in_date=now,
            check_out_date=now + datetime.timedelta(days=3)
        )

    def test_webhook_endpoint_exists(self):
        """Test that the webhook endpoint exists and accepts POST requests"""
        response = self.client.post(self.webhook_url, data={}, content_type='application/json')
        # Should not return 404
        self.assertNotEqual(response.status_code, 404)

    def test_webhook_returns_json_response(self):
        """Test that the webhook returns a JSON response"""
        data = {
            "test": "data"
        }
        response = self.client.post(self.webhook_url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')