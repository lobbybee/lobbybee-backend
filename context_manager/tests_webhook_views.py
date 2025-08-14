from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from context_manager.views.webhook import WhatsAppWebhookView
from context_manager.models import ConversationContext, FlowStep
from hotel.models import Hotel, Room, RoomCategory
from guest.models import Guest, Stay
from datetime import datetime, timedelta
import uuid

class WhatsAppWebhookViewTest(TestCase):
    """Test the WhatsApp Webhook view"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create a hotel
        self.hotel = Hotel.objects.create(
            id=uuid.uuid4(),
            name="Test Hotel",
            email="test@hotel.com",
            phone="+1234567890"
        )
        
        # Create a room category
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Standard Room",
            description="A standard room",
            base_price=100.00,
            max_occupancy=2
        )
        
        # Create a room
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            category=self.room_category,
            floor=1,
            status="available"
        )
        
        # Create a guest
        self.guest = Guest.objects.create(
            full_name="John Doe",
            email="john.doe@example.com",
            whatsapp_number="+1987654321",
            nationality="American"
        )
        
        # Create a stay
        self.stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            status="active",
            check_in_date=datetime.now(),
            check_out_date=datetime.now() + timedelta(days=3),
            number_of_guests=2
        )

    def test_webhook_post_with_twilio_format(self):
        """Test webhook POST with Twilio-like format"""
        url = reverse('whatsapp-webhook')
        data = {
            'From': 'whatsapp:+1987654321',
            'Body': 'Hello'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('message', response.data)

    def test_webhook_post_with_generic_format(self):
        """Test webhook POST with generic format"""
        url = reverse('whatsapp-webhook')
        data = {
            'from_no': '+1987654321',
            'message': 'Hello'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('message', response.data)

    def test_webhook_post_with_alternative_format(self):
        """Test webhook POST with alternative format"""
        url = reverse('whatsapp-webhook')
        data = {
            'from': '+1987654321',
            'body': 'Hello'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('message', response.data)

    def test_webhook_post_with_empty_data(self):
        """Test webhook POST with empty data"""
        url = reverse('whatsapp-webhook')
        data = {}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('message', response.data)

    def test_webhook_post_with_invalid_data(self):
        """Test webhook POST with invalid data"""
        url = reverse('whatsapp-webhook')
        data = "invalid data"
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('status', response.data)
        self.assertIn('message', response.data)

    def test_handle_initial_message_with_qr_code(self):
        """Test handling initial message with QR code format"""
        webhook_view = WhatsAppWebhookView()
        result = webhook_view.handle_initial_message("+1987654321", f"start-{self.hotel.id}")
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('Welcome!', result['message'])
        self.assertIn(str(self.hotel.id), result['message'])

    def test_handle_initial_message_with_invalid_hotel_id(self):
        """Test handling initial message with invalid hotel ID"""
        webhook_view = WhatsAppWebhookView()
        result = webhook_view.handle_initial_message("+1987654321", "start-invalid-id")
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('Invalid hotel ID format', result['message'])

    def test_handle_initial_message_with_demo_command(self):
        """Test handling initial message with demo command"""
        webhook_view = WhatsAppWebhookView()
        result = webhook_view.handle_initial_message("+1987654321", "demo")
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('Welcome to the demo!', result['message'])

    def test_handle_initial_message_with_unknown_command(self):
        """Test handling initial message with unknown command"""
        webhook_view = WhatsAppWebhookView()
        result = webhook_view.handle_initial_message("+1987654321", "unknown")
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('Thank you for your message', result['message'])

    def test_send_whatsapp_message(self):
        """Test sending WhatsApp message"""
        webhook_view = WhatsAppWebhookView()
        result = webhook_view.send_whatsapp_message("+1987654321", "Test message")
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('message_id', result)