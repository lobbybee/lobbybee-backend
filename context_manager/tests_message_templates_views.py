from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from context_manager.models import ScheduledMessageTemplate
from hotel.models import Hotel
import uuid

class MessageTemplatesViewsTest(TestCase):
    """Test the Scheduled Message Templates API views"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create a hotel for testing
        self.hotel = Hotel.objects.create(
            id=uuid.uuid4(),
            name="Test Hotel",
            email="test@hotel.com",
            phone="+1234567890"
        )
        
        # Create a test user and authenticate
        # Note: In a real implementation, you would authenticate the user
        # For now, we'll test unauthorized access
        
        # Create a test message template
        self.message_template = ScheduledMessageTemplate.objects.create(
            hotel=self.hotel,
            message_type='test_message',
            trigger_condition={'test': 'condition'},
            message_template='Test message template'
        )

    def test_list_message_templates_unauthorized(self):
        """Test listing message templates without authentication"""
        url = reverse('message-template-list', kwargs={'hotel_id': self.hotel.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_message_template_unauthorized(self):
        """Test creating a message template without authentication"""
        url = reverse('message-template-list', kwargs={'hotel_id': self.hotel.id})
        data = {
            'message_type': 'new_test_message',
            'trigger_condition': {'new': 'condition'},
            'message_template': 'New test message template'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_message_template_unauthorized(self):
        """Test retrieving a message template without authentication"""
        url = reverse('message-template-detail', kwargs={'hotel_id': self.hotel.id, 'template_id': self.message_template.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_message_template_unauthorized(self):
        """Test updating a message template without authentication"""
        url = reverse('message-template-detail', kwargs={'hotel_id': self.hotel.id, 'template_id': self.message_template.id})
        data = {
            'message_type': 'updated_test_message',
            'trigger_condition': {'updated': 'condition'},
            'message_template': 'Updated test message template'
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_message_template_unauthorized(self):
        """Test deleting a message template without authentication"""
        url = reverse('message-template-detail', kwargs={'hotel_id': self.hotel.id, 'template_id': self.message_template.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_message_templates_with_invalid_hotel(self):
        """Test listing message templates with invalid hotel ID"""
        url = reverse('message-template-list', kwargs={'hotel_id': uuid.uuid4()})
        response = self.client.get(url)
        # Even with invalid hotel ID, should still return unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_message_template_with_invalid_data(self):
        """Test creating a message template with invalid data"""
        url = reverse('message-template-list', kwargs={'hotel_id': self.hotel.id})
        data = {
            'message_type': '',  # Empty message type
            'trigger_condition': 'invalid_condition',  # Not a dict
            'message_template': 'New test message template'
        }
        response = self.client.post(url, data, format='json')
        # Should still be unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)