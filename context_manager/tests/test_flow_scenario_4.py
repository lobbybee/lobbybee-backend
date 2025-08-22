from django.test import TestCase
from django.urls import reverse
from context_manager.models import (
    FlowTemplate, FlowStepTemplate, ConversationContext
)
from hotel.models import Hotel, Room, RoomCategory
from guest.models import Guest, Stay
from django.utils import timezone
import datetime

class ReturningGuestFlowTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The log file is now initialized by test_00_log_setup.py
        cls.conversation_log_path = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/conversationLog.md"

    def setUp(self):
        """Set up data for a returning guest and session expiry test."""
        # Create hotels and a guest with a past stay
        self.hotel = Hotel.objects.create(name="Grand Palace Hotel")
        self.guest = Guest.objects.create(
            full_name="Sarah Johnson",
            whatsapp_number="+3344556677",
            loyalty_points=2450
        )
        room_cat = RoomCategory.objects.create(hotel=self.hotel, name="Suite", base_price=150, max_occupancy=2)
        room = Room.objects.create(hotel=self.hotel, room_number="101", category=room_cat, floor=1)
        Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=room,
            status='completed',
            check_in_date=timezone.now() - datetime.timedelta(days=30),
            check_out_date=timezone.now() - datetime.timedelta(days=27)
        )

        # --- Create FlowTemplates for Returning Guest Flow ---
        self.returning_guest_flow = FlowTemplate.objects.create(
            name="Returning Guest Flow",
            category="returning_guest",
            is_active=True
        )
        self.returning_welcome = FlowStepTemplate.objects.create(
            flow_template=self.returning_guest_flow,
            step_name="Returning Guest Welcome",
            message_template="""👋 Welcome back, {guest_name}!

🏨 Your Account Options:
1️⃣ View Stay History
2️⃣ Make New Reservation
3️⃣ Update Profile
4️⃣ Loyalty Points: {loyalty_points}""",
            options={
                "1": "View Stay History",
                "2": "Make New Reservation",
                "3": "Update Profile",
            }
        )
        self.stay_history_list = FlowStepTemplate.objects.create(
            flow_template=self.returning_guest_flow,
            step_name="Stay History List",
            message_template="""📚 Your Stay History

Recent stays:
1️⃣ Grand Palace Hotel - Dec 2024""",
            options={"1": "View Details"}
        )
        self.returning_welcome.conditional_next_steps = {"1": self.stay_history_list.id}
        self.returning_welcome.save()

        # --- Create minimal Main Menu flow for session expiry test ---
        main_menu_flow = FlowTemplate.objects.create(name="Main Menu Flow", category="main_menu", is_active=True)
        self.main_menu_step = FlowStepTemplate.objects.create(
            flow_template=main_menu_flow,
            step_name="Main Menu",
            message_template="Welcome back! How can I help you?",
            options={"1": "Room Service"}
        )

    def log_conversation(self, guest_number, message, response, test_name):
        """Log conversation to conversationLog.md"""
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"### {test_name} - {timestamp}\n\n"
        log_entry += f"**Guest ({guest_number}):** {message}\n\n"
        log_entry += f"**System:** {response}\n\n"
        log_entry += "---\n\n"
        
        with open(self.conversation_log_path, "a") as f:
            f.write(log_entry)

    def test_returning_guest_flow(self):
        """
        Test the flow for a known guest with no active stay.
        """
        test_name = "Scenario 4: Returning Guest"
        payload = {'from_no': self.guest.whatsapp_number, 'message': 'Hello'}

        # 1. Initial "Hello" from returning guest
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(self.guest.whatsapp_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"Welcome back, {self.guest.full_name}!", response.json()['message'])
        self.assertIn(f"Loyalty Points: {self.guest.loyalty_points}", response.json()['message'])
        context = ConversationContext.objects.get(user_id=self.guest.whatsapp_number)
        self.assertEqual(context.current_step.template, self.returning_welcome)

        # 2. User chooses to view stay history
        payload['message'] = '1'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(self.guest.whatsapp_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Your Stay History", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.stay_history_list)

    def test_session_expiry(self):
        """
        Test that a flow expires after 5 hours and the user is reset to the main menu.
        """
        test_name = "Session Management: 5-Hour Expiry"
        payload = {'from_no': self.guest.whatsapp_number, 'message': 'Hello'}

        # 1. Start a conversation
        self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        context = ConversationContext.objects.get(user_id=self.guest.whatsapp_number)

        # 2. Manually expire the context by setting last_activity to be old
        # Use update to bypass auto_now=True on the last_activity field
        ConversationContext.objects.filter(pk=context.pk).update(last_activity=timezone.now() - datetime.timedelta(hours=6))

        # 3. Send another message to trigger the expiry logic
        payload['message'] = '1' # Try to continue the expired flow
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(self.guest.whatsapp_number, payload['message'], response.json().get('message', 'Error'), test_name)
        
        # 4. Assert that the session was reset to the main menu
        self.assertEqual(response.status_code, 200)
        self.assertIn("Your session has expired due to inactivity. Returning to the main menu.", response.json()['message'])
        self.assertIn("Welcome back! How can I help you?", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.main_menu_step)
