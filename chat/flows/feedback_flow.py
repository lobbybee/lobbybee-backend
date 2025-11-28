import logging
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class FeedbackStep:
    """Constants for feedback flow steps."""
    INITIAL = 0
    RATING = 1
    NOTE_OPTION = 2
    NOTE_INPUT = 3
    GOOGLE_REVIEW = 4
    COMPLETED = 5


def process_feedback_flow(guest=None, hotel_id=None, conversation=None, flow_data=None, stay_id=None):
    """
    Process feedback flow messages.

    Args:
        guest: Guest object
        hotel_id: Hotel ID from command
        conversation: Conversation object (for continuing flows)
        flow_data: WhatsApp message data dict
        stay_id: Stay ID for which feedback is being given

    Returns:
        dict: Response object to send back
    """

    # Extract data from flow_data
    message_text = flow_data.get('message', '') if flow_data else ''
    message_id = flow_data.get('message_id') if flow_data else None
    media_id = flow_data.get('media_id') if flow_data and flow_data.get('message_type') != 'text' else None
    logger.info(f"Received feedback message: {message_text}")

    # Step handler pattern
    step_handlers = {
        FeedbackStep.INITIAL: handle_initial_step,
        FeedbackStep.RATING: handle_rating_step,
        FeedbackStep.NOTE_OPTION: handle_note_option_step,
        FeedbackStep.NOTE_INPUT: handle_note_input_step,
        FeedbackStep.GOOGLE_REVIEW: handle_google_review_step,
    }

    # Handle fresh feedback command
    if not conversation:
        return handle_fresh_feedback_command(guest, hotel_id, flow_data, stay_id)

    # For continuing flows, determine current step
    # Get the last SYSTEM flow message to determine current step
    last_flow_message = conversation.messages.filter(
        is_flow=True,
        sender_type='staff'
    ).order_by('-created_at').first()

    if last_flow_message is None:
        current_step = FeedbackStep.INITIAL
    else:
        current_step = last_flow_message.flow_step

    logger.info(f"Processing feedback step: {current_step}")

    # Save incoming guest message
    save_guest_message(conversation, message_text, message_id, media_id, current_step)

    # Get appropriate step handler
    handler = step_handlers.get(current_step, handle_unknown_step)

    return handler(conversation, guest, message_text, flow_data)


def handle_fresh_feedback_command(guest, hotel_id, flow_data, stay_id):
    """Handle fresh /feedback-{hotel_id} command."""
    from hotel.models import Hotel
    from chat.models import Conversation

    # Validate hotel
    try:
        hotel = Hotel.objects.get(id=hotel_id, is_active=True, status='verified')
    except Hotel.DoesNotExist:
        return {
            "type": "text",
            "text": "Invalid hotel code. Please try again."
        }

    # Validate stay exists for this guest and hotel
    from guest.models import Stay
    try:
        stay = Stay.objects.get(id=stay_id, guest=guest, hotel=hotel)
    except Stay.DoesNotExist:
        return {
            "type": "text",
            "text": "Invalid stay reference. Please contact the reception."
        }

    # Check if feedback already exists for this stay
    from guest.models import Feedback
    if Feedback.objects.filter(stay=stay).exists():
        return {
            "type": "text",
            "text": "You have already provided feedback for this stay. Thank you!"
        }

    # Archive any existing active feedback conversations
    Conversation.objects.filter(
        guest=guest,
        hotel=hotel,
        conversation_type='feedback',
        status='active'
    ).update(status='archived')

    # Create new feedback conversation
    with transaction.atomic():
        conversation = Conversation.objects.create(
            guest=guest,
            hotel=hotel,
            department='Reception',
            conversation_type='feedback',
            status='active'
        )

        # Start with initial step
        return handle_initial_step(conversation, guest, flow_data)


def handle_unknown_step(conversation, guest, message_text, flow_data):
    """Handle unknown step."""
    return {
        "type": "text",
        "text": "Something went wrong. Please start again with /feedback-{hotel_id}-{stay_id}"
    }


def save_guest_message(conversation, message_text, message_id, media_id, flow_step):
    """Save incoming guest message."""
    from chat.models import Message

    Message.objects.create(
        conversation=conversation,
        sender_type='guest',
        message_type='text',
        content=message_text,
        whatsapp_message_id=message_id,
        is_flow=True,
        flow_id='feedback',
        flow_step=flow_step
    )

    conversation.update_last_message(message_text)


def save_system_message(conversation, content, flow_step, is_success=True):
    """Save system/bot response message."""
    from chat.models import Message

    Message.objects.create(
        conversation=conversation,
        sender_type='staff',
        message_type='system',
        content=content,
        is_flow=True,
        flow_id='feedback',
        flow_step=flow_step,
        is_flow_step_success=is_success
    )


def handle_initial_step(conversation, guest, message_text, flow_data):
    """Initial step - show rating selection."""
    
    header_text = f"How was your stay at {conversation.hotel.name}?"
    body_text = "We'd love to hear about your experience! Please rate your stay from 1 to 5 stars."
    
    save_system_message(conversation, f"{header_text}\n\n{body_text}", FeedbackStep.RATING)

    return {
        "type": "button",
        "text": header_text,
        "body_text": body_text,
        "options": [
            {"id": "rating_1", "title": "⭐"},
            {"id": "rating_2", "title": "⭐⭐"},
            {"id": "rating_3", "title": "⭐⭐⭐"},
            {"id": "rating_4", "title": "⭐⭐⭐⭐"},
            {"id": "rating_5", "title": "⭐⭐⭐⭐⭐"}
        ]
    }


def handle_rating_step(conversation, guest, message_text, flow_data):
    """Process rating selection and determine next step."""
    
    # Extract rating from message
    rating = None
    error_msg = None
    
    # Handle button responses
    if message_text.startswith('rating_'):
        try:
            rating = int(message_text.split('_')[1])
            if rating < 1 or rating > 5:
                error_msg = "Please select a rating from 1 to 5."
        except (ValueError, IndexError):
            error_msg = "Invalid rating selection."
    else:
        # Handle text responses
        try:
            rating = int(message_text.strip())
            if rating < 1 or rating > 5:
                error_msg = "Please enter a rating from 1 to 5."
        except ValueError:
            error_msg = "Please enter a valid number from 1 to 5."
    
    if error_msg or rating is None:
        save_system_message(conversation, error_msg or "Invalid rating. Please select from 1 to 5.", FeedbackStep.RATING, is_success=False)
        
        header_text = "How was your stay?"
        body_text = "Please rate your stay from 1 to 5 stars."
        
        return {
            "type": "button",
            "text": header_text,
            "body_text": body_text,
            "options": [
                {"id": "rating_1", "title": "⭐"},
                {"id": "rating_2", "title": "⭐⭐"},
                {"id": "rating_3", "title": "⭐⭐⭐"},
                {"id": "rating_4", "title": "⭐⭐⭐⭐"},
                {"id": "rating_5", "title": "⭐⭐⭐⭐⭐"}
            ]
        }
    
    # Store rating in flow data
    flow_data['rating'] = rating
    
    # Create feedback record with rating
    from guest.models import Feedback, Stay
    stay = Stay.objects.filter(guest=guest, hotel=conversation.hotel, status='completed').order_by('-check_out_date').first()
    
    if stay:
        Feedback.objects.create(
            stay=stay,
            guest=guest,
            rating=rating,
            note=""
        )
    
    # Determine next step based on rating
    if rating >= 3:
        return handle_high_rating_flow(conversation, guest, flow_data, rating)
    else:
        return handle_low_rating_flow(conversation, guest, flow_data, rating)


def handle_high_rating_flow(conversation, guest, flow_data, rating):
    """Handle high rating flow for ratings >= 3."""
    
    rating_text = ""
    if rating == 3:
        rating_text = "Good! ⭐⭐⭐"
    elif rating == 4:
        rating_text = "Very Good! ⭐⭐⭐⭐"
    elif rating == 5:
        rating_text = "Excellent! ⭐⭐⭐⭐⭐"
    
    # Check if hotel has Google review link
    google_link = conversation.hotel.google_review_link
    
    if google_link:
        header_text = "Thank you for your positive feedback!"
        body_text = f"{rating_text}\n\nWe're glad you enjoyed your stay! If you have a moment, we'd really appreciate it if you could share your experience on Google Reviews.\n\nWould you like to add any additional notes about your stay?"
        
        save_system_message(conversation, f"{header_text}\n\n{body_text}", FeedbackStep.NOTE_OPTION)
        
        return {
            "type": "button",
            "text": header_text,
            "body_text": body_text,
            "options": [
                {"id": "add_note", "title": "📝 Add Note"},
                {"id": "skip_note", "title": "⏭️ Skip"}
            ]
        }
    else:
        # No Google review link, just ask for notes
        header_text = "Thank you for your positive feedback!"
        body_text = f"{rating_text}\n\nWe're glad you enjoyed your stay! Would you like to add any additional notes about your stay?"
        
        save_system_message(conversation, f"{header_text}\n\n{body_text}", FeedbackStep.NOTE_OPTION)
        
        return {
            "type": "button",
            "text": header_text,
            "body_text": body_text,
            "options": [
                {"id": "add_note", "title": "📝 Add Note"},
                {"id": "skip_note", "title": "⏭️ Skip"}
            ]
        }


def handle_low_rating_flow(conversation, guest, flow_data, rating):
    """Handle low rating flow for ratings < 3."""
    
    rating_text = ""
    if rating == 1:
        rating_text = "We're very sorry to hear that. ⭐"
    elif rating == 2:
        rating_text = "We're sorry to hear that. ⭐⭐"
    
    header_text = rating_text
    body_text = "We're sorry that your experience didn't meet your expectations. We value your feedback and would like to understand what we can do to improve.\n\nWould you like to share more details about your experience?"
    
    save_system_message(conversation, f"{header_text}\n\n{body_text}", FeedbackStep.NOTE_OPTION)
    
    return {
        "type": "button",
        "text": header_text,
        "body_text": body_text,
        "options": [
            {"id": "add_note", "title": "📝 Add Note"},
            {"id": "skip_note", "title": "⏭️ Skip"}
        ]
    }


def handle_note_option_step(conversation, guest, message_text, flow_data):
    """Handle note option selection."""
    
    # Get rating from database since flow_data is not persisted between steps
    from guest.models import Feedback, Stay
    rating = None
    
    try:
        stay = Stay.objects.filter(guest=guest, hotel=conversation.hotel, status='completed').order_by('-check_out_date').first()
        if stay:
            feedback = Feedback.objects.filter(stay=stay, guest=guest).first()
            if feedback:
                rating = feedback.rating
    except Exception as e:
        logger.error(f"Error retrieving rating from database: {e}")
        rating = None
    
    if message_text in ['add_note', 'btn_0']:
        # Guest wants to add a note
        if rating is None:
            # Fallback in case rating couldn't be retrieved
            rating = 3  # Default to neutral rating
        
        if rating >= 3:
            if conversation.hotel.google_review_link:
                header_text = "Share your experience"
                body_text = "Please tell us more about your stay. Your feedback helps us improve our service!\n\nAlso, don't forget to rate us on Google Reviews! 😊"
            else:
                header_text = "Share your experience"
                body_text = "Please tell us more about your stay. Your feedback helps us improve our service!"
        else:
            header_text = "Help us improve"
            body_text = "We're sorry your experience wasn't perfect. Please let us know what we could have done better. Your feedback is important to us and will help us improve."
        
        save_system_message(conversation, f"{header_text}\n\n{body_text}", FeedbackStep.NOTE_INPUT)
        
        return {
            "type": "text",
            "text": f"{header_text}\n\n{body_text}"
        }
    
    elif message_text in ['skip_note', 'btn_1']:
        # Guest wants to skip note
        return complete_feedback_flow(conversation, guest)
    
    else:
        # Invalid selection
        save_system_message(conversation, "Please select a valid option.", FeedbackStep.NOTE_OPTION, is_success=False)
        
        return {
            "type": "button",
            "text": "Add Note?",
            "body_text": "Would you like to add any additional notes?",
            "options": [
                {"id": "add_note", "title": "📝 Add Note"},
                {"id": "skip_note", "title": "⏭️ Skip"}
            ]
        }


def handle_note_input_step(conversation, guest, message_text, flow_data):
    """Handle note input from guest."""
    
    note = message_text.strip()
    
    # Get rating from database since flow_data is not persisted between steps
    from guest.models import Feedback, Stay
    rating = None
    
    try:
        stay = Stay.objects.filter(guest=guest, hotel=conversation.hotel, status='completed').order_by('-check_out_date').first()
        if stay:
            feedback = Feedback.objects.filter(stay=stay, guest=guest).first()
            if feedback:
                rating = feedback.rating
    except Exception as e:
        logger.error(f"Error retrieving rating from database: {e}")
        rating = None
    
    if not note:
        save_system_message(conversation, "Please enter a note or type 'skip' to continue.", FeedbackStep.NOTE_INPUT, is_success=False)
        return {
            "type": "text",
            "text": "Please enter a note or type 'skip' to continue."
        }
    
    # Update feedback record with note
    from guest.models import Feedback, Stay
    try:
        stay = Stay.objects.filter(guest=guest, hotel=conversation.hotel, status='completed').order_by('-check_out_date').first()
        if stay:
            feedback = Feedback.objects.get(stay=stay, guest=guest)
            feedback.note = note
            feedback.save()
    except Feedback.DoesNotExist:
        logger.error(f"Feedback record not found for guest {guest.id}")
    
    # If rating >= 3 and hotel has Google review link, show it
    if rating is None:
        # Fallback in case rating couldn't be retrieved
        rating = 3  # Default to neutral rating
    
    if rating >= 3 and conversation.hotel.google_review_link:
        header_text = "Thank you for your detailed feedback!"
        body_text = f"We appreciate you taking the time to share your experience.\n\n🌟 Please also consider leaving a Google Review:\n{conversation.hotel.google_review_link}\n\nYour feedback helps us improve and helps other guests make informed decisions!"
        
        save_system_message(conversation, f"{header_text}\n\n{body_text}", FeedbackStep.GOOGLE_REVIEW)
        
        return {
            "type": "text",
            "text": f"{header_text}\n\n{body_text}"
        }
    else:
        # Complete the flow
        return complete_feedback_flow(conversation, guest)


def handle_google_review_step(conversation, guest, message_text, flow_data):
    """Handle Google review step (this is mostly informational)."""
    
    # Any response here just completes the flow
    return complete_feedback_flow(conversation, guest)


def complete_feedback_flow(conversation, guest):
    """Complete the feedback flow."""
    try:
        # Update conversation
        conversation.status = 'closed'
        conversation.save(update_fields=['status'])
        
        header_text = "Thank you for your feedback!"
        body_text = f"We appreciate you taking the time to share your experience with us. Your feedback is valuable in helping us improve our services.\n\nWe hope to welcome you back to {conversation.hotel.name} again soon!\n\nHave a great day! 🌟"
        
        save_system_message(conversation, f"{header_text}\n\n{body_text}", FeedbackStep.COMPLETED)
        
        return {
            "type": "text",
            "text": f"{header_text}\n\n{body_text}"
        }
        
    except Exception as e:
        logger.error(f"Error completing feedback flow: {e}")
        error_text = "There was an error processing your feedback. Please contact the reception desk for assistance."
        save_system_message(conversation, error_text, FeedbackStep.COMPLETED, is_success=False)
        return {
            "type": "text",
            "text": error_text
        }