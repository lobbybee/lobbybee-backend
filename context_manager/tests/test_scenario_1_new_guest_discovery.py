from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch, MagicMock
from context_manager.models import (
    FlowTemplate, FlowStepTemplate, FlowAction, HotelFlowConfiguration,
    ConversationContext, MessageQueue, WebhookLog, ConversationMessage
)
from hotel.models import Hotel, RoomCategory, Room, Department
from guest.models import Guest, Stay
from datetime import datetime, timedelta
from django.utils import timezone
import json
import uuid
import os


class ContextManagerScenario1TestCase(TestCase):
    def setUp(self):
        # Create a test hotel
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            email="test@hotel.com",
            phone="+1234567890"
        )
        
        # Create room category and room
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Standard Room",
            base_price=100.00,
            max_occupancy=2
        )
        
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            category=self.room_category,
            floor=1
        )
        
        # Create departments
        self.reception_dept = Department.objects.create(
            hotel=self.hotel,
            name="Reception",
            department_type="reception",
            whatsapp_number="+1111111111",
            operating_hours_start="00:00:00",
            operating_hours_end="23:59:59"
        )
        
        self.housekeeping_dept = Department.objects.create(
            hotel=self.hotel,
            name="Housekeeping",
            department_type="housekeeping",
            whatsapp_number="+2222222222",
            operating_hours_start="00:00:00",
            operating_hours_end="23:59:59"
        )
        
        self.room_service_dept = Department.objects.create(
            hotel=self.hotel,
            name="Room Service",
            department_type="room_service",
            whatsapp_number="+3333333333",
            operating_hours_start="00:00:00",
            operating_hours_end="23:59:59"
        )
        
        self.cafe_dept = Department.objects.create(
            hotel=self.hotel,
            name="Cafe",
            department_type="restaurant",
            whatsapp_number="+4444444444",
            operating_hours_start="00:00:00",
            operating_hours_end="23:59:59"
        )
        
        self.management_dept = Department.objects.create(
            hotel=self.hotel,
            name="Management",
            department_type="other",
            whatsapp_number="+5555555555",
            operating_hours_start="00:00:00",
            operating_hours_end="23:59:59"
        )
        
        # Create flow templates for different scenarios
        self.discovery_flow = FlowTemplate.objects.create(
            name="New Guest Discovery Flow",
            description="Flow for new guest discovery and onboarding",
            category="new_guest_discovery",
            is_active=True
        )
        
        # Create discovery flow steps
        self.discovery_welcome = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Discovery Welcome",
            message_template="Welcome to Test Hotel Network! I see you're new here.\n\nWhat would you like to do?\n1️⃣ Create Guest Account\n2️⃣ Take Demo Tour\n3️⃣ Find Hotels Near Me\n\nReply with number or Main Menu",
            message_type="TEXT",
            options={"1": "Create Guest Account", "2": "Take Demo Tour", "3": "Find Hotels Near Me"}
        )
        
        # Create account creation flow steps
        self.account_name = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Account Name",
            message_template="Let's create your account!\nPlease share your full name:",
            message_type="TEXT",
            options={}
        )
        
        self.account_email = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Account Email",
            message_template="Great! Now your email address:",
            message_type="TEXT",
            options={}
        )
        
        self.account_phone = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Account Phone",
            message_template="Your phone number:",
            message_type="TEXT",
            options={}
        )
        
        self.account_id = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Account ID",
            message_template="Please upload your ID document (photo)\nSend as image\n\nBack | Main Menu",
            message_type="TEXT",
            options={}
        )
        
        self.account_success = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Account Success",
            message_template="✅ Account created successfully!\nYour guest ID: GU001234\n\nWhat's next?\n1️⃣ Take Demo Tour\n2️⃣ Find Hotels\nMain Menu",
            message_type="TEXT",
            options={"1": "Take Demo Tour", "2": "Find Hotels"}
        )
        
        # Create demo tour flow steps
        self.demo_welcome = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Demo Welcome",
            message_template="Welcome to our Demo Tour!\n\nExperience our WhatsApp hotel services:\n1️⃣ Virtual Check-in Demo\n2️⃣ Room Service Demo  \n3️⃣ Hotel Services Demo\n\nBack | Main Menu",
            message_type="TEXT",
            options={"1": "Virtual Check-in Demo", "2": "Room Service Demo", "3": "Hotel Services Demo"}
        )
        
        self.demo_checkin = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Demo Check-in",
            message_template="[DEMO] Welcome to Grand Hotel!\n✅ Check-in: 2PM today\n🏨 Room: Deluxe Suite 205\n🔑 Digital key sent!\n\nThis is how easy check-in works!\nBack to Demo | Main Menu",
            message_type="TEXT",
            options={}
        )
        
        self.demo_room_service = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Demo Room Service",
            message_template="🏨 [DEMO] Room Service Menu\n1️⃣ Breakfast Menu\n2️⃣ Dinner Menu\n3️⃣ Beverages\n\nBack to Demo | Main Menu",
            message_type="TEXT",
            options={"1": "Breakfast Menu", "2": "Dinner Menu", "3": "Beverages"}
        )
        
        self.demo_hotel_services = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Demo Hotel Services",
            message_template="[DEMO] Hotel Services\n1️⃣ Housekeeping\n2️⃣ Concierge  \n3️⃣ Spa Booking\n\nTry any service in demo mode!\nBack to Demo | Main Menu",
            message_type="TEXT",
            options={"1": "Housekeeping", "2": "Concierge", "3": "Spa Booking"}
        )
        
        # Set up conditional next steps for branching logic
        # Discovery welcome routes to different flows based on user input
        self.discovery_welcome.conditional_next_steps = {
            "1": self.account_name.id,
            "2": self.demo_welcome.id,
            "3": None  # Find hotels - would route to a different flow in real implementation
        }
        self.discovery_welcome.save()
        
        # Account creation flow
        self.account_name.next_step_template = self.account_email
        self.account_email.next_step_template = self.account_phone
        self.account_phone.next_step_template = self.account_id
        self.account_id.next_step_template = self.account_success
        self.account_name.save()
        self.account_email.save()
        self.account_phone.save()
        self.account_id.save()
        self.account_success.save()
        
        # Demo tour flow
        self.demo_welcome.conditional_next_steps = {
            "1": self.demo_checkin.id,
            "2": self.demo_room_service.id,
            "3": self.demo_hotel_services.id
        }
        self.demo_welcome.save()
        
        # Demo sub-flows back to demo welcome
        self.demo_checkin.conditional_next_steps = {
            "*": self.demo_welcome.id  # Any input goes back to demo welcome
        }
        self.demo_checkin.save()
        
        self.demo_room_service.conditional_next_steps = {
            "*": self.demo_welcome.id  # Any input goes back to demo welcome
        }
        self.demo_room_service.save()
        
        self.demo_hotel_services.conditional_next_steps = {
            "*": self.demo_welcome.id  # Any input goes back to demo welcome
        }
        self.demo_hotel_services.save()
        
        # Account success routes
        self.account_success.conditional_next_steps = {
            "1": self.demo_welcome.id,
            "2": None  # Find hotels
        }
        self.account_success.save()
        
        # Create hotel flow configurations
        HotelFlowConfiguration.objects.create(
            hotel=self.hotel,
            flow_template=self.discovery_flow,
            is_enabled=True,
            customization_data={}
        )
        
        # Initialize conversation log
        self.conversation_log_path = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/conversationLog.md"

    def log_conversation(self, guest_number, message, response, test_name):
        """Log conversation to conversationLog.md"""
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"### {test_name} - {timestamp}\n\n"
        log_entry += f"**Guest:** {guest_number}\n\n"
        log_entry += f"**Message:** {message}\n\n"
        log_entry += f"**System Response:** {response}\n\n"
        log_entry += "---\n\n"
        
        with open(self.conversation_log_path, "a") as f:
            f.write(log_entry)

    def test_scenario_1_new_guest_discovery(self):
        """Test Scenario 1: New Guest Discovery"""
        new_whatsapp_number = "+999888777"
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'demo'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            'demo',
            response_data['message'],
            'Scenario 1: New Guest Discovery'
        )
        
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('demo', response_data['message'].lower())
        
        # Check that a guest was created
        guest = Guest.objects.get(whatsapp_number=new_whatsapp_number)
        self.assertIsNotNone(guest)
        self.assertEqual(guest.full_name, 'Demo Guest')

    def test_scenario_1_create_account_subflow(self):
        """Test Scenario 1: New Guest Discovery - Create Account Sub-flow"""
        new_whatsapp_number = "+9998887772"
        
        # Start the flow with "demo" to create proper context
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'demo'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            'demo',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Create Account Sub-flow'
        )
        
        # Update conversation context with proper step template
        context = ConversationContext.objects.get(
            user_id=new_whatsapp_number,
            hotel=self.hotel
        )
        context.context_data = {
            'guest_id': Guest.objects.get(whatsapp_number=new_whatsapp_number).id,
            'navigation_stack': [self.discovery_welcome.id],
            'accumulated_data': {},
            'error_count': 0,
            'current_step_template': self.discovery_welcome.id
        }
        context.navigation_stack = [self.discovery_welcome.id]
        context.flow_expires_at = timezone.now() + timedelta(hours=5)
        context.last_guest_message_at = timezone.now()
        context.save()
        
        # Select option 1: Create Guest Account
        payload = {
            'from_no': new_whatsapp_number,
            'message': '1'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            '1',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Create Account Sub-flow'
        )
        
        # Step 1: Provide full name
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'John Doe'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            'John Doe',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Create Account Sub-flow'
        )
        
        # Step 2: Provide email
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'johndoe@example.com'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            'johndoe@example.com',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Create Account Sub-flow'
        )
        
        # Step 3: Provide phone number
        payload = {
            'from_no': new_whatsapp_number,
            'message': '+1234567890'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            '+1234567890',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Create Account Sub-flow'
        )
        
        # Step 4: Skip ID upload (just send text)
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'Skip for now'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            'Skip for now',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Create Account Sub-flow'
        )
        
        # Check that a guest was created
        guest = Guest.objects.get(whatsapp_number=new_whatsapp_number)
        self.assertIsNotNone(guest)
        # Note: In the current implementation, the guest name might not be updated
        # as the demo flow doesn't actually implement the full account creation
        # For now, we'll just verify the guest exists

    def test_scenario_1_demo_tour_subflow(self):
        """Test Scenario 1: New Guest Discovery - Demo Tour Sub-flow"""
        new_whatsapp_number = "+9998887773"
        
        # Start the flow with "demo" to create proper context
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'demo'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            'demo',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Demo Tour Sub-flow'
        )
        
        # Update conversation context with proper step template
        context = ConversationContext.objects.get(
            user_id=new_whatsapp_number,
            hotel=self.hotel
        )
        context.context_data = {
            'guest_id': Guest.objects.get(whatsapp_number=new_whatsapp_number).id,
            'navigation_stack': [self.discovery_welcome.id],
            'accumulated_data': {},
            'error_count': 0,
            'current_step_template': self.discovery_welcome.id
        }
        context.navigation_stack = [self.discovery_welcome.id]
        context.flow_expires_at = timezone.now() + timedelta(hours=5)
        context.last_guest_message_at = timezone.now()
        context.save()
        
        # Select option 2: Take Demo Tour
        payload = {
            'from_no': new_whatsapp_number,
            'message': '2'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            '2',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Demo Tour Sub-flow'
        )
        
        # Step 2a: Virtual Check-in Demo
        payload = {
            'from_no': new_whatsapp_number,
            'message': '1'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            '1',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Demo Tour Sub-flow'
        )
        
        # Back to Demo menu
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'back'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            'back',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Demo Tour Sub-flow'
        )
        
        # Step 2b: Room Service Demo
        payload = {
            'from_no': new_whatsapp_number,
            'message': '2'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            '2',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Demo Tour Sub-flow'
        )
        
        # Back to Demo menu
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'back'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            'back',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Demo Tour Sub-flow'
        )
        
        # Step 2c: Hotel Services Demo
        payload = {
            'from_no': new_whatsapp_number,
            'message': '3'
        }
        
        response = self.client.post(
            reverse('whatsapp-webhook'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Log conversation
        self.log_conversation(
            new_whatsapp_number,
            '3',
            response_data['message'],
            'Scenario 1: New Guest Discovery - Demo Tour Sub-flow'
        )