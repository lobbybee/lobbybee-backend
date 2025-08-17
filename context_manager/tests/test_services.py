from django.test import TestCase
from context_manager.models import (
    FlowTemplate, FlowStepTemplate, FlowAction, HotelFlowConfiguration,
    ConversationContext
)
from context_manager.services import (
    get_hotel_flow_step, generate_response, transition_step,
    validate_input, handle_navigation, update_accumulated_data,
    replace_placeholders
)
from hotel.models import Hotel
from guest.models import Guest
from datetime import timedelta
from django.utils import timezone
import json


class ContextManagerServicesTestCase(TestCase):
    def setUp(self):
        # Create a test hotel
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            email="test@hotel.com",
            phone="+1234567890",
            wifi_password="hotelwifi123"
        )
        
        # Create a test guest
        self.guest = Guest.objects.create(
            full_name="Test Guest",
            email="test@guest.com",
            whatsapp_number="+1234567891",
            nationality="US"
        )
        
        # Create a flow template for testing
        self.flow_template = FlowTemplate.objects.create(
            name="Test Flow",
            description="A test flow for service testing",
            category="guest_checkin",
            is_active=True
        )
        
        # Create flow step templates
        self.step_template1 = FlowStepTemplate.objects.create(
            flow_template=self.flow_template,
            step_name="Start Step",
            message_template="Welcome to {hotel_name}! Please confirm your name: {guest_name} (1. Yes, 2. No)",
            message_type="TEXT",
            options={"1": "Yes", "2": "No"}
        )
        
        self.step_template2 = FlowStepTemplate.objects.create(
            flow_template=self.flow_template,
            step_name="Collect DOB",
            message_template="Please provide your date of birth (DD-MM-YYYY).",
            message_type="TEXT",
            options={}
        )
        
        self.step_template3 = FlowStepTemplate.objects.create(
            flow_template=self.flow_template,
            step_name="Confirmation",
            message_template="Thank you! Your DOB is {date_of_birth}. Is this correct? (1. Yes, 2. No)",
            message_type="TEXT",
            options={"1": "Yes", "2": "No"}
        )
        
        # Link steps
        self.step_template1.next_step_template = self.step_template2
        self.step_template2.next_step_template = self.step_template3
        self.step_template1.save()
        self.step_template2.save()
        
        # Create hotel flow configuration with customizations
        self.hotel_config = HotelFlowConfiguration.objects.create(
            hotel=self.hotel,
            flow_template=self.flow_template,
            is_enabled=True,
            customization_data={
                'step_customizations': {
                    str(self.step_template1.id): {
                        'message_template': 'Welcome to {hotel_name}! Dear {guest_name}, confirm your name? (1. Yes, 2. No)',
                        'options': {"1": "Confirm", "2": "Re-enter"}
                    }
                }
            }
        )
        
        # Create a conversation context for testing
        self.context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'navigation_stack': [self.step_template1.id],
                'accumulated_data': {'date_of_birth': '01-01-1990'},
                'error_count': 0,
                'current_step_template': self.step_template1.id
            },
            is_active=True,
            navigation_stack=[self.step_template1.id],
            flow_expires_at=timezone.now() + timedelta(hours=5)
        )

    def test_get_hotel_flow_step_without_customization(self):
        """Test getting hotel-specific flow step without customizations"""
        step_data = get_hotel_flow_step(self.hotel, self.step_template2)
        
        # Should return base template message
        self.assertEqual(
            step_data['message_template'],
            'Please provide your date of birth (DD-MM-YYYY).'
        )
        
        # Should return base template options
        self.assertEqual(step_data['options'], {})

    def test_generate_response_with_placeholders(self):
        """Test generating response with placeholder replacements"""
        response = generate_response(self.context, self.step_template1)
        
        # Should replace placeholders with actual data
        self.assertIn('Welcome to Test Hotel!', response)
        self.assertIn('Test Guest', response)
        self.assertIn('1. Yes', response)
        self.assertIn('2. No', response)

    def test_replace_placeholders(self):
        """Test replacing placeholders in templates"""
        template = "Welcome {guest_name} to {hotel_name}. Your WiFi is {wifi_password}."
        result = replace_placeholders(template, self.context)
        
        self.assertIn('Test Guest', result)
        self.assertIn('Test Hotel', result)
        self.assertIn('hotelwifi123', result)

    def test_validate_input_with_options(self):
        """Test validating user input against step options"""
        # Test with valid option
        result = validate_input(
            self.context, '1', self.step_template1,
            get_hotel_flow_step(self.hotel, self.step_template1)
        )
        self.assertTrue(result['valid'])
        
        # Test with invalid option
        result = validate_input(
            self.context, '3', self.step_template1,
            get_hotel_flow_step(self.hotel, self.step_template1)
        )
        self.assertFalse(result['valid'])

    def test_validate_input_without_options(self):
        """Test validating user input for steps without options"""
        result = validate_input(
            self.context, 'any input', self.step_template2,
            get_hotel_flow_step(self.hotel, self.step_template2)
        )
        self.assertTrue(result['valid'])