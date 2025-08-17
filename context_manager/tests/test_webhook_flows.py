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


class ContextManagerWebhookTestCase(TestCase):
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
        
        # Create a test guest
        self.guest = Guest.objects.create(
            full_name="Test Guest",
            email="test@guest.com",
            whatsapp_number="+1234567891",
            nationality="US"
        )
        
        # Create flow templates for different scenarios
        self.checkin_flow = FlowTemplate.objects.create(
            name="Guest Check-in Flow",
            description="Flow for guest check-in process",
            category="guest_checkin",
            is_active=True
        )
        
        self.main_menu_flow = FlowTemplate.objects.create(
            name="Main Menu Flow",
            description="Main menu for checked-in guests",
            category="main_menu",
            is_active=True
        )
        
        self.service_flow = FlowTemplate.objects.create(
            name="Service Request Flow",
            description="Flow for requesting hotel services",
            category="service_request",
            is_active=True
        )
        
        # Create check-in flow steps
        self.checkin_start = FlowStepTemplate.objects.create(
            flow_template=self.checkin_flow,
            step_name="Check-in Start",
            message_template="Welcome to {hotel_name}! Please provide your full name to begin check-in.",
            message_type="TEXT",
            options={}
        )
        
        self.checkin_confirm = FlowStepTemplate.objects.create(
            flow_template=self.checkin_flow,
            step_name="Confirm Guest Details",
            message_template="Thank you {guest_name}! Please confirm your details:\nEmail: {email}\nNationality: {nationality}\n1. Confirm\n2. Edit",
            message_type="TEXT",
            options={"1": "Confirm", "2": "Edit"}
        )
        
        self.checkin_complete = FlowStepTemplate.objects.create(
            flow_template=self.checkin_flow,
            step_name="Check-in Complete",
            message_template="Check-in complete! Your room is {room_number}. How can we assist you today?\n1. Reception\n2. Housekeeping\n3. Room Service\n4. Cafe\n5. Management",
            message_type="TEXT",
            options={
                "1": "Reception",
                "2": "Housekeeping", 
                "3": "Room Service",
                "4": "Cafe",
                "5": "Management"
            }
        )
        
        # Link check-in steps
        self.checkin_start.next_step_template = self.checkin_confirm
        self.checkin_confirm.next_step_template = self.checkin_complete
        self.checkin_start.save()
        self.checkin_confirm.save()
        
        # Create main menu flow steps
        self.main_menu = FlowStepTemplate.objects.create(
            flow_template=self.main_menu_flow,
            step_name="Main Menu",
            message_template="Main Menu:\n1. Reception\n2. Housekeeping\n3. Room Service\n4. Cafe\n5. Management\n6. My Stay Info",
            message_type="TEXT",
            options={
                "1": "Reception",
                "2": "Housekeeping", 
                "3": "Room Service",
                "4": "Cafe",
                "5": "Management",
                "6": "My Stay Info"
            }
        )
        
        # Create service flow steps
        self.service_menu = FlowStepTemplate.objects.create(
            flow_template=self.service_flow,
            step_name="Service Menu",
            message_template="Please select a service:\n1. Reception\n2. Housekeeping\n3. Room Service\n4. Cafe\n5. Management",
            message_type="TEXT",
            options={
                "1": "Reception",
                "2": "Housekeeping", 
                "3": "Room Service",
                "4": "Cafe",
                "5": "Management"
            }
        )
        
        self.room_service_menu = FlowStepTemplate.objects.create(
            flow_template=self.service_flow,
            step_name="Room Service Menu",
            message_template="Room Service Menu:\n1. Breakfast\n2. Lunch\n3. Dinner\n4. Snacks\n5. Beverages",
            message_type="TEXT",
            options={
                "1": "Breakfast",
                "2": "Lunch",
                "3": "Dinner",
                "4": "Snacks",
                "5": "Beverages"
            }
        )
        
        # Link service steps
        self.service_menu.next_step_template = self.room_service_menu
        self.service_menu.save()
        
        # Create hotel flow configurations
        HotelFlowConfiguration.objects.create(
            hotel=self.hotel,
            flow_template=self.checkin_flow,
            is_enabled=True,
            customization_data={}
        )
        
        HotelFlowConfiguration.objects.create(
            hotel=self.hotel,
            flow_template=self.main_menu_flow,
            is_enabled=True,
            customization_data={}
        )
        
        HotelFlowConfiguration.objects.create(
            hotel=self.hotel,
            flow_template=self.service_flow,
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

    def test_scenario_2_qr_code_checkin(self):
        """Test Scenario 2: QR Code Check-in"""
        whatsapp_number = "+111222333"
        payload = {
            'from_no': whatsapp_number,
            'message': f'start-{self.hotel.id}'
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
            whatsapp_number,
            f'start-{self.hotel.id}',
            response_data['message'],
            'Scenario 2: QR Code Check-in'
        )
        
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('welcome', response_data['message'].lower())
        
        # Check that a guest was created or retrieved
        guest = Guest.objects.get(whatsapp_number=whatsapp_number)
        self.assertIsNotNone(guest)
        
        # Check that a conversation context was created
        context = ConversationContext.objects.get(user_id=whatsapp_number)
        self.assertIsNotNone(context)
        self.assertTrue(context.is_active)
        self.assertEqual(context.hotel, self.hotel)

    def test_scenario_3_in_stay_service_access(self):
        """Test Scenario 3: In-Stay Service Access"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an active conversation context with proper step template
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.main_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Request room service
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '3'  # Room Service
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
            self.guest.whatsapp_number,
            '3',
            response_data.get('message', 'No response'),
            'Scenario 3: In-Stay Service Access'
        )

    def test_scenario_4_returning_guest_experience(self):
        """Test Scenario 4: Returning Guest Experience"""
        # Create a past stay for the guest
        past_stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=10),
            check_out_date=timezone.now() - timedelta(days=5),
            status='completed'
        )
        
        # Create a conversation context for the returning guest
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'navigation_stack': [self.main_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.main_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Send a random message from an existing guest
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': 'Hello, I was here last week'
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
            self.guest.whatsapp_number,
            'Hello, I was here last week',
            response_data.get('message', 'No response'),
            'Scenario 4: Returning Guest Experience'
        )

    def test_navigation_back_functionality(self):
        """Test Back navigation functionality"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an active conversation context with navigation stack
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id, self.service_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.service_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id, self.service_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Send "back" command
        payload = {
            'from_no': self.guest.whatsapp_number,
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
            self.guest.whatsapp_number,
            'back',
            response_data.get('message', 'No response'),
            'Navigation: Back Functionality'
        )

    def test_navigation_main_menu_functionality(self):
        """Test Main Menu navigation functionality"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an active conversation context with navigation stack
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id, self.service_menu.id],
                'accumulated_data': {'test': 'data'},
                'error_count': 0,
                'current_step_template': self.service_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id, self.service_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Send "main menu" command
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': 'main menu'
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
            self.guest.whatsapp_number,
            'main menu',
            response_data.get('message', 'No response'),
            'Navigation: Main Menu Functionality'
        )

    def test_session_flow_expiry(self):
        """Test session flow management with 5-hour expiry"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an expired conversation context
        expired_time = timezone.now() - timedelta(hours=6)
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.main_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id],
            flow_expires_at=expired_time,
            last_guest_message_at=timezone.now() - timedelta(hours=6)
        )
        
        # Send a message to trigger expiry
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': 'test message'
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
            self.guest.whatsapp_number,
            'test message',
            response_data.get('message', 'No response'),
            'Session Flow Management: 5-hour Expiry'
        )

    def test_message_window_tracking(self):
        """Test 24-hour messaging window tracking"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create a conversation context with recent guest message
        recent_time = timezone.now() - timedelta(hours=2)
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.main_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=recent_time
        )
        
        # Create a pending message in queue
        message = MessageQueue.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            message_type='test',
            message_content='Test message',
            scheduled_time=timezone.now(),
            status='pending'
        )
        
        # Send a message to trigger the 24-hour window check
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': 'response'
        }
        
        with patch('context_manager.tasks.send_pending_messages.delay') as mock_task:
            response = self.client.post(
                reverse('whatsapp-webhook'),
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            # Check that the task was called
            mock_task.assert_called_once_with(self.guest.whatsapp_number)
            
            # Log conversation
            self.log_conversation(
                self.guest.whatsapp_number,
                'response',
                'Message window tracking triggered',
                'Message Window Tracking: 24-hour Compliance'
            )

    def test_service_flows_reception(self):
        """Test Reception service flow"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an active conversation context with main menu step
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.main_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Request reception service
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '1'  # Reception
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
            self.guest.whatsapp_number,
            '1',
            response_data.get('message', 'No response'),
            'Service Flow: Reception'
        )

    def test_service_flows_housekeeping(self):
        """Test Housekeeping service flow"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an active conversation context with main menu step
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.main_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Request housekeeping service
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '2'  # Housekeeping
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
            self.guest.whatsapp_number,
            '2',
            response_data.get('message', 'No response'),
            'Service Flow: Housekeeping'
        )

    def test_service_flows_room_service_with_submenu(self):
        """Test Room Service flow with submenu navigation"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an active conversation context with service menu step
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id, self.service_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.service_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id, self.service_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Request breakfast from room service menu
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '1'  # Breakfast
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
            self.guest.whatsapp_number,
            '1',
            response_data.get('message', 'No response'),
            'Service Flow: Room Service with Submenu'
        )

    def test_service_flows_cafe(self):
        """Test Cafe service flow"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an active conversation context with main menu step
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.main_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Request cafe service
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '4'  # Cafe
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
            self.guest.whatsapp_number,
            '4',
            response_data.get('message', 'No response'),
            'Service Flow: Cafe'
        )

    def test_service_flows_management(self):
        """Test Management service flow"""
        # Create an active stay for the guest
        stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(days=2),
            status='active'
        )
        
        # Update guest status
        self.guest.status = 'checked_in'
        self.guest.save()
        
        # Create an active conversation context with main menu step
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'guest_id': self.guest.id,
                'stay_id': stay.id,
                'navigation_stack': [self.main_menu.id],
                'accumulated_data': {},
                'error_count': 0,
                'current_step_template': self.main_menu.id  # This is the key fix
            },
            is_active=True,
            navigation_stack=[self.main_menu.id],
            flow_expires_at=timezone.now() + timedelta(hours=5),
            last_guest_message_at=timezone.now()
        )
        
        # Request management service
        payload = {
            'from_no': self.guest.whatsapp_number,
            'message': '5'  # Management
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
            self.guest.whatsapp_number,
            '5',
            response_data.get('message', 'No response'),
            'Service Flow: Management'
        )