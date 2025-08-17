from django.test import TestCase
from django.urls import reverse
from context_manager.models import (
    FlowTemplate, FlowStepTemplate, ConversationContext
)
from hotel.models import Hotel, Room, RoomCategory
from guest.models import Guest, Stay
from django.utils import timezone
import datetime

class InStayServiceFlowTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The log file is now initialized by test_00_log_setup.py
        cls.conversation_log_path = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/conversationLog.md"

    def setUp(self):
        """Set up data for an in-stay guest."""
        self.hotel = Hotel.objects.create(name="Grand Palace Hotel")
        self.guest = Guest.objects.create(
            full_name="John Doe",
            whatsapp_number="+2233445566"
        )
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Deluxe Suite",
            base_price=250.00,
            max_occupancy=2
        )
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="205",
            category=self.room_category,
            floor=2
        )
        self.stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            status='active',
            check_in_date=timezone.now() - datetime.timedelta(days=1),
            check_out_date=timezone.now() + datetime.timedelta(days=2)
        )

        # --- Create FlowTemplates for In-Stay Services ---
        self.in_stay_flow = FlowTemplate.objects.create(
            name="In-Stay Services Flow",
            category="in_stay_services",
            is_active=True
        )

        # Main Menu
        self.in_stay_main_menu = FlowStepTemplate.objects.create(
            flow_template=self.in_stay_flow,
            step_name="In-Stay Main Menu",
            message_template="""🏨 Welcome back, {guest_name}!
Room {room_number} | {hotel_name}

🛎️ How can I help you today?""",
            options={
                "1": "Reception Services",
                "2": "Housekeeping",
                "3": "Room Service",
            }
        )

        # Reception Sub-flow
        self.reception_menu = FlowStepTemplate.objects.create(
            flow_template=self.in_stay_flow,
            step_name="Reception Services Menu",
            message_template="""🏨 Reception Services""",
            options={
                "1": "Extra Towels/Amenities",
                "2": "Wake-up Call",
            }
        )
        self.amenities_menu = FlowStepTemplate.objects.create(
            flow_template=self.in_stay_flow,
            step_name="Amenities Menu",
            message_template="""🛁 Amenities Request
What do you need?""",
            options={
                "1": "Extra Towels",
                "2": "Extra Pillows",
            }
        )
        self.towels_confirm = FlowStepTemplate.objects.create(
            flow_template=self.in_stay_flow,
            step_name="Extra Towels Confirmation",
            message_template="""✅ Extra towels requested for Room {room_number}
⏰ Delivery time: 15-20 minutes

Anything else?""",
            options={"1": "Back to Reception", "2": "Main Menu"}
        )

        # Link steps
        self.in_stay_main_menu.conditional_next_steps = {"1": self.reception_menu.id}
        self.in_stay_main_menu.save()
        self.reception_menu.conditional_next_steps = {"1": self.amenities_menu.id}
        self.reception_menu.save()
        self.amenities_menu.conditional_next_steps = {"1": self.towels_confirm.id}
        self.amenities_menu.save()

    def log_conversation(self, guest_number, message, response, test_name):
        """Log conversation to conversationLog.md"""
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"### {test_name} - {timestamp}\n\n"
        log_entry += f"**Guest ({guest_number}):** {message}\n\n"
        log_entry += f"**System:** {response}\n\n"
        log_entry += "---\n\n"
        
        with open(self.conversation_log_path, "a") as f:
            f.write(log_entry)

    def test_in_stay_reception_services_flow(self):
        """
        Test the flow for an existing, checked-in guest accessing reception services.
        """
        test_name = "Scenario: In-Stay Service Access"
        payload = {'from_no': self.guest.whatsapp_number, 'message': 'Hi'}

        # 1. Initial "Hi" from checked-in guest
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(self.guest.whatsapp_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"Welcome back, {self.guest.full_name}!", response.json()['message'])
        context = ConversationContext.objects.get(user_id=self.guest.whatsapp_number)
        self.assertEqual(context.current_step.template, self.in_stay_main_menu)

        # 2. User chooses Reception Services
        payload['message'] = '1'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(self.guest.whatsapp_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Reception Services", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.reception_menu)

        # 3. User chooses Extra Towels/Amenities
        payload['message'] = '1'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(self.guest.whatsapp_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Amenities Request", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.amenities_menu)

        # 4. User chooses Extra Towels
        payload['message'] = '1'
        response = self.client.post(reverse('whatsapp-webhook'), data=payload, content_type='application/json')
        self.log_conversation(self.guest.whatsapp_number, payload['message'], response.json().get('message', 'Error'), test_name)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Extra towels requested", response.json()['message'])
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.towels_confirm)
