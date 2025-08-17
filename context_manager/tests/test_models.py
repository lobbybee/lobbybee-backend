from django.test import TestCase
from context_manager.models import (
    FlowTemplate, FlowStepTemplate, FlowAction, HotelFlowConfiguration,
    ConversationContext, MessageQueue, WebhookLog, ConversationMessage
)
from hotel.models import Hotel
from guest.models import Guest
from datetime import timedelta
from django.utils import timezone


class ContextManagerModelsTestCase(TestCase):
    def setUp(self):
        # Create a test hotel
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            email="test@hotel.com",
            phone="+1234567890"
        )
        
        # Create a test guest
        self.guest = Guest.objects.create(
            full_name="Test Guest",
            email="test@guest.com",
            whatsapp_number="+1234567891",
            nationality="US"
        )

    def test_flow_template_creation(self):
        """Test creating a FlowTemplate"""
        flow_template = FlowTemplate.objects.create(
            name="Test Flow Template",
            description="A test flow template",
            category="checkin",
            is_active=True
        )
        
        self.assertEqual(flow_template.name, "Test Flow Template")
        self.assertEqual(flow_template.category, "checkin")
        self.assertTrue(flow_template.is_active)
        self.assertEqual(str(flow_template), "Test Flow Template (checkin)")

    def test_flow_action_creation(self):
        """Test creating a FlowAction"""
        flow_action = FlowAction.objects.create(
            name="Send Notification",
            action_type="SEND_NOTIFICATION",
            configuration={"department": "reception"}
        )
        
        self.assertEqual(flow_action.name, "Send Notification")
        self.assertEqual(flow_action.action_type, "SEND_NOTIFICATION")
        self.assertEqual(str(flow_action), "Send Notification (SEND_NOTIFICATION)")

    def test_flow_step_template_creation(self):
        """Test creating a FlowStepTemplate"""
        flow_template = FlowTemplate.objects.create(
            name="Test Flow",
            description="A test flow",
            category="checkin",
            is_active=True
        )
        
        flow_step_template = FlowStepTemplate.objects.create(
            flow_template=flow_template,
            step_name="Welcome Step",
            message_template="Welcome to our hotel!",
            message_type="TEXT",
            options={"1": "Continue", "2": "Cancel"}
        )
        
        self.assertEqual(flow_step_template.step_name, "Welcome Step")
        self.assertEqual(flow_step_template.message_type, "TEXT")
        self.assertEqual(
            flow_step_template.options, 
            {"1": "Continue", "2": "Cancel"}
        )
        self.assertEqual(
            str(flow_step_template), 
            "Welcome Step (Test Flow)"
        )

    def test_hotel_flow_configuration_creation(self):
        """Test creating a HotelFlowConfiguration"""
        flow_template = FlowTemplate.objects.create(
            name="Test Flow",
            description="A test flow",
            category="checkin",
            is_active=True
        )
        
        config = HotelFlowConfiguration.objects.create(
            hotel=self.hotel,
            flow_template=flow_template,
            is_enabled=True,
            customization_data={
                "step_customizations": {
                    "1": {"message_template": "Custom welcome!"}
                }
            }
        )
        
        self.assertEqual(config.hotel, self.hotel)
        self.assertEqual(config.flow_template, flow_template)
        self.assertTrue(config.is_enabled)
        self.assertEqual(
            config.customization_data["step_customizations"]["1"]["message_template"],
            "Custom welcome!"
        )
        self.assertEqual(
            str(config),
            f"Test Flow config for {self.hotel.name}"
        )

    def test_conversation_context_creation(self):
        """Test creating a ConversationContext"""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={"test": "data"},
            is_active=True,
            navigation_stack=[1, 2, 3],
            flow_expires_at=timezone.now() + timedelta(hours=5)
        )
        
        self.assertEqual(context.user_id, self.guest.whatsapp_number)
        self.assertEqual(context.hotel, self.hotel)
        self.assertTrue(context.is_active)
        self.assertEqual(context.navigation_stack, [1, 2, 3])
        self.assertEqual(str(context), f"Context for {self.guest.whatsapp_number} at {self.hotel.name}")

    def test_message_queue_creation(self):
        """Test creating a MessageQueue entry"""
        message = MessageQueue.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            message_type="welcome",
            message_content="Welcome to our hotel!",
            scheduled_time=timezone.now(),
            status="pending"
        )
        
        self.assertEqual(message.user_id, self.guest.whatsapp_number)
        self.assertEqual(message.hotel, self.hotel)
        self.assertEqual(message.message_type, "welcome")
        self.assertEqual(message.status, "pending")
        self.assertIn("Message to", str(message))

    def test_webhook_log_creation(self):
        """Test creating a WebhookLog entry"""
        payload = {
            "from": self.guest.whatsapp_number,
            "message": "Hello"
        }
        
        log = WebhookLog.objects.create(
            payload=payload,
            processed_successfully=True
        )
        
        self.assertEqual(log.payload, payload)
        self.assertTrue(log.processed_successfully)
        self.assertIn("Webhook log", str(log))

    def test_conversation_message_creation(self):
        """Test creating a ConversationMessage entry"""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            context_data={},
            is_active=True
        )
        
        message = ConversationMessage.objects.create(
            context=context,
            message_content="Hello from guest",
            is_from_guest=True
        )
        
        self.assertEqual(message.context, context)
        self.assertTrue(message.is_from_guest)
        self.assertIn("Guest:", str(message))