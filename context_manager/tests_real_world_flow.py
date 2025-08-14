from django.test import TestCase
from context_manager.models import FlowStep, ConversationContext
from context_manager.services import process_incoming_message
from hotel.models import Hotel, Room, RoomCategory
from guest.models import Guest, Stay
from datetime import datetime, timedelta, time
from django.utils import timezone
import uuid

class RealWorldComplexFlowTest(TestCase):
    """Test a complex real-world guest flow simulating actual hotel operations"""

    def setUp(self):
        """Set up test data for a realistic hotel scenario"""
        # Create a hotel
        self.hotel = Hotel.objects.create(
            id=uuid.uuid4(),
            name="Grand Plaza Hotel",
            email="info@grandplaza.com",
            phone="+1234567890",
            wifi_password="grandplaza2025"
        )
        
        # Create a room category
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Deluxe Suite",
            description="Spacious suite with city view",
            base_price=300.00,
            max_occupancy=4
        )
        
        # Create a room
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="505",
            category=self.room_category,
            floor=5,
            status="available"
        )
        
        # Create a guest
        self.guest = Guest.objects.create(
            full_name="Michael Johnson",
            email="michael.johnson@example.com",
            whatsapp_number="+1987654321",
            nationality="American"
        )
        
        # Create a stay
        self.stay = Stay.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            room=self.room,
            status="active",
            check_in_date=timezone.now(),
            check_out_date=timezone.now() + timedelta(days=3),
            number_of_guests=2
        )
        
        # Create FlowStep records for a comprehensive hotel experience
        # Checkin start step (required by the system)
        self.checkin_start = FlowStep.objects.create(
            step_id='checkin_start',
            hotel=self.hotel,
            flow_type='checkin',
            message_template="Welcome to Grand Plaza Hotel, {guest_name}! You're in room {room_number}. How can we assist you today?\n1. Room Service\n2. Housekeeping\n3. Café Menu\n4. Concierge Services\n5. Check-out\n6. Speak to Management",
            options={'1': 'Room Service', '2': 'Housekeeping', '3': 'Café Menu', '4': 'Concierge', '5': 'Check-out', '6': 'Management'}
        )
        
        # Room Service menu
        self.room_service_menu = FlowStep.objects.create(
            step_id='room_service_menu',
            hotel=self.hotel,
            flow_type='room_service',
            message_template="Room Service Menu:\n1. Breakfast (7:00 AM - 11:00 AM)\n2. Lunch (12:00 PM - 3:00 PM)\n3. Dinner (6:00 PM - 10:00 PM)\n4. Snacks & Beverages\n5. Back to Main Menu",
            options={'1': 'Breakfast', '2': 'Lunch', '3': 'Dinner', '4': 'Snacks', '5': 'Main Menu'}
        )
        
        # Breakfast menu
        self.breakfast_menu = FlowStep.objects.create(
            step_id='breakfast_menu',
            hotel=self.hotel,
            flow_type='room_service',
            message_template="Breakfast Menu:\n1. Continental Breakfast - $15\n2. American Breakfast - $20\n3. Vegetarian Breakfast - $18\n4. Back to Room Service",
            options={'1': 'Continental', '2': 'American', '3': 'Vegetarian', '4': 'Back'}
        )
        
        # Order confirmation
        self.order_confirmation = FlowStep.objects.create(
            step_id='order_confirmation',
            hotel=self.hotel,
            flow_type='room_service',
            message_template="You've ordered American Breakfast for $20. Room {room_number}. Delivery in 30 minutes. Confirm?\n1. Confirm Order\n2. Cancel Order",
            options={'1': 'Confirm', '2': 'Cancel'}
        )
        
        # Order placed
        self.order_placed = FlowStep.objects.create(
            step_id='order_placed',
            hotel=self.hotel,
            flow_type='room_service',
            message_template="Your order has been placed! Thank you for choosing our room service. Enjoy your meal!",
            options={}
        )
        
        # Housekeeping request
        self.housekeeping_request = FlowStep.objects.create(
            step_id='housekeeping_request',
            hotel=self.hotel,
            flow_type='housekeeping',
            message_template="Housekeeping Services:\n1. Daily Cleaning\n2. Towel & Linen Change\n3. Mini-bar Stocking\n4. Special Requests\n5. Back to Main Menu",
            options={'1': 'Daily Cleaning', '2': 'Towels', '3': 'Mini-bar', '4': 'Special', '5': 'Main Menu'}
        )
        
        # Special housekeeping request
        self.special_housekeeping = FlowStep.objects.create(
            step_id='special_housekeeping',
            hotel=self.hotel,
            flow_type='housekeeping',
            message_template="Please describe your special housekeeping request:",
            options={}
        )
        
        # Housekeeping request confirmed
        self.housekeeping_confirmed = FlowStep.objects.create(
            step_id='housekeeping_confirmed',
            hotel=self.hotel,
            flow_type='housekeeping',
            message_template="Your housekeeping request has been received. Our team will attend to it shortly.",
            options={}
        )
        
        # Café menu
        self.cafe_menu = FlowStep.objects.create(
            step_id='cafe_menu',
            hotel=self.hotel,
            flow_type='cafe',
            message_template="Café Menu:\n1. Coffee & Tea\n2. Pastries & Desserts\n3. Light Meals\n4. Back to Main Menu",
            options={'1': 'Beverages', '2': 'Pastries', '3': 'Meals', '4': 'Main Menu'}
        )
        
        # Check-out confirmation
        self.checkout_confirmation = FlowStep.objects.create(
            step_id='checkout_confirmation',
            hotel=self.hotel,
            flow_type='checkout',
            message_template="You're checking out today, {guest_name}. Your final bill is $900. Confirm check-out?\n1. Confirm Check-out\n2. Back to Main Menu",
            options={'1': 'Confirm', '2': 'Cancel'}
        )
        
        # Check-out complete
        self.checkout_complete = FlowStep.objects.create(
            step_id='checkout_complete',
            hotel=self.hotel,
            flow_type='checkout',
            message_template="Thank you for staying with us, {guest_name}! We hope you enjoyed your stay at Grand Plaza Hotel. Safe travels!",
            options={}
        )
        
        # Management contact
        self.management_contact = FlowStep.objects.create(
            step_id='management_contact',
            hotel=self.hotel,
            flow_type='management',
            message_template="Please describe your concern or feedback for management:",
            options={}
        )
        
        # Management response
        self.management_response = FlowStep.objects.create(
            step_id='management_response',
            hotel=self.hotel,
            flow_type='management',
            message_template="Thank you for your feedback, {guest_name}. A manager will contact you shortly at {guest_phone}.",
            options={}
        )
        
        # Set up conditional next steps for the checkin_start step
        self.checkin_start.conditional_next_steps = {
            '1': 'room_service_menu',
            '2': 'housekeeping_request',
            '5': 'checkout_confirmation'
        }
        self.checkin_start.save()
        
        # Set up conditional next steps for the room_service_menu step
        self.room_service_menu.conditional_next_steps = {
            '1': 'breakfast_menu',
            '5': 'checkin_start'
        }
        self.room_service_menu.save()
        
        # Set up conditional next steps for the breakfast_menu step
        self.breakfast_menu.conditional_next_steps = {
            '2': 'order_confirmation',
            '4': 'room_service_menu'
        }
        self.breakfast_menu.save()
        
        # Set up conditional next steps for the order_confirmation step
        self.order_confirmation.conditional_next_steps = {
            '1': 'order_placed',
            '2': 'room_service_menu'
        }
        self.order_confirmation.save()
        
        # Set up conditional next steps for the housekeeping_request step
        self.housekeeping_request.conditional_next_steps = {
            '4': 'special_housekeeping',
            '5': 'checkin_start'
        }
        self.housekeeping_request.save()
        
        # Set up next step for the special_housekeeping step
        self.special_housekeeping.next_step = self.housekeeping_confirmed
        self.special_housekeeping.save()
        
        # Set up conditional next steps for the checkout_confirmation step
        self.checkout_confirmation.conditional_next_steps = {
            '1': 'checkout_complete',
            '2': 'checkin_start'
        }
        self.checkout_confirmation.save()

    def simulate_conversation(self, messages):
        """Simulate a conversation with a series of messages"""
        conversation_log = []
        
        for i, message in enumerate(messages):
            payload = {
                'from_no': self.guest.whatsapp_number,
                'message': message
            }
            result = process_incoming_message(payload)
            conversation_log.append(f"Guest: {message}")
            conversation_log.append(f"System: {result['message']}")
            
            # If this is not the last message and the conversation ended, 
            # create a new context to continue
            if result['status'] == 'success' and 'Conversation completed successfully' in result['message'] and i < len(messages) - 1:
                # In a real implementation, we would create a new context here
                # For this test, we'll just note that the conversation restarted
                conversation_log.append("(Conversation would restart with new context in real implementation)")
        
        return conversation_log

    def test_room_service_flow(self):
        """Test a room service flow"""
        conversation_log = []
        
        # Log initial greeting
        conversation_log.append("=== Grand Plaza Hotel - Room Service Flow ===")
        conversation_log.append(f"Guest: {self.guest.full_name} ({self.guest.whatsapp_number})")
        conversation_log.append(f"Room: {self.room.room_number} - {self.room_category.name}")
        conversation_log.append("")
        conversation_log.append("--- Conversation Start ---")
        conversation_log.append("")
        
        # Simulate messages for room service flow
        messages = [
            "1",  # Room Service
            "1",  # Breakfast
            "2",  # American Breakfast
            "1",  # Confirm Order
        ]
        
        # Clean up any existing context for this user/hotel combination
        ConversationContext.objects.filter(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel
        ).delete()
        
        # Create initial context for room service flow
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'room_service',
                'current_step': 'checkin_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {
                    'guest_name': self.guest.full_name,
                    'room_number': self.room.room_number,
                    'guest_phone': self.guest.whatsapp_number,
                    'item': 'American Breakfast',
                    'price': 20
                },
                'navigation_stack': ['checkin_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        for message in messages:
            payload = {
                'from_no': self.guest.whatsapp_number,
                'message': message
            }
            result = process_incoming_message(payload)
            conversation_log.append(f"Guest: {message}")
            conversation_log.append(f"System: {result['message']}")
        
        conversation_log.append("")
        conversation_log.append("--- Conversation End ---")
        
        return conversation_log

    def test_housekeeping_flow(self):
        """Test a housekeeping flow"""
        conversation_log = []
        
        conversation_log.append("=== Grand Plaza Hotel - Housekeeping Flow ===")
        conversation_log.append("")
        conversation_log.append("--- Conversation Start ---")
        conversation_log.append("")
        
        # Clean up any existing context for this user/hotel combination
        ConversationContext.objects.filter(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel
        ).delete()
        
        # Create initial context for housekeeping flow
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'housekeeping',
                'current_step': 'checkin_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {
                    'guest_name': self.guest.full_name,
                    'room_number': self.room.room_number,
                    'guest_phone': self.guest.whatsapp_number
                },
                'navigation_stack': ['checkin_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        messages = [
            "2",  # Housekeeping
            "4",  # Special Requests
            "Please arrange for an extra blanket and pillows for the sofa bed.",
        ]
        
        for message in messages:
            payload = {
                'from_no': self.guest.whatsapp_number,
                'message': message
            }
            result = process_incoming_message(payload)
            conversation_log.append(f"Guest: {message}")
            conversation_log.append(f"System: {result['message']}")
        
        conversation_log.append("")
        conversation_log.append("--- Conversation End ---")
        
        return conversation_log

    def test_checkout_flow(self):
        """Test a checkout flow"""
        conversation_log = []
        
        conversation_log.append("=== Grand Plaza Hotel - Check-out Flow ===")
        conversation_log.append("")
        conversation_log.append("--- Conversation Start ---")
        conversation_log.append("")
        
        # Clean up any existing context for this user/hotel combination
        ConversationContext.objects.filter(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel
        ).delete()
        
        # Create initial context for checkout flow
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={
                'current_flow': 'checkout',
                'current_step': 'checkin_start',
                'guest_id': self.guest.id,
                'stay_id': self.stay.id,
                'accumulated_data': {
                    'guest_name': self.guest.full_name,
                    'room_number': self.room.room_number,
                    'guest_phone': self.guest.whatsapp_number,
                    'total_amount': 900
                },
                'navigation_stack': ['checkin_start'],
                'error_count': 0,
            },
            is_active=True
        )
        
        messages = [
            "5",  # Check-out
            "1",  # Confirm Check-out
        ]
        
        for message in messages:
            payload = {
                'from_no': self.guest.whatsapp_number,
                'message': message
            }
            result = process_incoming_message(payload)
            conversation_log.append(f"Guest: {message}")
            conversation_log.append(f"System: {result['message']}")
        
        conversation_log.append("")
        conversation_log.append("--- Conversation End ---")
        
        return conversation_log

    def test_complex_guest_flow(self):
        """Test a complex guest flow simulating real hotel operations"""
        # Create the conversation log
        log_content = "# Grand Plaza Hotel - Guest Experience Simulation\n\n"
        log_content += "## Complex Guest Flow Simulation\n\n"
        log_content += "This log simulates a real-world complex guest flow at Grand Plaza Hotel, including room service, housekeeping, and check-out.\n\n"
        
        # Room Service Flow
        room_service_log = self.test_room_service_flow()
        for line in room_service_log:
            if line.startswith("==="):
                log_content += f"**{line}**\n\n"
            elif line.startswith("---"):
                log_content += f"_{line}_\n\n"
            elif line.startswith("Guest:") or line.startswith("System:"):
                log_content += f"**{line}**\n"
            else:
                log_content += f"{line}\n"
        
        log_content += "\n---\n\n"
        
        # Housekeeping Flow
        housekeeping_log = self.test_housekeeping_flow()
        for line in housekeeping_log:
            if line.startswith("==="):
                log_content += f"**{line}**\n\n"
            elif line.startswith("---"):
                log_content += f"_{line}_\n\n"
            elif line.startswith("Guest:") or line.startswith("System:"):
                log_content += f"**{line}**\n"
            else:
                log_content += f"{line}\n"
        
        log_content += "\n---\n\n"
        
        # Check-out Flow
        checkout_log = self.test_checkout_flow()
        for line in checkout_log:
            if line.startswith("==="):
                log_content += f"**{line}**\n\n"
            elif line.startswith("---"):
                log_content += f"_{line}_\n\n"
            elif line.startswith("Guest:") or line.startswith("System:"):
                log_content += f"**{line}**\n"
            else:
                log_content += f"{line}\n"
        
        log_content += "\n=== Simulation Complete ===\n"
        
        # Write to conversationLog.md
        with open('/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/conversationLog.md', 'w') as f:
            f.write(log_content)
        
        print("Complex guest flow simulation completed and logged to conversationLog.md")