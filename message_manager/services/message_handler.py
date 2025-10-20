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
        self.DEPARTMENT_MAPPING = {
            'reception': 'Reception',
            'housekeeping': 'Housekeeping',
            'room_service': 'Room Service',
            'cafe': 'Café',
            'management': 'Management',
        }

    def process_message(self, phone_number, message_content, department=None):
        print("Inside process_message")
        logger.debug(f"Processing message from phone_number: {phone_number}, content: {message_content}, department: {department}")

        # Find or create conversation
        conversation = self.get_or_create_conversation(phone_number)
        logger.debug(f"Conversation retrieved/created: id={conversation.id}, status={conversation.status}, current_step={conversation.current_step}")

        # Set department (optional, defaults to None if not provided)
        conversation.department = department

        # Ensure the conversation is saved to the database
        conversation.save()
        # Refresh from DB to ensure synchronization (fixes potential staleness issues)
        conversation.refresh_from_db()
        logger.debug(f"Conversation after save/refresh: id={conversation.id}, pk={conversation.pk}, stay_id={conversation.stay.id if conversation.stay else None}")

        # Check if conversation requires a stay but none exists
        if conversation.status in ['checkin', 'active'] and not conversation.stay:
            logger.debug(f"No active stay found for conversation {conversation.id} with status {conversation.status}")
            return {"message": "No active stay found. Please contact reception."}

        # Save incoming message
        try:
            Message.objects.create(
                conversation_id=conversation.pk,
                content=message_content,
                sender_type='guest'
            )
            logger.debug(f"Guest message saved to conversation {conversation.id}")
        except Exception as e:
            logger.error(f"Error saving guest message: {str(e)} - Conversation details: id={conversation.id}, pk={conversation.pk}, stay_id={conversation.stay.id if conversation.stay else None}")
            return {"status": "error"}

        # If in relay mode, forward to department
        if conversation.status == 'relay':
            logger.debug(f"Conversation {conversation.id} is in relay mode, handling relay message")
            return self.handle_relay_message(conversation, message_content)

        # Process with flow logic
        logger.debug(f"Processing flow step for conversation {conversation.id}")
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

            try:
                conversation, created = Conversation.objects.get_or_create(
                    stay=stay,
                    defaults={'status': self.determine_initial_status(stay)}
                )
                return conversation
            except Exception as e:
                logger.error(f"Failed to get or create conversation for stay {stay.id}: {str(e)}")
                return self.create_demo_conversation(phone_number)

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
                # Extract department type from step name for relay actions
                department_type = None
                if 'start_relay_' in conversation.current_step:
                    department_type = conversation.current_step.replace('start_relay_', '')
                elif 'demo_' in conversation.current_step:
                    department_type = conversation.current_step.replace('demo_', '')
                
                # Map to title-case for consistency with user model
                department_type = self.DEPARTMENT_MAPPING.get(department_type, department_type)

                result = action_func(conversation, message_content, department_type)
                if 'next_step' in result:
                    next_step = result['next_step']

        # Update conversation
        conversation.current_step = next_step
        try:
            conversation.save()
        except Exception as e:
            logger.error(f"Error saving conversation in process_flow_step: {str(e)}")

        # Get next message
        next_step_data = flow.get(next_step, flow['start'])
        message = next_step_data.get('message', '...')
        message = str(message)  # Ensure message is a string to prevent AttributeError

        # Replace placeholders
        if '{hotel_name}' in message and hasattr(conversation, 'stay') and conversation.stay:
            message = message.replace('{hotel_name}', conversation.stay.hotel.name)

        return {"message": message}

    def handle_relay_message(self, conversation, message_content):
        # In a real implementation, this would forward the message to the department
        # For now, we'll just log it
        department = getattr(conversation, 'department', 'unknown')
        logger.info(f"Relaying message to department {department}: {message_content}")
        return {"status": "relayed"}
