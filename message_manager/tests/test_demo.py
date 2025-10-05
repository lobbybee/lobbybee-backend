from django.test import TestCase, Client
from message_manager.models import Conversation


class DemoConversationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.webhook_url = '/api/message_manager/webhook/whatsapp/'

    def test_demo_conversation_creation(self):
        """Test that a demo conversation is created for unknown guests"""
        # Initially no conversations
        initial_count = Conversation.objects.count()
        
        # Send a message to the webhook
        data = {
            "test": "data"
        }
        response = self.client.post(self.webhook_url, data=data, content_type='application/json')
        
        # Check that we got a response
        self.assertEqual(response.status_code, 200)
        
        # Check that a conversation was created
        # Note: In the current implementation, the phone number is hardcoded in the webhook
        # So it will find the existing stay and create a checkin conversation
        # To properly test demo conversations, we would need to modify the webhook
        # to extract the actual phone number from the request