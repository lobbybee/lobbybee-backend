from django.test import TestCase
from context_manager.models import FlowStep, ConversationContext
from context_manager.services import (
    process_incoming_message, 
    get_active_context, 
    validate_input, 
    transition_step,
    generate_response,
    replace_placeholders,
    handle_navigation,
    update_accumulated_data
)
from hotel.models import Hotel, Room, RoomCategory
from guest.models import Guest, Stay
from datetime import datetime, timedelta
import uuid

class ContextManagerServicesTest(TestCase):
    """Test the Context Manager services"""

    def setUp(self):
        """Set up test data"""
        # Create a hotel
        self.hotel = Hotel.objects.create(
            id=uuid.uuid4(),
            name="Test Hotel",
            email="test@hotel.com",
            phone="+1234567890",
            wifi_password="testwifi123"
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
        
        # Create FlowStep records for testing
        self.start_step = FlowStep.objects.create(
            step_id='test_start',
            flow_type='test_flow',
            message_template="Welcome {guest_name} to {hotel_name}! Your room is {room_number}.",
            options={'1': 'Continue', '2': 'Cancel'}
        )
        
        self.next_step = FlowStep.objects.create(
            step_id='test_next',
            flow_type='test_flow',
            message_template="Please provide your feedback about room {room_number}.",
            options={}
        )
        
        # Link steps
        self.start_step.next_step = self.next_step
        self.start_step.save()

    def test_get_active_context_with_active_context(self):
        """Test retrieving an active context"""
        # Create an active context
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'test_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {},
                'navigation_stack': ['test_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        # Test retrieving the context
        retrieved_context = get_active_context(self.guest.whatsapp_number)
        self.assertIsNotNone(retrieved_context)
        self.assertEqual(retrieved_context.id, context.id)
        self.assertTrue(retrieved_context.is_active)

    def test_get_active_context_with_no_context(self):
        """Test retrieving context when none exists"""
        # Test with non-existent WhatsApp number
        retrieved_context = get_active_context("+1111111111")
        self.assertIsNone(retrieved_context)

    def test_validate_input_with_valid_option(self):
        """Test validating valid input against step options"""
        result = validate_input(None, '1', self.start_step)
        self.assertTrue(result['valid'])

    def test_validate_input_with_invalid_option(self):
        """Test validating invalid input against step options"""
        result = validate_input(None, '3', self.start_step)
        self.assertFalse(result['valid'])
        self.assertIn("Please select a valid option", result['message'])

    def test_validate_input_with_navigation_commands(self):
        """Test validating navigation commands"""
        result = validate_input(None, 'back', self.start_step)
        self.assertTrue(result['valid'])
        
        result = validate_input(None, 'main menu', self.start_step)
        self.assertTrue(result['valid'])

    def test_validate_input_without_options(self):
        """Test validating input for steps without options"""
        result = validate_input(None, 'any input', self.next_step)
        self.assertTrue(result['valid'])

    def test_transition_step_with_next_step(self):
        """Test transitioning to next step"""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'test_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {},
                'navigation_stack': ['test_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        next_step = transition_step(context, '1', self.start_step)
        self.assertIsNotNone(next_step)
        self.assertEqual(next_step.step_id, 'test_next')

    def test_transition_step_with_no_next_step(self):
        """Test transitioning when no next step exists"""
        # Create a step with no next step
        terminal_step = FlowStep.objects.create(
            step_id='terminal_step',
            flow_type='test_flow',
            message_template="This is the end of the flow.",
            options={}
        )
        
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'terminal_step',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {},
                'navigation_stack': ['terminal_step'],
                'error_count': 0,
            },
            is_active=True
        )
        
        next_step = transition_step(context, 'any input', terminal_step)
        self.assertIsNone(next_step)

    def test_generate_response_with_options(self):
        """Test generating response with options"""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'test_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {},
                'navigation_stack': ['test_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        response = generate_response(context, self.start_step)
        self.assertIn("Welcome John Doe to Test Hotel!", response)
        self.assertIn("Your room is 101", response)
        self.assertIn("1. Continue", response)
        self.assertIn("2. Cancel", response)

    def test_generate_response_without_options(self):
        """Test generating response without options"""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'test_next',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {},
                'navigation_stack': ['test_start', 'test_next'],
                'error_count': 0,
            },
            is_active=True
        )
        
        response = generate_response(context, self.next_step)
        self.assertIn("Please provide your feedback about room 101", response)
        # Should not contain numbered options (like "1. Continue")
        self.assertNotIn("1. Continue", response)

    def test_replace_placeholders(self):
        """Test replacing placeholders in templates"""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'test_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {
                    'custom_field': 'custom_value'
                },
                'navigation_stack': ['test_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        template = "Hello {guest_name}, welcome to {hotel_name}. Your room is {room_number} and WiFi password is {wifi_password}. Custom: {custom_field}"
        result = replace_placeholders(template, context)
        
        self.assertIn("Hello John Doe", result)
        self.assertIn("welcome to Test Hotel", result)
        self.assertIn("Your room is 101", result)
        self.assertIn("WiFi password is testwifi123", result)
        self.assertIn("Custom: custom_value", result)

    def test_handle_navigation_back(self):
        """Test handling back navigation"""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'test_next',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {'test_data': 'test_value'},
                'navigation_stack': ['test_start', 'test_next'],
                'error_count': 2,
            },
            is_active=True
        )
        
        result = handle_navigation(context, 'back')
        self.assertEqual(result['status'], 'success')
        
        # Refresh context from database
        context.refresh_from_db()
        self.assertEqual(context.context_data['current_step'], 'test_start')
        self.assertEqual(len(context.context_data['navigation_stack']), 1)
        self.assertEqual(context.context_data['error_count'], 0)  # Error count should be reset

    def test_handle_navigation_main_menu(self):
        """Test handling main menu navigation"""
        # Create the checkin_start step that handle_navigation expects
        main_menu_step = FlowStep.objects.create(
            step_id='checkin_start',
            hotel=self.hotel,
            flow_type='guest_checkin',
            message_template="Main menu: Welcome back!",
            options={}
        )
        
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'test_next',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {'test_data': 'test_value'},
                'navigation_stack': ['test_start', 'test_next'],
                'error_count': 2,
            },
            is_active=True
        )
        
        result = handle_navigation(context, 'main menu')
        self.assertEqual(result['status'], 'success')
        
        # Refresh context from database
        context.refresh_from_db()
        self.assertEqual(context.context_data['current_step'], 'checkin_start')  # Default main menu step
        self.assertEqual(context.context_data['accumulated_data'], {})  # Data should be cleared
        self.assertEqual(context.context_data['error_count'], 0)  # Error count should be reset

    def test_update_accumulated_data(self):
        """Test updating accumulated data"""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'test_flow',
                'current_step': 'test_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {},
                'navigation_stack': ['test_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        # Create a step for testing data accumulation
        collect_dob_step = FlowStep.objects.create(
            step_id='checkin_collect_dob',
            flow_type='guest_checkin',
            message_template="Please provide your date of birth.",
            options={}
        )
        
        context.context_data['current_step'] = 'checkin_collect_dob'
        context.save()
        
        update_accumulated_data(context, '15-06-1990', collect_dob_step)
        
        # Refresh context from database
        context.refresh_from_db()
        self.assertEqual(context.context_data['accumulated_data']['date_of_birth'], '15-06-1990')