from django.test import TestCase
from django.urls import reverse
from context_manager.models import (
    FlowTemplate, FlowStepTemplate, FlowStep, ConversationContext, ConversationMessage
)
from hotel.models import Hotel
from guest.models import Guest
from django.utils import timezone
import json

class ContextManagerFlowTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The log file is now initialized by test_00_log_setup.py
        cls.conversation_log_path = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/conversationLog.md"

    def setUp(self):
        """Set up the necessary data for testing the conversation flows."""
        # Create a test hotel
        self.hotel = Hotel.objects.create(
            name="Grand Test Hotel",
            email="contact@grandtest.com",
            phone="+1000000000"
        )

        # --- Create FlowTemplates for core scenarios ---
        self.discovery_flow = FlowTemplate.objects.create(
            name="New Guest Discovery Flow",
            category="new_guest_discovery",
            is_active=True
        )
        self.checkin_flow = FlowTemplate.objects.create(
            name="Guest Check-in Flow",
            category="guest_checkin",
            is_active=True
        )
        self.main_menu_flow = FlowTemplate.objects.create(
            name="Main Menu Flow",
            category="main_menu",
            is_active=True
        )

        # --- Create FlowStepTemplates for the Discovery Flow ---
        self.discovery_welcome = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Discovery Welcome",
            message_template="Welcome to the LobbyBee network! What would you like to do?",
            options={"1": "Create Account", "2": "Take a Demo"}
        )
        self.discovery_collect_name = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Collect Full Name",
            message_template="Great! What is your full name?",
        )
        self.account_success = FlowStepTemplate.objects.create(
            flow_template=self.discovery_flow,
            step_name="Account Success",
            message_template="Thanks, {full_name}! Your account is ready."
        )
        self.discovery_welcome.next_step_template = self.discovery_collect_name
        self.discovery_collect_name.next_step_template = self.account_success
        self.discovery_welcome.conditional_next_steps = {"1": self.discovery_collect_name.id}
        self.discovery_welcome.save()
        self.discovery_collect_name.save()

        # --- Create FlowStepTemplates for the Check-in Flow ---
        self.checkin_start = FlowStepTemplate.objects.create(
            flow_template=self.checkin_flow,
            step_name="Check-in Start",
            message_template="Welcome to {hotel_name}! To check in, please confirm your full name."
        )
        self.checkin_confirm = FlowStepTemplate.objects.create(
            flow_template=self.checkin_flow,
            step_name="Check-in Confirmation",
            message_template="Thanks, {full_name}! Your check-in is complete."
        )
        self.checkin_start.next_step_template = self.checkin_confirm
        self.checkin_start.save()

        # --- Create FlowStepTemplates for the Main Menu Flow ---
        self.main_menu_step = FlowStepTemplate.objects.create(
            flow_template=self.main_menu_flow,
            step_name="Main Menu",
            message_template="Welcome back! How can I help you?",
            options={"1": "Room Service", "2": "Housekeeping"}
        )

        # --- Create FlowTemplates for the Interactive Discovery Flow ---
        self.interactive_discovery_flow = FlowTemplate.objects.create(
            name="Interactive New Guest Discovery Flow",
            category="new_guest_discovery_interactive",
            is_active=True
        )
        # Main Flow
        self.interactive_welcome = FlowStepTemplate.objects.create(
            flow_template=self.interactive_discovery_flow,
            step_name="Interactive Welcome",
            message_template="""👋 Welcome to [Hotel Network]! I see you're new here.

🏨 What would you like to do?
1️⃣ Create Guest Account
2️⃣ Take Demo Tour
3️⃣ Find Hotels Near Me""",
            options={"1": "Create Guest Account", "2": "Take Demo Tour", "3": "Find Hotels Near Me"}
        )
        # Create Account Sub-flow
        self.interactive_collect_name = FlowStepTemplate.objects.create(
            flow_template=self.interactive_discovery_flow,
            step_name="Collect Full Name",
            message_template="📝 Let's create your account!\nPlease share your full name:",
        )
        self.interactive_collect_email = FlowStepTemplate.objects.create(
            flow_template=self.interactive_discovery_flow,
            step_name="Collect Email",
            message_template="📧 Great! Now your email address:",
        )
        self.interactive_collect_phone = FlowStepTemplate.objects.create(
            flow_template=self.interactive_discovery_flow,
            step_name="Collect Phone Number",
            message_template="📱 Your phone number:",
        )
        self.interactive_upload_id = FlowStepTemplate.objects.create(
            flow_template=self.interactive_discovery_flow,
            step_name="Collect ID Document",
            message_template="""🆔 Please upload your ID document (photo)
📸 Send as image""",
        )
        self.interactive_account_success = FlowStepTemplate.objects.create(
            flow_template=self.interactive_discovery_flow,
            step_name="Interactive Account Success",
            message_template="""✅ Account created successfully!
Your guest ID: {guest_id}

🏨 What's next?
1️⃣ Take Demo Tour
2️⃣ Find Hotels""",
            options={"1": "Take Demo Tour", "2": "Find Hotels"}
        )
        # Link steps
        self.interactive_welcome.conditional_next_steps = {"1": self.interactive_collect_name.id}
        self.interactive_welcome.save()
        self.interactive_collect_name.next_step_template = self.interactive_collect_email
        self.interactive_collect_name.save()
        self.interactive_collect_email.next_step_template = self.interactive_collect_phone
        self.interactive_collect_email.save()
        self.interactive_collect_phone.next_step_template = self.interactive_upload_id
        self.interactive_collect_phone.save()
        self.interactive_upload_id.next_step_template = self.interactive_account_success
        self.interactive_upload_id.save()

    def log_conversation(self, guest_number, message, response, test_name):
        """Log conversation to conversationLog.md"""
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"### {test_name} - {timestamp}\n\n"
        log_entry += f"**Guest ({guest_number}):** {message}\n\n"
        log_entry += f"**System:** {response}\n\n"
        log_entry += "---\n\n"
        
        with open(self.conversation_log_path, "a") as f:
            f.write(log_entry)

    def test_scenario_1_new_guest_discovery(self):
        """
        Test the flow for a new user sending a 'demo' message.
        Ensures the system creates a guest and starts the discovery flow.
        """
        new_whatsapp_number = "+9876543210"
        payload = {
            'from_no': new_whatsapp_number,
            'message': 'demo'
        }

        # 1. Initial "demo" message
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        response_data = response.json()
        self.log_conversation(new_whatsapp_number, payload['message'], response_data.get('message', 'Error'), 'Scenario 1: New Guest Discovery')

        # Assertions for the initial response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['status'], 'success')
        self.assertIn("Welcome to the LobbyBee network!", response_data['message'])

        # Assertions for database state
        self.assertTrue(Guest.objects.filter(whatsapp_number=new_whatsapp_number).exists())
        guest = Guest.objects.get(whatsapp_number=new_whatsapp_number)
        context = ConversationContext.objects.get(user_id=new_whatsapp_number)
        self.assertTrue(context.is_active)
        self.assertEqual(context.current_step.template, self.discovery_welcome)
        self.assertEqual(len(context.navigation_stack), 1)

        # 2. User chooses to create an account
        payload['message'] = '1'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        response_data = response.json()
        self.log_conversation(new_whatsapp_number, payload['message'], response_data.get('message', 'Error'), 'Scenario 1: New Guest Discovery')

        # Assertions for the second step
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['status'], 'success')
        self.assertIn("Great! What is your full name?", response_data['message'])

        # Assertions for context update
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.discovery_collect_name)
        self.assertEqual(len(context.navigation_stack), 2)

    def test_scenario_2_qr_code_checkin(self):
        """
        Test the flow for a user scanning a hotel-specific QR code.
        """
        qr_whatsapp_number = "+1234567890"
        payload = {
            'from_no': qr_whatsapp_number,
            'message': f'start-{self.hotel.id}'
        }

        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        response_data = response.json()
        self.log_conversation(qr_whatsapp_number, payload['message'], response_data.get('message', 'Error'), 'Scenario 2: QR Code Check-in')

        # Assertions for the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['status'], 'success')
        self.assertIn(f"Welcome to {self.hotel.name}!", response_data['message'])

        # Assertions for database state
        self.assertTrue(Guest.objects.filter(whatsapp_number=qr_whatsapp_number).exists())
        context = ConversationContext.objects.get(user_id=qr_whatsapp_number)
        self.assertTrue(context.is_active)
        self.assertEqual(context.hotel, self.hotel)
        self.assertEqual(context.current_step.template, self.checkin_start)

    def test_navigation_and_state_management(self):
        """
        Tests the 'back' and 'main menu' navigation and data accumulation.
        """
        nav_whatsapp_number = "+5555555555"
        
        # 1. Start the discovery flow
        response = self.client.post(reverse('whatsapp-webhook'), data={'from_no': nav_whatsapp_number, 'message': 'demo'}, content_type='application/json')
        self.log_conversation(nav_whatsapp_number, 'demo', response.json().get('message', 'Error'), 'Navigation & State')
        
        # 2. Move to the next step
        response = self.client.post(reverse('whatsapp-webhook'), data={'from_no': nav_whatsapp_number, 'message': '1'}, content_type='application/json')
        self.log_conversation(nav_whatsapp_number, '1', response.json().get('message', 'Error'), 'Navigation & State')
        context = ConversationContext.objects.get(user_id=nav_whatsapp_number)
        self.assertEqual(context.current_step.template, self.discovery_collect_name)

        # 3. Provide name (which should be stored in accumulated_data)
        response = self.client.post(reverse('whatsapp-webhook'), data={'from_no': nav_whatsapp_number, 'message': 'John Doe'}, content_type='application/json')
        self.log_conversation(nav_whatsapp_number, 'John Doe', response.json().get('message', 'Error'), 'Navigation & State')
        context.refresh_from_db()
        self.assertEqual(context.context_data['accumulated_data'].get('full_name'), 'John Doe')

        # 4. Navigate 'back' (should skip the 'collect name' step since we have the name)
        response = self.client.post(reverse('whatsapp-webhook'), data={'from_no': nav_whatsapp_number, 'message': 'back'}, content_type='application/json')
        self.log_conversation(nav_whatsapp_number, 'back', response.json().get('message', 'Error'), 'Navigation & State')
        context.refresh_from_db()
        self.assertEqual(response.json()['status'], 'success')
        self.assertIn("Welcome to the LobbyBee network!", response.json()['message'])
        self.assertEqual(context.current_step.template, self.discovery_welcome)
        self.assertEqual(len(context.navigation_stack), 1)

        # 5. Navigate to 'main menu'
        response = self.client.post(reverse('whatsapp-webhook'), data={'from_no': nav_whatsapp_number, 'message': 'main menu'}, content_type='application/json')
        self.log_conversation(nav_whatsapp_number, 'main menu', response.json().get('message', 'Error'), 'Navigation & State')
        context.refresh_from_db()
        self.assertEqual(response.json()['status'], 'success')
        self.assertIn("Welcome back!", response.json()['message'])
        self.assertEqual(context.current_step.template, self.main_menu_step)
        self.assertEqual(len(context.navigation_stack), 1) # Navigation stack is reset

    def test_scenario_3_new_guest_discovery_full(self):
        """
        Test the full "Create Guest Account" sub-flow for a new user.
        """
        new_user_number = "+1122334455"
        test_name = "Scenario 3: Full Guest Discovery"

        # 1. Initial "Hi" message
        payload = {'from_no': new_user_number, 'message': 'Hi'}
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(new_user_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Welcome to [Hotel Network]!", response.json()['message'])
        context = ConversationContext.objects.get(user_id=new_user_number)
        self.assertEqual(context.current_step.template, self.interactive_welcome)

        # 2. User chooses to create an account
        payload['message'] = '1'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(new_user_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Let's create your account!", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.interactive_collect_name)

        # 3. User provides full name
        payload['message'] = 'Test User'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(new_user_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Now your email address", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.interactive_collect_email)
        self.assertEqual(context.context_data['accumulated_data']['full_name'], 'Test User')

        # 4. User provides email
        payload['message'] = 'test@example.com'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(new_user_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Your phone number", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.interactive_collect_phone)
        self.assertEqual(context.context_data['accumulated_data']['email'], 'test@example.com')

        # 5. User provides phone number
        payload['message'] = '+1122334455'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(new_user_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("upload your ID document", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.interactive_upload_id)
        self.assertEqual(context.context_data['accumulated_data']['phone_number'], '+1122334455')

        # 6. User "uploads" ID (we just send some text, as we don't handle media)
        payload['message'] = 'ID_document.jpg'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(new_user_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Account created successfully!", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.interactive_account_success)
        guest = Guest.objects.get(whatsapp_number=new_user_number)
        self.assertIn(str(guest.id), response.json()['message'])
