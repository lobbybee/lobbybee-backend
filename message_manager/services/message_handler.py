from .flow_definitions import DEMO_FLOW, CHECKIN_FLOW, SERVICES_FLOW
from .actions import *
from guest.models import Stay, Guest
from ..models import Conversation, Message

import logging
logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self):
        self.flows = {
            'demo': DEMO_FLOW,
            'checkin': CHECKIN_FLOW,
            'active': SERVICES_FLOW
        }

    def process_message(self, phone_number, message_content):
        # Find or create conversation
        conversation = self.get_or_create_conversation(phone_number)

        # Save incoming message
        Message.objects.create(
            conversation=conversation,
            content=message_content,
            sender_type='guest'
        )

        # If in relay mode, forward to department
        if conversation.status == 'relay':
            return self.handle_relay_message(conversation, message_content)

        # Process with flow logic
        return self.process_flow_step(conversation, message_content)

    def get_or_create_conversation(self, phone_number):
        try:
            guest = Guest.objects.get(whatsapp_number=phone_number)
            # Find most recent active stay
            stay = Stay.objects.filter(
                guest=guest,
                status__in=['pending', 'active']
            ).order_by('-created_at').first()

            if not stay:
                # Create demo conversation for non-guests
                return self.create_demo_conversation(phone_number)

            conversation, created = Conversation.objects.get_or_create(
                stay=stay,
                defaults={'status': self.determine_initial_status(stay)}
            )
            return conversation

        except Guest.DoesNotExist:
            return self.create_demo_conversation(phone_number)

    def determine_initial_status(self, stay):
        if stay.status == 'pending':
            return 'checkin'
        elif stay.status == 'active':
            return 'active'
        return 'demo'

    def create_demo_conversation(self, phone_number):
        # Check if a demo conversation already exists for this phone number
        try:
            conversation = Conversation.objects.get(
                stay=None,
                context_data__phone_number=phone_number
            )
            return conversation
        except Conversation.DoesNotExist:
            # Create a new demo conversation
            conversation = Conversation.objects.create(
                stay=None,  # Demo conversations don't have a stay
                status='demo',
                context_data={'phone_number': phone_number}
            )
            return conversation

    def process_flow_step(self, conversation, message_content):
        # Get current flow
        flow = self.flows.get(conversation.status, DEMO_FLOW)
        current_step = flow.get(conversation.current_step, flow['start'])
        
        # Check for triggers
        next_step = current_step.get('default_next', 'start')
        if 'next_triggers' in current_step:
            for trigger, target in current_step['next_triggers'].items():
                if trigger.lower() in message_content.lower():
                    next_step = target
                    break
        
        # Execute action if defined
        if 'action' in current_step:
            action_name = current_step['action']
            # Import and call action function dynamically
            if action_name in globals():
                action_func = globals()[action_name]
                result = action_func(conversation, message_content)
                if 'next_step' in result:
                    next_step = result['next_step']
        
        # Update conversation
        conversation.current_step = next_step
        conversation.save()
        
        # Get next message
        next_step_data = flow.get(next_step, flow['start'])
        message = next_step_data.get('message', '...')
        
        # Replace placeholders
        if '{hotel_name}' in message and hasattr(conversation, 'stay') and conversation.stay:
            message = message.replace('{hotel_name}', conversation.stay.hotel.name)
            
        return {"message": message}

    def handle_relay_message(self, conversation, message_content):
        # In a real implementation, this would forward the message to the department
        # For now, we'll just log it
        logger.info(f"Relaying message to department {conversation.department}: {message_content}")
        return {"status": "relayed"}