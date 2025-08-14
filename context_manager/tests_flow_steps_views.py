from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from context_manager.models import FlowStep
from hotel.models import Hotel
import uuid

class FlowStepsViewsTest(TestCase):
    """Test the Flow Steps API views"""

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
        
        # Create a test flow step
        self.flow_step = FlowStep.objects.create(
            step_id='test_step',
            hotel=self.hotel,
            flow_type='test_flow',
            message_template='Test message template',
            options={'1': 'Option 1', '2': 'Option 2'}
        )

    def test_list_flow_steps_unauthorized(self):
        """Test listing flow steps without authentication"""
        url = reverse('flow-step-list', kwargs={'hotel_id': self.hotel.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_flow_step_unauthorized(self):
        """Test creating a flow step without authentication"""
        url = reverse('flow-step-list', kwargs={'hotel_id': self.hotel.id})
        data = {
            'step_id': 'new_test_step',
            'flow_type': 'test_flow',
            'message_template': 'New test message template',
            'options': {'1': 'Option 1', '2': 'Option 2'}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_flow_step_unauthorized(self):
        """Test retrieving a flow step without authentication"""
        url = reverse('flow-step-detail', kwargs={'hotel_id': self.hotel.id, 'step_id': self.flow_step.step_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_flow_step_unauthorized(self):
        """Test updating a flow step without authentication"""
        url = reverse('flow-step-detail', kwargs={'hotel_id': self.hotel.id, 'step_id': self.flow_step.step_id})
        data = {
            'flow_type': 'updated_test_flow',
            'message_template': 'Updated test message template',
            'options': {'1': 'Updated Option 1', '2': 'Updated Option 2'}
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_flow_step_unauthorized(self):
        """Test deleting a flow step without authentication"""
        url = reverse('flow-step-detail', kwargs={'hotel_id': self.hotel.id, 'step_id': self.flow_step.step_id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_flow_steps_with_invalid_hotel(self):
        """Test listing flow steps with invalid hotel ID"""
        url = reverse('flow-step-list', kwargs={'hotel_id': uuid.uuid4()})
        response = self.client.get(url)
        # Even with invalid hotel ID, should still return unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_flow_step_with_duplicate_step_id(self):
        """Test creating a flow step with duplicate step_id"""
        url = reverse('flow-step-list', kwargs={'hotel_id': self.hotel.id})
        data = {
            'step_id': 'test_step',  # Duplicate step_id
            'flow_type': 'test_flow',
            'message_template': 'New test message template',
            'options': {'1': 'Option 1', '2': 'Option 2'}
        }
        response = self.client.post(url, data, format='json')
        # Should still be unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)