from django.test import TransactionTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from datetime import timedelta
from context_manager.models import (
    FlowTemplate, FlowStepTemplate, ConversationContext, FlowStep
)
from hotel.models import Hotel
from guest.models import Guest
from context_manager.services.context import reset_conversation

from context_manager.services.flow import start_flow

class NewFeaturesTestCase(TransactionTestCase):
    def setUp(self):
        self.hotel = Hotel.objects.create(name="Feature Test Hotel")
        self.guest = Guest.objects.create(full_name="Feature Guest", whatsapp_number="+1112223333")

        # Flow for navigation testing
        self.nav_flow = FlowTemplate.objects.create(name="Nav Flow", category="nav_flow", is_active=True)
        self.step_a = FlowStepTemplate.objects.create(
            flow_template=self.nav_flow,
            step_name="Step A",
            message_template="This is Step A.",
            allowed_flow_categories=["jump_flow"]
        )

        # Flow to be jumped to
        self.jump_flow = FlowTemplate.objects.create(name="Jump Flow", category="jump_flow", is_active=True)
        self.step_b = FlowStepTemplate.objects.create(
            flow_template=self.jump_flow,
            step_name="Step B",
            message_template="This is Step B."
        )

    def test_allowed_flow_category_navigation(self):
        """Test that user input matching an allowed_flow_categories triggers a new flow."""
        # Create context and start the initial flow
        context, _ = ConversationContext.objects.get_or_create(user_id=self.guest.whatsapp_number, hotel=self.hotel)
        start_flow(context, 'nav_flow')
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.step_a)

        # Send a message that matches the allowed category
        response = self.client.post(reverse('whatsapp-webhook'), data={'from_no': self.guest.whatsapp_number, 'message': 'jump_flow'}, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("This is Step B", response.json()['message'])
        
        context.refresh_from_db()
        self.assertEqual(context.current_step.template, self.step_b)

    def test_reset_conversation_service(self):
        """Test the reset_conversation service function."""
        context = ConversationContext.objects.create(
            user_id=self.guest.whatsapp_number,
            hotel=self.hotel,
            is_active=True,
            navigation_stack=[1, 2, 3],
            context_data={'accumulated_data': {'key': 'value'}},
            error_count=3
        )
        
        reset_conversation(context)
        
        context.refresh_from_db()
        self.assertTrue(context.is_active)
        self.assertEqual(context.navigation_stack, [])
        self.assertEqual(context.context_data.get('accumulated_data'), {})
        self.assertEqual(context.error_count, 0)

    def test_cleanup_inactive_contexts_command(self):
        """Test the cleanup_inactive_contexts management command."""
        # Active context - should not be deleted
        ConversationContext.objects.create(user_id="active_user", hotel=self.hotel)
        
        # Stale context - should be deleted
        stale_context = ConversationContext.objects.create(user_id="stale_user", hotel=self.hotel)
        ConversationContext.objects.filter(pk=stale_context.pk).update(last_activity=timezone.now() - timedelta(days=10))
        
        call_command('cleanup_inactive_contexts')
        
        self.assertTrue(ConversationContext.objects.filter(user_id="active_user").exists())
        self.assertFalse(ConversationContext.objects.filter(user_id="stale_user").exists())

    def test_cascade_delete_on_flow_step(self):
        """Test that deleting a FlowStep deletes the ConversationContext."""
        context = ConversationContext.objects.create(user_id=self.guest.whatsapp_number, hotel=self.hotel)
        flow_step = FlowStep.objects.create(hotel=self.hotel, template=self.step_a)
        context.current_step = flow_step
        context.save()
        
        self.assertTrue(ConversationContext.objects.filter(id=context.id).exists())
        
        # Deleting the flow_step should cascade and delete the context
        flow_step.delete()
        
        self.assertFalse(ConversationContext.objects.filter(id=context.id).exists())
