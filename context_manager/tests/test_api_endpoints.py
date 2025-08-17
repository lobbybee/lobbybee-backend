from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from user.models import User
from context_manager.models import (
    FlowTemplate, FlowStepTemplate, FlowAction, HotelFlowConfiguration,
    FlowStep, ScheduledMessageTemplate
)
from hotel.models import Hotel
import json
import uuid


class ContextManagerAPITestCase(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='superadmin'
        )
        
        # Create a test hotel
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            email="test@hotel.com",
            phone="+1234567890"
        )
        
        # Create API client and authenticate
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_flow_template_list(self):
        """Test admin API for listing flow templates"""
        # Test listing
        response = self.client.get(reverse('flow-template-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_flow_template_retrieve(self):
        """Test admin API for retrieving flow templates"""
        # Create a flow template for testing
        flow_template = FlowTemplate.objects.create(
            name="Test Flow",
            description="A test flow for API testing",
            category="guest_checkin",
            is_active=True
        )
        
        # Test retrieve
        response = self.client.get(
            reverse('flow-template-detail', kwargs={'id': flow_template.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], flow_template.name)

    def test_flow_step_template_list(self):
        """Test admin API for listing flow step templates"""
        # Test listing
        response = self.client.get(reverse('flow-step-template-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_hotel_flow_steps_list(self):
        """Test hotel API for listing flow steps"""
        # Test listing
        response = self.client.get(
            reverse('flow-step-list', kwargs={'hotel_id': self.hotel.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_scheduled_message_template_list(self):
        """Test hotel API for listing scheduled message templates"""
        # Test listing
        response = self.client.get(
            reverse('message-template-list', kwargs={'hotel_id': self.hotel.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)