import json
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from pathlib import Path
import logging

from hotel.models import Hotel
from context_manager.models import FlowTemplate, FlowStepTemplate, Placeholder

# Suppress INFO logs from the application to keep test output clean
logging.disable(logging.INFO)

class MessageFormattingTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.conversation_log = []
        self.user_id_counter = 0

        # --- Create Demo Hotel ---
        self.demo_hotel = Hotel.objects.create(
            id='00000000-0000-0000-0000-000000000001',
            name='LobbyBee Demo',
            is_demo=True,
            phone='+10000000000',
            email='demo@lobbybee.com'
        )

        # --- Create Placeholders ---
        Placeholder.objects.create(name='hotel_phone', resolving_logic='hotel.phone')
        Placeholder.objects.create(name='hotel_email', resolving_logic='hotel.email')

        # --- Create FlowTemplates ---
        self.random_guest_flow = FlowTemplate.objects.create(
            name='Random Guest Flow',
            category='random_guest',
            is_active=True
        )
        self.services_flow = FlowTemplate.objects.create(
            name='Hotel Services Flow',
            category='hotel_services',
            is_active=True
        )

        # --- Create FlowStepTemplates for random_guest flow ---
        self.welcome_step = FlowStepTemplate.objects.create(
            flow_template=self.random_guest_flow,
            step_name='Welcome Message',
            message_template=json.loads('{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Welcome! How can we assist you today?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "demo", "title": "View Demo"}}, {"type": "reply", "reply": {"id": "contact", "title": "Contact Us"}}]}}}'),
            options={"demo": "View Demo", "contact": "Contact Us"}
        )
        self.demo_services_step = FlowStepTemplate.objects.create(
            flow_template=self.random_guest_flow,
            step_name='Demo Services',
            message_template=json.loads('{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Here is a demo of our premium services. You can explore:"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "explore_services", "title": "Hotel Services"}}]}}}'),
            options={"explore_services": "Hotel Services"}
        )
        self.contact_step = FlowStepTemplate.objects.create(
            flow_template=self.random_guest_flow,
            step_name='Contact Details',
            message_template=json.loads('{\"text\": \"Contact Information:\\n\\ud83d\\udcde Phone: {hotel_phone}\\n\\ud83d\\udce7 Email: {hotel_email}\"}')
        )
        
        # --- Create first step for hotel_services flow ---
        self.services_menu_step = FlowStepTemplate.objects.create(
            flow_template=self.services_flow,
            step_name='Services Menu',
            message_template=json.loads('{"type": "interactive", "interactive": {"type": "list", "body": {"text": "How can we assist you today?"}, "action": {"button": "Select Service", "sections": [{"title": "Hotel Services", "rows": [{"id": "reception", "title": "Reception"}]}]}}}')
        )

        # --- Link steps ---
        self.welcome_step.conditional_next_steps = {
            "demo": self.demo_services_step.id,
            "contact": self.contact_step.id
        }
        self.welcome_step.save()

        self.demo_services_step.conditional_next_steps = {
            "explore_services": self.services_menu_step.id
        }
        self.demo_services_step.save()

    def tearDown(self):
        # Write conversation log to file
        log_file_path = Path(__file__).resolve().parent.parent.parent / 'conversationLog.md'
        with open(log_file_path, 'a') as f:
            f.write('\n\n---\n\n## Test Conversation: Message Formatting (ORM Setup)\n\n')
            for entry in self.conversation_log:
                f.write(entry)
        
        # Re-enable logging
        logging.disable(logging.NOTSET)

    def _send_message(self, user_id, message):
        # Helper to send a message and log it
        self.conversation_log.append(f"**User ({user_id}):** {message}\n\n")
        response = self.client.post(reverse('whatsapp-webhook'), {'from_no': user_id, 'message': message}, format='json')
        
        self.assertEqual(response.status_code, 200, f"API call failed with status {response.status_code}: {response.content}")
        
        response_data = response.json()
        messages = response_data.get('messages', [])
        for msg in messages:
            json_str = json.dumps(msg, indent=2)
            log_entry = f"**Bot:**\n```json\n{json_str}\n```\n\n"
            self.conversation_log.append(log_entry)
        
        return response_data

    def test_demo_flow_and_message_formats(self):
        """
        Tests the demo flow, checking for correct interactive and text message formats.
        """
        self.user_id_counter += 1
        user_id = f"test_user_{self.user_id_counter}"

        # 1. User sends "demo" to start the flow
        response = self._send_message(user_id, "demo")
        
        messages = response.get('messages', [])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].get('type'), 'interactive')
        self.assertEqual(messages[0].get('interactive', {}).get('type'), 'button')
        self.assertIn('Welcome!', messages[0].get('interactive', {}).get('body', {}).get('text'))

        # 2. User selects "Contact Us"
        response = self._send_message(user_id, "contact")
        
        messages = response.get('messages', [])
        self.assertEqual(len(messages), 1)
        self.assertIn('text', messages[0])
        self.assertNotIn('type', messages[0])
        self.assertIn('Contact Information', messages[0].get('text'))

    def test_main_menu_command_and_multiple_messages(self):
        """
        Tests the 'main menu' command to ensure it returns multiple, correctly formatted messages.
        """
        self.user_id_counter += 1
        user_id = f"test_user_{self.user_id_counter}"

        # 1. Start a flow by sending "demo"
        self._send_message(user_id, "demo")

        # 2. User sends "main menu" command
        response = self._send_message(user_id, "main menu")
        
        messages = response.get('messages', [])
        self.assertEqual(len(messages), 2, "Expected two messages: a notification and the main menu.")
        
        self.assertIn('text', messages[0])
        self.assertEqual(messages[0]['text'], 'Returning to the main menu.')

        self.assertEqual(messages[1].get('type'), 'interactive')
        self.assertEqual(messages[1].get('interactive', {}).get('type'), 'button')
        self.assertIn('Welcome!', messages[1].get('interactive', {}).get('body', {}).get('text'))