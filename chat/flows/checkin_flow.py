# flows/checkin_flow.py

import logging
from django.utils import timezone
from django.db import transaction
import re
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Import WhatsApp media download function
from ..utils.whatsapp_utils import download_whatsapp_media


class CheckinStep:
    """Constants for check-in flow steps."""
    INITIAL = 0
    NATIONALITY = 1  # Collect nationality first
    ID_TYPE = 2  # Then ID type selection
    ID_UPLOAD = 3  # ID upload steps
    ID_BACK_UPLOAD = 4
    NAME = 5  # Manual data collection steps (only if needed after ID processing)
    EMAIL = 6
    DOB = 7
    AADHAR_CONFIRMATION = 8  # After ID_BACK_UPLOAD for AADHAR
    CONFIRMATION = 9
    COMPLETED = 10


# Document types supported - must match GuestIdentityDocument.DOCUMENT_TYPES
DOCUMENT_TYPES = {
    'aadhar_id': 'AADHAR',
    'driving_license': 'License',
    'national_id': 'National ID',
    'voter_id': 'Voter ID',
    'other': 'Other Govt ID'
}


# Validation helper functions
def validate_name(name):
    """Validate guest name."""
    name = name.strip()
    if len(name) < 2:
        return False, "Please provide a valid name (at least 2 characters):"
    return True, name


def validate_email(email):
    """Validate email address."""
    email = email.strip()
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Please provide a valid email address:"
    return True, email


def validate_dob(dob_text):
    """Validate date of birth and age."""
    dob_text = dob_text.strip()

    # Parse date - try multiple formats
    date_formats = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']
    parsed_date = None

    for date_format in date_formats:
        try:
            parsed_date = datetime.strptime(dob_text, date_format).date()
            break
        except ValueError:
            continue

    if not parsed_date:
        return False, None, "Please provide a valid date of birth in DD/MM/YYYY format:"

    # Basic age validation (must be at least 18)
    today = date.today()
    age = today.year - parsed_date.year - ((today.month, today.day) < (parsed_date.month, parsed_date.day))

    if age < 18:
        return False, None, "You must be at least 18 years old to check in. Please provide a valid date of birth:"

    return True, parsed_date, ""


def validate_nationality(nationality):
    """Validate nationality."""
    nationality = nationality.strip()
    if len(nationality) < 2:
        return False, "Please provide a valid nationality:"
    return True, nationality


def validate_id_type(id_type):
    """Validate ID document type."""

    # Handle WhatsApp interactive button responses (option_0, option_1, etc.)
    if id_type.startswith('option_'):
        try:
            option_index = int(id_type.split('_')[1])
            doc_type_keys = list(DOCUMENT_TYPES.keys())
            if 0 <= option_index < len(doc_type_keys):
                normalized = doc_type_keys[option_index]
                return True, normalized, ""
        except (ValueError, IndexError):
            pass

    # Original validation for text inputs
    normalized = id_type.strip().lower().replace(' ', '_')

    if normalized not in DOCUMENT_TYPES:
        return False, None, "Please select a valid ID document type from the list."

    return True, normalized, ""


# Helper functions for ID management
def get_id_upload_instructions(doc_type):
    """Get instructions for uploading ID document"""
    if doc_type == 'aadhar_id':
        return f"📸 Please upload a clear photo of your {DOCUMENT_TYPES[doc_type]}.\n\nFor best results:\n• Ensure good lighting\n• Place on a flat surface\n• All text should be clearly visible\n• Avoid glare and shadows\n• 📱 **IMPORTANT: Keep the QR code portion clear and visible**\n• Make sure the QR code is not blurry or cut off\n\nPlease upload the front side first (the side with the QR code)."

    else:
        return f"📸 Please upload a clear photo of your {DOCUMENT_TYPES[doc_type]}.\n\nFor best results:\n• Ensure good lighting\n• Place on a flat surface\n• All text should be clearly visible\n• Avoid glare and shadows\n\nPlease upload the front side first."


def get_id_back_upload_instructions(doc_type):
    """Get instructions for uploading back side of ID"""
    if doc_type == 'aadhar_id':
        return f"📸 Now please upload the back side of your {DOCUMENT_TYPES[doc_type]}.\n\nNote: Some AADHAR cards have QR codes on both sides - please ensure the QR code is clear and visible on this side too.\n\nIf your AADHAR doesn't have a QR code on the back, please upload the back side anyway for complete verification."

    else:
        return f"📸 Now please upload the back side of your {DOCUMENT_TYPES[doc_type]}."


def process_checkin_flow(guest=None, hotel_id=None, conversation=None, flow_data=None, is_fresh_checkin_command=False):
    """
    Process checkin flow messages.

    Args:
        guest: Guest object (can be None for new guests)
        hotel_id: Hotel ID from command
        conversation: Conversation object (for continuing flows)
        flow_data: WhatsApp message data dict
        is_fresh_checkin_command: Whether this is a fresh /checkin command

    Returns:
        dict: Response object to send back
    """

    # Extract data from flow_data
    message_text = flow_data.get('message', '') if flow_data else ''
    message_id = flow_data.get('message_id') if flow_data else None
    media_id = flow_data.get('media_id') if flow_data and flow_data.get('message_type') != 'text' else None
    logger.info(f"Received message: {message_text}")
    # Step handler pattern
    step_handlers = {
        CheckinStep.INITIAL: handle_initial_step,
        CheckinStep.NAME: handle_name_step,
        CheckinStep.EMAIL: handle_email_step,
        CheckinStep.DOB: handle_dob_step,
        CheckinStep.NATIONALITY: handle_nationality_step,
        CheckinStep.ID_TYPE: handle_id_type_step,
        CheckinStep.ID_UPLOAD: handle_id_upload_step,
        CheckinStep.ID_BACK_UPLOAD: handle_id_back_upload_step,
        CheckinStep.AADHAR_CONFIRMATION: handle_aadhar_confirmation_step,
        CheckinStep.CONFIRMATION: handle_confirmation_step,
    }

    # Handle fresh checkin command
    if is_fresh_checkin_command:
        return handle_fresh_checkin_command(guest, hotel_id, flow_data)

    # For continuing flows, determine current step
    if not conversation:
        return {
            "type": "text",
            "text": "No active conversation found. Please start again with /checkin-{hotel_id}"
        }

    # Get the last SYSTEM flow message to determine current step
    # This prevents getting stuck on guest image upload messages
    last_flow_message = conversation.messages.filter(
        is_flow=True,
        sender_type='staff'
    ).order_by('-created_at').first()

    if last_flow_message is None:
        current_step = CheckinStep.INITIAL
    else:
        current_step = last_flow_message.flow_step

    # Debug logging
    logger.info(f"DEBUG: Determined current_step={current_step} from last_system_message flow_step={last_flow_message.flow_step if last_flow_message else None}")
    logger.info(f"DEBUG: Processing message_type={flow_data.get('message_type')}, media_id={flow_data.get('media_id')}")

    # Save incoming guest message
    save_guest_message(conversation, message_text, message_id, media_id, current_step)

    # Get appropriate step handler
    handler = step_handlers.get(current_step, handle_unknown_step)

    return handler(conversation, guest, message_text, flow_data)


def handle_fresh_checkin_command(guest, hotel_id, flow_data):
    """Handle fresh /checkin-{hotel_id} command."""
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

    # Create guest if not exists
    if not guest:
        from guest.models import Guest
        whatsapp_number = flow_data.get('whatsapp_number')
        guest, created = Guest.objects.get_or_create(
            whatsapp_number=whatsapp_number,
            defaults={
                'status': 'pending_checkin',
                'is_whatsapp_active': True,
            }
        )
    else:
        created = False

    # Check if guest has completed stays before (returning guest)
    from guest.models import Stay
    has_completed_stays = Stay.objects.filter(
        guest=guest,
        status='completed'  # Successfully checked out
    ).exists()

    # If guest has completed stays, show confirmation of existing data
    # If new guest or no completed stays, clean up old incomplete data
    if has_completed_stays:
        # Returning guest - show data confirmation flow
        return handle_returning_guest_checkin(guest, hotel_id, flow_data)
    else:
        # New guest or only failed/incomplete checkins - clean up old data
        cleanup_incomplete_guest_data(guest)

        # Delete any existing pending stays for this guest
        from guest.models import Stay
        Stay.objects.filter(
            guest=guest,
            status='pending'
        ).delete()

    # Archive any existing active checkin conversations
    Conversation.objects.filter(
        guest=guest,
        hotel=hotel,
        conversation_type='checkin',
        status='active'
    ).update(status='archived')

    # Create new checkin conversation
    with transaction.atomic():
        conversation = Conversation.objects.create(
            guest=guest,
            hotel=hotel,
            department='Reception',
            conversation_type='checkin',
            status='active'
        )

        # Start with initial step
        return handle_initial_step(conversation, guest, flow_data.get('message', ''), flow_data)


def handle_returning_guest_checkin(guest, hotel_id, flow_data):
    """Handle check-in for returning guests with existing data."""
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

    # Archive any existing active checkin conversations
    Conversation.objects.filter(
        guest=guest,
        hotel=hotel,
        conversation_type='checkin',
        status='active'
    ).update(status='archived')

    # Create new checkin conversation
    with transaction.atomic():
        conversation = Conversation.objects.create(
            guest=guest,
            hotel=hotel,
            department='Reception',
            conversation_type='checkin',
            status='active'
        )

        # Show existing data confirmation
        return show_guest_data_confirmation(conversation, guest, flow_data)


def cleanup_incomplete_guest_data(guest):
    """Clean up incomplete guest data from failed check-ins."""
    from guest.models import GuestIdentityDocument, Booking

    # Delete incomplete bookings (pending or cancelled)
    Booking.objects.filter(
        primary_guest=guest,
        status__in=['pending', 'cancelled']
    ).delete()

    # Delete unverified identity documents
    GuestIdentityDocument.objects.filter(
        guest=guest,
        is_verified=False
    ).delete()

    # Reset guest to basic state
    guest.status = 'pending_checkin'
    guest.full_name = ''
    guest.email = ''
    guest.date_of_birth = None
    guest.nationality = ''
    guest.save(update_fields=['status', 'full_name', 'email', 'date_of_birth', 'nationality'])


def show_guest_data_confirmation(conversation, guest, flow_data):
    """Show existing guest data for confirmation."""

    # Build confirmation message with existing data
    response_text = "Welcome Back!"

    # Build the data display
    data_parts = []
    if guest.full_name:
        data_parts.append(f"Name: {guest.full_name}")
    if guest.email:
        data_parts.append(f"Email: {guest.email}")
    if guest.date_of_birth:
        data_parts.append(f"Date of Birth: {guest.date_of_birth.strftime('%d/%m/%Y')}")
    if guest.nationality:
        data_parts.append(f"Nationality: {guest.nationality}")

    if data_parts:
        body_text = "We found your previous information:\n\n" + "\n".join(data_parts) + "\n\nIs this information still correct? Reply 'yes' to confirm, or 'no' to update."
    else:
        body_text = "Welcome back! We'll need to collect your information for this check-in."

    save_system_message(conversation, f"{response_text}\n\n{body_text}", CheckinStep.INITIAL)

    return {
        "type": "text",
        "text": response_text,
        "body_text": body_text
    }


def handle_unknown_step(conversation, guest, message_text, flow_data):
    """Handle unknown step."""
    return {
        "type": "text",
        "text": "Something went wrong. Please start again with /checkin-{hotel_id}"
    }


def save_guest_message(conversation, message_text, message_id, media_id, flow_step):
    """Save incoming guest message."""
    from chat.models import Message

    Message.objects.create(
        conversation=conversation,
        sender_type='guest',
        message_type='text',  # Will handle media later
        content=message_text,
        whatsapp_message_id=message_id,
        is_flow=True,
        flow_id='checkin',
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
        flow_id='checkin',
        flow_step=flow_step,
        is_flow_step_success=is_success
    )


# Step handlers
def handle_initial_step(conversation, guest, message_text, flow_data):
    """Initial step - handle returning guest confirmation or start new check-in."""

    # Check if this is a response to returning guest data confirmation
    if message_text:
        response = message_text.strip().lower()

        # Check if guest is confirming existing data
        if response in ['yes', 'correct', 'confirm', '1', 'btn_0']:
            # Guest confirmed existing data - proceed with next steps
            # Check what information is missing and ask for it
            missing_info = []
            if not guest.full_name:
                missing_info.append('name')
            if not guest.email:
                missing_info.append('email')
            if not guest.date_of_birth:
                missing_info.append('date of birth')
            if not guest.nationality:
                missing_info.append('nationality')

            if missing_info:
                # Some info is missing, start collection from first missing item
                response_text = "Information Required"
                body_text = f"Great! We still need some information from you:\n\nMissing: {', '.join(missing_info).title()}\n\nLet's start with your {'nationality' if 'nationality' in missing_info else 'name' if 'name' in missing_info else 'email' if 'email' in missing_info else 'date of birth'}:"

                if 'nationality' in missing_info:
                    save_system_message(conversation, f"{response_text}\n\n{body_text}", CheckinStep.NATIONALITY)
                    return {"type": "text", "text": response_text, "body_text": body_text}
                elif 'name' in missing_info:
                    save_system_message(conversation, f"{response_text}\n\n{body_text}", CheckinStep.NAME)
                    return {"type": "text", "text": response_text, "body_text": body_text}
                elif 'email' in missing_info:
                    save_system_message(conversation, f"{response_text}\n\n{body_text}", CheckinStep.EMAIL)
                    return {"type": "text", "text": response_text, "body_text": body_text}
                else:
                    save_system_message(conversation, f"{response_text}\n\n{body_text}", CheckinStep.DOB)
                    return {"type": "text", "text": response_text, "body_text": body_text}
            else:
                # All info is present, proceed to ID upload
                header_text = "Select ID Document Type"
                body_text = "Perfect! We have all your information. Please select your government-issued ID document type from the list below to complete verification."
                save_system_message(conversation, f"{header_text}\n\n{body_text}", CheckinStep.ID_TYPE)

                return get_id_type_options_response(header_text, body_text)

        elif response in ['no', 'incorrect', 'update', '2', 'btn_1']:
            # Guest wants to update information - clear existing data and start fresh
            guest.full_name = ''
            guest.email = ''
            guest.date_of_birth = None
            guest.nationality = ''
            guest.save(update_fields=['full_name', 'email', 'date_of_birth', 'nationality'])

            response_text = "Information Update"
            body_text = "Let's collect your current information. Please start with your full name:"
            save_system_message(conversation, f"{response_text}\n\n{body_text}", CheckinStep.NAME)
            return {"type": "text", "text": response_text, "body_text": body_text}

    # Fresh check-in start - ask for nationality first

    response_text = f"Welcome to {conversation.hotel.name}! Let's get you checked in quickly. Please provide your nationality to begin the verification process. \n eg: Indian"
    save_system_message(conversation, f"{response_text}", CheckinStep.NATIONALITY)

    return {
        "type": "text",
        "text": response_text
    }


def handle_name_step(conversation, guest, message_text, flow_data):
    """Process name input and ask for email."""

    # Use validation helper
    is_valid, result = validate_name(message_text)

    if not is_valid:
        save_system_message(conversation, result, CheckinStep.NAME, is_success=False)
        return {
            "type": "text",
            "text": result
        }

    # Save name
    guest.full_name = result
    guest.save(update_fields=['full_name'])

    # Check if email exists, skip if yes
    if guest.email:
        response_text = f"Great! We have your email as {guest.email}.\n\nPlease provide your date of birth (DD/MM/YYYY):"
        save_system_message(conversation, response_text, CheckinStep.DOB)
        return {
            "type": "text",
            "text": response_text
        }

    response_text = "Thank you! Please provide your email address:"
    save_system_message(conversation, response_text, CheckinStep.EMAIL)

    return {
        "type": "text",
        "text": response_text
    }


def handle_email_step(conversation, guest, message_text, flow_data):
    """Process email input and ask for date of birth."""

    # Use validation helper
    is_valid, result = validate_email(message_text)

    if not is_valid:
        save_system_message(conversation, result, CheckinStep.EMAIL, is_success=False)
        return {
            "type": "text",
            "text": result
        }

    # Save email
    guest.email = result
    guest.save(update_fields=['email'])

    # Check if DOB exists
    if guest.date_of_birth:
        response_text = f"Thank you! We have your date of birth on record.\n\nPlease provide your nationality:"
        save_system_message(conversation, response_text, CheckinStep.NATIONALITY)
        return {
            "type": "text",
            "text": response_text
        }

    response_text = "Great! Please provide your date of birth (DD/MM/YYYY):"
    save_system_message(conversation, response_text, CheckinStep.DOB)

    return {
        "type": "text",
        "text": response_text
    }


def handle_dob_step(conversation, guest, message_text, flow_data):
    """Process date of birth and ask for nationality."""

    # Use validation helper
    is_valid, parsed_date, error_msg = validate_dob(message_text)

    if not is_valid:
        save_system_message(conversation, error_msg, CheckinStep.DOB, is_success=False)
        return {
            "type": "text",
            "text": error_msg
        }

    # Save DOB
    guest.date_of_birth = parsed_date
    guest.save(update_fields=['date_of_birth'])

    # Go directly to confirmation - show all collected info
    return show_confirmation_with_collected_data(conversation, guest, flow_data)


def handle_nationality_step(conversation, guest, message_text, flow_data):
    """Process nationality and ask for ID document type."""

    # Use validation helper
    is_valid, result = validate_nationality(message_text)

    if not is_valid:
        save_system_message(conversation, result, CheckinStep.NATIONALITY, is_success=False)
        return {
            "type": "text",
            "text": result
        }

    # Save nationality
    guest.nationality = result
    guest.save(update_fields=['nationality'])

    header_text = "Select ID Document Type"
    body_text = "Great! Please select your government-issued ID document type from the list below to complete your verification."
    save_system_message(conversation, f"{header_text}\n\n{body_text}", CheckinStep.ID_TYPE)

    return get_id_type_options_response(header_text, body_text)


def get_id_type_options_response(header_text, body_text=None):
    """Get standard ID type options response with proper header and body."""
    doc_type_keys = list(DOCUMENT_TYPES.keys())

    # Default body text if not provided
    if body_text is None:
        body_text = "Please select your government-issued ID document type from the list below. This is required for identity verification during the check-in process."

    return {
        "type": "list",
        "text": header_text,
        "body_text": body_text,
        "options": [
            {"id": f"option_{index}", "title": DOCUMENT_TYPES[doc_id]}
            for index, doc_id in enumerate(doc_type_keys)
        ]
    }


def handle_id_type_step(conversation, guest, message_text, flow_data):
    """Process ID type selection and ask for document upload."""

    # Use validation helper
    is_valid, id_type, error_msg = validate_id_type(message_text)

    if not is_valid:
        save_system_message(conversation, error_msg, CheckinStep.ID_TYPE, is_success=False)
        header_text = "Select ID Document Type"
        body_text = f"Invalid selection. {error_msg} Please select a valid ID document type from the list below."
        return get_id_type_options_response(header_text, body_text)

    # Store ID type in flow data
    flow_data['selected_id_type'] = id_type
    flow_data['document_name'] = DOCUMENT_TYPES[id_type]

    # Store ID type in document entry
    from guest.models import GuestIdentityDocument

    # Create or update document entry
    doc, created = GuestIdentityDocument.objects.get_or_create(
        guest=guest,
        is_primary=True,
        defaults={
            'document_type': id_type,
            'is_verified': False
        }
    )

    if not created:
        doc.document_type = id_type
        doc.save(update_fields=['document_type'])

    # Get upload instructions based on document type
    response_text = get_id_upload_instructions(id_type)
    save_system_message(conversation, response_text, CheckinStep.ID_UPLOAD)

    return {
        "type": "text",
        "text": response_text
    }


def handle_id_upload_step(conversation, guest, message_text, flow_data):
    """Handle ID document upload - downloads and stores front side."""

    # Check if this is media upload
    media_id = flow_data.get('media_id') if flow_data.get('message_type') != 'text' else None

    if not media_id:
        # No media uploaded - ask again
        response_text = "Please upload an image of your ID document."
        save_system_message(conversation, response_text, CheckinStep.ID_UPLOAD, is_success=False)
        return {
            "type": "text",
            "text": response_text
        }

    try:
        logger.info(f"Processing ID upload for guest {guest.id}, media_id: {media_id}")

        # Download the media
        media_data = download_whatsapp_media(media_id)
        logger.info(f"Media download result: {media_data is not None}")

        if not media_data or not media_data.get('content'):
            logger.error(f"Media download failed or no content. media_data: {media_data}")
            response_text = "Failed to download your ID image. Please try uploading again."
            save_system_message(conversation, response_text, CheckinStep.ID_UPLOAD, is_success=False)
            return {
                "type": "text",
                "text": response_text
            }

        # Store the front image data in flow_data
        flow_data['id_front_image'] = media_data['content']
        flow_data['id_front_filename'] = media_data['filename']
        logger.info(f"Stored media in flow_data, filename: {media_data['filename']}, size: {len(media_data['content'])} bytes")

        # Save the image to the guest's document entry
        from guest.models import GuestIdentityDocument
        from django.core.files.base import ContentFile

        logger.info(f"Looking for GuestIdentityDocument for guest {guest.id}, is_primary=True")
        doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)
        logger.info(f"Found document: {doc.id}, type: {doc.document_type}, current file: {doc.document_file}")

        doc.document_file.save(media_data['filename'], ContentFile(media_data['content']), save=True)
        doc.save()
        logger.info(f"Successfully saved document file for guest {guest.id}")

        # Get selected_id_type from GuestIdentityDocument instead of flow_data
        try:
            from guest.models import GuestIdentityDocument
            doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)
            selected_id_type = doc.document_type
            logger.info(f"Retrieved selected_id_type from document: {selected_id_type}")
        except GuestIdentityDocument.DoesNotExist:
            selected_id_type = 'aadhar_id'  # Default fallback
            logger.warning(f"No document found for guest {guest.id}, using default: {selected_id_type}")

        # Ask for back upload
        response_text = get_id_back_upload_instructions(selected_id_type)
        save_system_message(conversation, response_text, CheckinStep.ID_BACK_UPLOAD)
        return {
            "type": "text",
            "text": response_text
        }

    except GuestIdentityDocument.DoesNotExist as e:
        logger.error(f"GuestIdentityDocument not found for guest {guest.id}: {e}")
        response_text = "Document record not found. Please restart the check-in process."
        save_system_message(conversation, response_text, CheckinStep.ID_UPLOAD, is_success=False)
        return {
            "type": "text",
            "text": response_text
        }
    except Exception as e:
        logger.error(f"Error processing ID upload: {e}", exc_info=True)
        response_text = "Error processing your ID image. Please try uploading again."
        save_system_message(conversation, response_text, CheckinStep.ID_UPLOAD, is_success=False)
        return {
            "type": "text",
            "text": response_text
        }


def handle_id_back_upload_step(conversation, guest, message_text, flow_data):
    """Handle back side ID document upload."""
    logger.info(f"DEBUG: Entering handle_id_back_upload_step for guest {guest.id}")

    # Check if this is media upload
    media_id = flow_data.get('media_id') if flow_data.get('message_type') != 'text' else None

    if not media_id:
        response_text = "Please upload an image of the back side of your ID or type 'continue'."
        save_system_message(conversation, response_text, CheckinStep.ID_BACK_UPLOAD, is_success=False)
        return {
            "type": "text",
            "text": response_text
        }

    try:
        # Download the media
        media_data = download_whatsapp_media(media_id)

        if not media_data or not media_data.get('content'):
            response_text = "Failed to download your ID image. Please try uploading again."
            save_system_message(conversation, response_text, CheckinStep.ID_BACK_UPLOAD, is_success=False)
            return {
                "type": "text",
                "text": response_text
            }

        # Store the back image data
        flow_data['id_back_image'] = media_data['content']
        flow_data['id_back_filename'] = media_data['filename']

        # Save the image to the guest's document entry
        from guest.models import GuestIdentityDocument
        from django.core.files.base import ContentFile

        doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)
        doc.document_file_back.save(media_data['filename'], ContentFile(media_data['content']), save=True)
        doc.save()

        return process_id_verification(conversation, guest, flow_data)

    except Exception as e:
        logger.error(f"Error processing ID back upload: {e}")
        response_text = "Error processing your ID image. Please try uploading again."
        save_system_message(conversation, response_text, CheckinStep.ID_BACK_UPLOAD, is_success=False)
        return {
            "type": "text",
            "text": response_text
        }


def process_id_verification(conversation, guest, flow_data):
    """Process ID verification based on document type."""
    logger.info(f"DEBUG: Entering process_id_verification for guest {guest.id}")

    # Get selected_id_type from GuestIdentityDocument instead of flow_data
    try:
        from guest.models import GuestIdentityDocument
        doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)
        selected_id_type = doc.document_type
        logger.info(f"Retrieved selected_id_type from document in process_id_verification: {selected_id_type}")
    except GuestIdentityDocument.DoesNotExist:
        selected_id_type = 'aadhar_id'  # Default fallback
        logger.warning(f"No document found for guest {guest.id}, using default: {selected_id_type}")

    if selected_id_type == 'aadhar_id':
        logger.info(f"DEBUG: Calling process_aadhar_verification for AADHAR")
        return process_aadhar_verification(conversation, guest, flow_data)
    else:
        # For non-AADHAR IDs, redirect to NAME step for manual information collection
        response_text = f"📝 For {DOCUMENT_TYPES[selected_id_type]} verification, I need to collect some details manually.\n\nLet's start with your full name as shown on your ID:"
        save_system_message(conversation, response_text, CheckinStep.NAME)
        return {
            "type": "text",
            "text": response_text
        }





def handle_aadhar_confirmation_step(conversation, guest, message_text, flow_data):
    """Handle AADHAR confirmation response."""

    response = message_text.strip().lower()

    # Handle both text responses and button responses (btn_0, btn_1)
    if response in ['yes', 'correct', 'confirm', '1', 'btn_0']:
        # Extracted info is correct - data already saved
        logger.info(f"User confirmed AADHAR data with response '{response}', completing check-in for guest {guest.id}")

        response_text = f"""✅ Thank you for confirming your information!

Dear {guest.full_name}, our receptionist will validate your information and assign you a room shortly.

Welcome to {conversation.hotel.name}! 🏨"""

        save_system_message(conversation, response_text, CheckinStep.COMPLETED)
        return {
            "type": "text",
            "text": response_text
        }

    elif response in ['no', 'incorrect', 'modify', '2', 'btn_1']:
        # User wants to correct - redirect to NAME step for manual input
        logger.info(f"User wants to correct AADHAR data with response '{response}', redirecting to NAME step")
        response_text = "📝 Let's collect your details manually. Please start with your full name as shown on your ID:"
        save_system_message(conversation, response_text, CheckinStep.NAME)
        return {
            "type": "text",
            "text": response_text
        }

    else:
        # Invalid response - show confirmation again
        logger.info(f"Invalid response '{response}', showing AADHAR confirmation again")
        return show_aadhar_confirmation(conversation, guest, flow_data)


def process_aadhar_verification(conversation, guest, flow_data):
    """Process AADHAR verification after both sides are uploaded."""
    from ..utils.adhaar import decode_aadhaar_qr_from_image

    # Load images from database instead of flow_data (more reliable)
    try:
        from guest.models import GuestIdentityDocument
        doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)

        # Read front image from database
        front_image_data = None
        if doc.document_file:
            with doc.document_file.open('rb') as f:
                front_image_data = f.read()

        # Read back image from database (just saved)
        back_image_data = None
        if doc.document_file_back:
            with doc.document_file_back.open('rb') as f:
                back_image_data = f.read()

        logger.info(f"DEBUG: Front image loaded from database: {front_image_data is not None}")
        logger.info(f"DEBUG: Back image loaded from database: {back_image_data is not None}")

        if not front_image_data:
            response_text = "Front side image is required for AADHAR verification."
            save_system_message(conversation, response_text, CheckinStep.ID_UPLOAD, is_success=False)
            return {
                "type": "text",
                "text": response_text
            }

    except GuestIdentityDocument.DoesNotExist:
        response_text = "Document record not found. Please restart the check-in process."
        save_system_message(conversation, response_text, CheckinStep.ID_UPLOAD, is_success=False)
        return {
            "type": "text",
            "text": response_text
        }

    try:
        # Try to extract QR data from front side first
        front_result = decode_aadhaar_qr_from_image(front_image_data)
        if front_result:
            formatted_data = format_aadhar_data_for_display(front_result)
            flow_data["extracted_aadhar_info"] = formatted_data

            # Save extracted data to Guest immediately (can be overwritten later)
            if 'name' in formatted_data:
                guest.full_name = formatted_data['name']
            if 'dob' in formatted_data:
                from datetime import datetime
                try:
                    guest.date_of_birth = datetime.strptime(formatted_data['dob'], '%d/%m/%Y').date()
                except:
                    pass

            guest.save(update_fields=['full_name', 'date_of_birth'])
            logger.info(f"Saved AADHAR extracted data to guest {guest.id}")

            return show_aadhar_confirmation(conversation, guest, flow_data)

        # Try back side if front fails
        if back_image_data:
            back_result = decode_aadhaar_qr_from_image(back_image_data)
            if back_result:
                formatted_data = format_aadhar_data_for_display(back_result)
                flow_data["extracted_aadhar_info"] = formatted_data

                # Save extracted data to Guest immediately (can be overwritten later)
                if 'name' in formatted_data:
                    guest.full_name = formatted_data['name']
                if 'dob' in formatted_data:
                    from datetime import datetime
                    try:
                        guest.date_of_birth = datetime.strptime(formatted_data['dob'], '%d/%m/%Y').date()
                    except:
                        pass

                guest.save(update_fields=['full_name', 'date_of_birth'])
                logger.info(f"Saved AADHAR extracted data to guest {guest.id}")

                return show_aadhar_confirmation(conversation, guest, flow_data)

        # Both sides failed - redirect to NAME step for manual input
        response_text = "Couldn't extract AADHAR information from QR code. Please provide your details manually. Enter your full name:"
        save_system_message(conversation, response_text, CheckinStep.NAME)
        return {
            "type": "text",
            "text": response_text
        }

    except Exception as e:
        logger.error(f"Error processing AADHAR verification: {e}")
        response_text = "Error processing AADHAR QR code. Please provide your details manually. Enter your full name:"
        save_system_message(conversation, response_text, CheckinStep.NAME)
        return {
            "type": "text",
            "text": response_text
        }


def format_aadhar_data_for_display(aadhar_data):
    """Format AADHAR data for user confirmation."""
    formatted_data = {}

    # Map AADHAR fields to display format
    if "name" in aadhar_data:
        formatted_data["name"] = aadhar_data["name"].title()
    else:
        formatted_data["name"] = aadhar_data.get("full_name", "Not detected").title()

    if "dob" in aadhar_data:
        formatted_data["dob"] = aadhar_data["dob"]
    else:
        formatted_data["dob"] = aadhar_data.get("date_of_birth", "Not detected")

    return formatted_data


def show_aadhar_confirmation(conversation, guest, flow_data):
    """Show confirmation for extracted AADHAR data."""
    extracted_info = flow_data.get('extracted_aadhar_info', {})

    header_text = "Confirm AADHAR Details"
    body_text = f"📋 **AADHAR Information Extracted:**\n"
    body_text += f"• Name: {extracted_info.get('name', 'Not detected')}\n"
    body_text += f"• DOB: {extracted_info.get('dob', 'Not detected')}\n\n"
    body_text += "Please review the extracted information. If everything looks correct, confirm to proceed. Otherwise, select the option to correct the details."

    save_system_message(conversation, body_text, CheckinStep.AADHAR_CONFIRMATION)

    return {
        "type": "button",
        "text": header_text,
        "body_text": body_text,
        "options": [
            {"id": "confirm", "title": "Yes, Correct"},
            {"id": "modify", "title": "No, Correct It"}
        ]
    }


def show_confirmation_with_extracted_data(conversation, guest, flow_data):
    """Show confirmation with extracted or manual data."""

    # Use extracted info if available, otherwise use guest data
    extracted_info = flow_data.get('extracted_info') or flow_data.get('extracted_aadhar_info', {})

    name = extracted_info.get('name') or guest.full_name or 'Not provided'
    email = guest.email or 'Not provided'
    dob = extracted_info.get('dob') or (guest.date_of_birth.strftime('%d/%m/%Y') if guest.date_of_birth else 'Not provided')
    nationality = guest.nationality or 'Not provided'

    header_text = "Confirm Your Details"
    body_text = f"""Please review and confirm your information before we complete the check-in process:

📋 **Personal Information:**
• Name: {name}
• Email: {email}
• Date of Birth: {dob}
• Nationality: {nationality}

Please verify that all details are accurate. Select Confirm to proceed with check-in or Change Info to modify any details."""

    save_system_message(conversation, body_text, CheckinStep.CONFIRMATION)

    return {
        "type": "button",
        "text": header_text,
        "body_text": body_text,
        "options": [
            {"id": "confirm", "title": "Confirm"},
            {"id": "modify", "title": "Change Info"}
        ]
    }


def handle_confirmation_step(conversation, guest, message_text, flow_data):
    """Show confirmation of all collected data or process confirmation response."""

    # If message_text is empty, this is showing the confirmation
    if not message_text.strip():
        return show_confirmation_with_extracted_data(conversation, guest, flow_data)

    # Process confirmation response
    return process_confirmation_response(conversation, guest, message_text)


def show_confirmation(conversation, guest):
    """Show confirmation of all collected data."""

    dob_formatted = guest.date_of_birth.strftime('%d/%m/%Y') if guest.date_of_birth else 'Not provided'

    header_text = "Confirm Your Details"
    body_text = f"""Please review and confirm your information before we complete the check-in process:

📋 **Personal Information:**
• Name: {guest.full_name}
• Email: {guest.email}
• Date of Birth: {dob_formatted}
• Nationality: {guest.nationality}

Please verify that all details are accurate. Select Confirm to proceed with check-in or Change Info to modify any details."""

    save_system_message(conversation, body_text, CheckinStep.CONFIRMATION)

    return {
        "type": "button",
        "text": header_text,
        "body_text": body_text,
        "options": [
            {"id": "confirm", "title": "Confirm"},
            {"id": "modify", "title": "Change Info"}
        ]
    }


def process_confirmation_response(conversation, guest, message_text):
    """Process confirmation response."""

    response = message_text.strip().lower()

    # Handle both text responses and button responses (btn_0, btn_1)
    if response in ['confirm', 'btn_0']:
        # Create booking record for successful check-in
        from guest.models import Booking
        from django.utils import timezone

        # Create booking with current date as check-in date
        # Check-out date defaults to tomorrow (can be modified later)
        from datetime import timedelta
        booking = Booking.objects.create(
            hotel=conversation.hotel,
            primary_guest=guest,
            check_in_date=timezone.now(),
            check_out_date=timezone.now() + timedelta(days=1),
            status='pending',  # Will be confirmed by staff
            guest_names=[guest.full_name] if guest.full_name else []
        )

        # Update guest status
        guest.status = 'pending_checkin'
        guest.save(update_fields=['status'])

        # Update conversation
        conversation.conversation_type = 'booking_created'
        conversation.status = 'closed'
        conversation.save(update_fields=['conversation_type', 'status'])

        success_text = f"""✅ Check-in created successfully!

Dear {guest.full_name}, your check-in at {conversation.hotel.name} has been created.

Our receptionist will verify your details, assign you a room, and confirm your check-in shortly.

Booking ID: {booking.id}
Welcome to {conversation.hotel.name}! 🏨"""

        save_system_message(conversation, success_text, CheckinStep.COMPLETED)

        return {
            "type": "text",
            "text": success_text
        }

    elif response in ['modify', 'btn_1']:
        # Restart the flow
        response_text = "Let's start over. Please provide your full name:"
        save_system_message(conversation, response_text, CheckinStep.NAME)

        return {
            "type": "text",
            "text": response_text
        }

    else:
        # Invalid response - show confirmation again
        return show_confirmation(conversation, guest)


def show_confirmation_with_collected_data(conversation, guest, flow_data):
    """Show confirmation of all manually collected data."""

    # Build confirmation message with collected data
    header_text = "Confirm Your Details"

    # Build the data display
    data_parts = []
    if guest.full_name:
        data_parts.append(f"Name: {guest.full_name}")
    if guest.email:
        data_parts.append(f"Email: {guest.email}")
    if guest.date_of_birth:
        data_parts.append(f"Date of Birth: {guest.date_of_birth.strftime('%d/%m/%Y')}")
    if guest.nationality:
        data_parts.append(f"Nationality: {guest.nationality}")

    if data_parts:
        body_text = "Please confirm your details:\n\n" + "\n".join(data_parts) + "\n\nReply 'confirm' to complete check-in, or 'modify' to make changes."
    else:
        body_text = "No details found. Please contact support."

    save_system_message(conversation, f"{header_text}\n\n{body_text}", CheckinStep.CONFIRMATION)

    return {
        "type": "button",
        "text": header_text,
        "body_text": body_text,
        "options": [
            {"id": "confirm", "title": "Confirm"},
            {"id": "modify", "title": "Change Info"}
        ]
    }
