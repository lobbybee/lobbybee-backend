from django.test import TestCase
from context_manager.models import FlowStep, ConversationContext
from context_manager.services import process_incoming_message
from hotel.models import Hotel, Room, RoomCategory
from guest.models import Guest, Stay
from datetime import datetime, timedelta
import uuid

class ContextManagerIntegrationTest(TestCase):
    """Integration tests for the Context Manager"""

    def setUp(self):
        """Set up test data for integration tests"""
        # Create a hotel
        self.hotel = Hotel.objects.create(
            id=uuid.uuid4(),
            name="Grand Hotel",
            email="info@grandhotel.com",
            phone="+1234567890",
            wifi_password="grandwifi123"
        )
        
        # Create a room category
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Deluxe Room",
            description="A luxurious deluxe room",
            base_price=200.00,
            max_occupancy=2
        )
        
        # Create a room
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="305",
            category=self.room_category,
            floor=3,
            status="available"
        )
        
        # Create a guest
        self.guest = Guest.objects.create(
            full_name="Jane Smith",
            email="jane.smith@example.com",
            whatsapp_number="+1555123456",
            nationality="British"
        )
        
        # Create a stay
        self.stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            status="active",
            check_in_date=datetime.now(),
            check_out_date=datetime.now() + timedelta(days=2),
            number_of_guests=1
        )
        
        # Create FlowStep records for a complete check-in flow
        self.checkin_start = FlowStep.objects.create(
            step_id='checkin_start',
            flow_type='guest_checkin',
            message_template="Welcome to {hotel_name}, {guest_name}! Please confirm your name: {guest_name}. (1. Yes, 2. No)",
            options={'1': 'Yes', '2': 'No'}
        )
        
        self.collect_dob = FlowStep.objects.create(
            step_id='checkin_collect_dob',
            flow_type='guest_checkin',
            message_template="Please provide your date of birth (DD-MM-YYYY).",
            options={}
        )
        
        self.final_confirmation = FlowStep.objects.create(
            step_id='checkin_final_confirmation',
            flow_type='guest_checkin',
            message_template="Thank you! Your check-in is complete. Your room is {room_number}. WiFi: {wifi_password}",
            options={}
        )
        
        # Set up step relationships
        self.checkin_start.next_step = self.collect_dob
        self.checkin_start.save()
        
        self.collect_dob.previous_step = self.checkin_start
        self.collect_dob.next_step = self.final_confirmation
        self.collect_dob.save()
        
        self.final_confirmation.previous_step = self.collect_dob
        self.final_confirmation.save()

    def test_complete_checkin_flow(self):
        """Test a complete check-in flow from start to finish"""
        # Create initial context
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'guest_checkin',
                'current_step': 'checkin_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {},
                'navigation_stack': ['checkin_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        # Step 1: Guest confirms name
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '1'  # Yes
        }
        
        result = process_incoming_message(payload)
        self.assertEqual(result['status'], 'success')
        self.assertIn('Please provide your date of birth', result['message'])
        
        # Refresh context
        context.refresh_from_db()
        self.assertEqual(context.context_data['current_step'], 'checkin_collect_dob')
        self.assertTrue(context.context_data['accumulated_data']['name_confirmed'])
        
        # Step 2: Guest provides date of birth
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '15-06-1990'
        }
        
        result = process_incoming_message(payload)
        self.assertEqual(result['status'], 'success')
        self.assertIn('Thank you! Your check-in is complete', result['message'])
        self.assertIn('Your room is 305', result['message'])
        self.assertIn('WiFi: grandwifi123', result['message'])
        
        # Refresh context
        context.refresh_from_db()
        self.assertEqual(context.context_data['current_step'], 'checkin_final_confirmation')
        self.assertEqual(context.context_data['accumulated_data']['date_of_birth'], '15-06-1990')
        
        # Step 3: Final step - conversation should end
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': 'thanks'
        }
        
        result = process_incoming_message(payload)
        self.assertEqual(result['status'], 'success')
        self.assertIn('Conversation completed successfully', result['message'])
        
        # Refresh context and verify it's no longer active
        context.refresh_from_db()
        self.assertFalse(context.is_active)

    def test_navigation_commands(self):
        """Test navigation commands during a flow"""
        # Create context
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'guest_checkin',
                'current_step': 'checkin_collect_dob',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {'name_confirmed': True},
                'navigation_stack': ['checkin_start', 'checkin_collect_dob'],
                'error_count': 0,
            },
            is_active=True
        )
        
        # Test back command
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': 'back'
        }
        
        result = process_incoming_message(payload)
        self.assertEqual(result['status'], 'success')
        self.assertIn('Welcome to Grand Hotel', result['message'])
        self.assertIn('Please confirm your name', result['message'])
        
        # Refresh context
        context.refresh_from_db()
        self.assertEqual(context.context_data['current_step'], 'checkin_start')
        self.assertEqual(len(context.context_data['navigation_stack']), 1)

    def test_error_handling_and_cooloff(self):
        """Test error handling and cooloff mechanism"""
        # Create context
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'guest_checkin',
                'current_step': 'checkin_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {},
                'navigation_stack': ['checkin_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        # Send invalid input 4 times
        for i in range(4):
            payload = {
                'from_no': self.guest.whatsapp_number,
                'message': '3'  # Invalid option
            }
            
            result = process_incoming_message(payload)
            self.assertEqual(result['status'], 'success')
            self.assertIn('Please select a valid option', result['message'])
            
            # Refresh context
            context.refresh_from_db()
            self.assertEqual(context.context_data['error_count'], i + 1)
        
        # On the 5th try, we should get the cooloff message
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '3'  # Invalid option
        }
        
        result = process_incoming_message(payload)
        self.assertEqual(result['status'], 'error')
        self.assertIn('Too many consecutive errors', result['message'])
        
        # Refresh context and verify it's no longer active
        context.refresh_from_db()
        self.assertFalse(context.is_active)

    def test_placeholder_replacement(self):
        """Test placeholder replacement in messages"""
        # Create context
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'guest_checkin',
                'current_step': 'test_placeholders',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {
                    'custom_field': 'custom_value'
                },
                'navigation_stack': ['test_placeholders'],
                'error_count': 0,
            },
            is_active=True
        )
        
        # Test message with multiple placeholders
        test_step = FlowStep.objects.create(
            step_id='test_placeholders',
            hotel=self.hotel,
            flow_type='test_flow',
            message_template="Hello {guest_name}, welcome to {hotel_name}. Your room is {room_number}, WiFi: {wifi_password}. Custom: {custom_field}",
            options={}
        )
        
        # Directly test the generate_response function
        from context_manager.services import generate_response
        response = generate_response(context, test_step)
        
        self.assertIn('Hello Jane Smith', response)
        self.assertIn('welcome to Grand Hotel', response)
        self.assertIn('Your room is 305', response)
        self.assertIn('WiFi: grandwifi123', response)
        self.assertIn('Custom: custom_value', response)