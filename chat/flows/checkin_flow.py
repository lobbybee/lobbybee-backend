# flows/checkin_flow.py

import logging
from django.utils import timezone
from django.db import transaction
import re
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Import WhatsApp media download function
from ..utils.whatsapp_utils import download_whatsapp_media
import random
from faker import Faker

from chat.utils.ocr.tasks.simple_ocr_tasks import extract_id_document, extract_id_document_task, extract_id_document_sync


class CheckinStep:
    """Constants for check-in flow steps."""
    INITIAL = 0
    ID_TYPE = 1  # ID type selection
    ID_UPLOAD = 2  # ID upload steps
    ID_BACK_UPLOAD = 3
    COMPLETED = 4


# Document types supported - must match GuestIdentityDocument.DOCUMENT_TYPES
DOCUMENT_TYPES = {
    'aadhar_id': 'AADHAR',
    'driving_license': 'License',
    'national_id': 'National ID',
    'voter_id': 'Voter ID',
    'other': 'Other Govt ID'
}





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


def generate_random_guest_data():
    """Generate random guest data when QR code is not readable."""
    try:
        # Initialize faker
        fake = Faker()

        # Generate random name
        full_name = fake.name()

        # Generate random date of birth (18-65 years old)
        from datetime import date, timedelta
        today = date.today()
        min_birth_date = today - timedelta(days=65*365)
        max_birth_date = today - timedelta(days=18*365)
        random_days = random.randint(0, (max_birth_date - min_birth_date).days)
        dob = min_birth_date + timedelta(days=random_days)

        # Set nationality as Indian (default)
        nationality = "Indian"

        return {
            'name': full_name,
            'dob': dob,
            'nationality': nationality
        }
    except Exception as e:
        logger.error(f"Error generating random guest data: {e}")
        # Fallback data
        return {
            'name': 'Guest User',
            'dob': date(1990, 1, 1),
            'nationality': 'Indian'
        }


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
        CheckinStep.ID_TYPE: handle_id_type_step,
        CheckinStep.ID_UPLOAD: handle_id_upload_step,
        CheckinStep.ID_BACK_UPLOAD: handle_id_back_upload_step,
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

    logger.info(f"Processing check-in step: {current_step}")

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

    # Clean up previous incomplete attempts for returning guests
    # This prevents duplicate pending stays/bookings but preserves guest personal data
    cleanup_incomplete_guest_data_preserve_personal_info(guest)

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
    from guest.models import GuestIdentityDocument, Booking, Stay

    # Delete incomplete stays (pending status - these are from WhatsApp flows without room assignment)
    Stay.objects.filter(
        guest=guest,
        status='pending'
    ).delete()

    # Delete incomplete bookings (pending or cancelled status)
    # Note: pending_verification is a guest status, not a booking status
    Booking.objects.filter(
        primary_guest=guest,
        status__in=['pending']
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


def cleanup_incomplete_guest_data_preserve_personal_info(guest):
    """Clean up incomplete guest data from failed check-ins but preserve guest personal information."""
    from guest.models import GuestIdentityDocument, Booking, Stay

    # Delete incomplete stays (pending status - these are from WhatsApp flows without room assignment)
    Stay.objects.filter(
        guest=guest,
        status='pending'
    ).delete()

    # Delete incomplete bookings (pending or cancelled status)
    Booking.objects.filter(
        primary_guest=guest,
        status__in=['pending']
    ).delete()

    # Only delete UNVERIFIED identity documents, preserve verified ones
    GuestIdentityDocument.objects.filter(
        guest=guest,
        is_verified=False
    ).delete()

    # Reset guest status but preserve personal information
    guest.status = 'pending_checkin'
    guest.save(update_fields=['status'])


def show_guest_data_confirmation(conversation, guest, flow_data):
    """Show existing guest data for confirmation."""

    # Build confirmation message with existing data
    header_text = "Welcome Back!"

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
        body_text = "We found your previous information:\n\n" + "\n".join(data_parts) + "\n\nIs this information still correct?"
    else:
        body_text = "Welcome back! We'll need to collect your information for this check-in."

    # Create interactive response with confirmation buttons
    response = {
        "type": "button",
        "text": header_text,
        "body_text": body_text,
        "options": [
            {"id": "confirm_data", "title": "✓ Confirm"},
            {"id": "update_data", "title": "✏️ Update"}
        ]
    }

    save_system_message(conversation, f"{header_text}\n\n{body_text}\n\nOptions:\n1. Confirm\n2. Update", CheckinStep.INITIAL)

    return response


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
    """Initial step - start new check-in directly with ID type selection."""

    # Check if this is a response to returning guest data confirmation
    if message_text:
        response = message_text.strip().lower()

        # Check if guest is confirming existing data
        if response in ['yes', 'correct', 'confirm', '1', 'btn_0']:
            # Guest confirmed existing data - complete the checkin flow
            return complete_checkin_flow(conversation, guest)

        elif response in ['no', 'incorrect', 'update', '2', 'btn_1']:
            # Guest wants to update information - proceed to ID upload anyway
            # We'll use random data if QR is not readable
            header_text = "Select ID Document Type"
            body_text = "Let's complete your verification. Please select your government-issued ID document type from the list below."
            save_system_message(conversation, f"{header_text}\n\n{body_text}", CheckinStep.ID_TYPE)
            return get_id_type_options_response(header_text, body_text)

    # Fresh check-in start - go directly to ID type selection
    header_text = f"Welcome to {conversation.hotel.name}!"
    body_text = "Let's get you checked in quickly. Please select your government-issued ID document type to begin the verification process."
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
        logger.info(f"Processing ID upload for guest {guest.id}")

        # Download the media
        media_data = download_whatsapp_media(media_id)

        if not media_data or not media_data.get('content'):
            logger.error("Failed to download ID image or no content received")
            response_text = "Failed to download your ID image. Please try uploading again."
            save_system_message(conversation, response_text, CheckinStep.ID_UPLOAD, is_success=False)
            return {
                "type": "text",
                "text": response_text
            }

        # Store the front image data in flow_data
        flow_data['id_front_image'] = media_data['content']
        flow_data['id_front_filename'] = media_data['filename']

        # Save the image to the guest's document entry
        from guest.models import GuestIdentityDocument
        from django.core.files.base import ContentFile

        doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)
        doc.document_file.save(media_data['filename'], ContentFile(media_data['content']), save=True)
        doc.save()
        logger.info(f"Successfully saved document file for guest {guest.id}")

        # Get selected_id_type from GuestIdentityDocument instead of flow_data
        try:
            from guest.models import GuestIdentityDocument
            doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)
            selected_id_type = doc.document_type
        except GuestIdentityDocument.DoesNotExist:
            selected_id_type = 'aadhar_id'  # Default fallback
            logger.warning(f"No document found for guest {guest.id}, using default ID type")

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
    logger.info(f"Processing ID back upload for guest {guest.id}")

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
        import os

        doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)

        # Sanitize filename - use just the basename to avoid absolute path issues
        filename = os.path.basename(media_data['filename'])
        doc.document_file_back.save(filename, ContentFile(media_data['content']), save=True)
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
    """Process ID verification using simple OCR task."""
    logger.info(f"Processing ID verification for guest {guest.id}")

    # Get document from GuestIdentityDocument
    try:
        from guest.models import GuestIdentityDocument
        doc = GuestIdentityDocument.objects.get(guest=guest, is_primary=True)
        selected_id_type = doc.document_type
    except GuestIdentityDocument.DoesNotExist:
        logger.error(f"No document found for guest {guest.id}")
        return _generate_fallback_data_and_complete(conversation, guest, 'aadhar_id')

    # Get document paths (use .name instead of .path for cloud storage compatibility)
    front_image_path = doc.document_file.name if doc and doc.document_file else None
    back_image_path = doc.document_file_back.name if doc and doc.document_file_back else None

    if not front_image_path:
        logger.error(f"No front image found for guest {guest.id}")
        return _generate_fallback_data_and_complete(conversation, guest, selected_id_type)

    try:
        # Use simple OCR task to extract data
        logger.info(f"Extracting data from {selected_id_type} document")

        result = extract_id_document_sync(
            image_path=front_image_path,
            document_type=selected_id_type.upper(),
            back_image_path=back_image_path
        )

        

        if result.get('success') and result.get('data'):
            extracted_data = result['data']
            logger.info(f"Successfully extracted data: {list(extracted_data.keys())}")

            # Update guest information
            if extracted_data.get('full_name'):
                guest.full_name = extracted_data['full_name']

            if extracted_data.get('date_of_birth'):
                try:
                    # Parse DOB from extracted data
                    dob_str = extracted_data['date_of_birth']
                    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                        try:
                            parsed_dob = datetime.strptime(dob_str, fmt).date()
                            guest.date_of_birth = parsed_dob
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logger.warning(f"Failed to parse DOB '{extracted_data['date_of_birth']}': {e}")

            guest.save()

            # Update document with ID number
            if extracted_data.get('id_number') and doc:
                doc.document_number = extracted_data['id_number']
                doc.save()

            # Instead of sending a message and stopping, go directly to completion
            return complete_checkin_flow(conversation, guest)
        else:
            logger.error(f"OCR extraction failed: {result.get('error', 'Unknown error')}")
            return _generate_fallback_data_and_complete(conversation, guest, selected_id_type)

    except Exception as e:
        logger.error(f"Error processing ID verification: {e}", exc_info=True)
        return _generate_fallback_data_and_complete(conversation, guest, selected_id_type)


def _generate_fallback_data_and_complete(conversation, guest, selected_id_type):
    """Generate fallback data and complete checkin flow."""
    logger.info(f"Using fallback data for {DOCUMENT_TYPES[selected_id_type]} verification")

    # Generate random guest data
    random_data = generate_random_guest_data()

    # Save random data to guest
    guest.full_name = random_data['name']
    guest.date_of_birth = random_data['dob']
    guest.nationality = random_data['nationality']
    guest.save(update_fields=['full_name', 'date_of_birth', 'nationality'])

    logger.info(f"Generated fallback data for guest {guest.id}: {random_data['name']}, DOB: {random_data['dob']}")

    # Go directly to completion
    return complete_checkin_flow(conversation, guest)























def complete_checkin_flow(conversation, guest):
    """Complete the check-in flow by creating booking and stay records."""
    try:
        booking, stay = create_pending_stay_from_flow(conversation, guest)

        # Update conversation
        conversation.conversation_type = 'booking_created'
        conversation.status = 'closed'
        conversation.save(update_fields=['conversation_type', 'status'])

        response_text = f"""✅ Check-in completed successfully!

Dear {guest.full_name}, your information has been received and is pending verification.

Our receptionist will:
• Verify your identity documents
• Assign you a suitable room
• Confirm your check-in details

You'll receive a confirmation once your room is ready.

Booking ID: {booking.id}
Welcome to {conversation.hotel.name}! 🏨"""

        save_system_message(conversation, response_text, CheckinStep.COMPLETED)
        return {
            "type": "text",
            "text": response_text
        }

    except Exception as e:
        logger.error(f"Error completing check-in flow: {e}")
        error_text = "There was an error processing your check-in. Please contact the reception desk for assistance."
        save_system_message(conversation, error_text, CheckinStep.COMPLETED, is_success=False)
        return {
            "type": "text",
            "text": error_text
        }


def create_pending_stay_from_flow(conversation, guest):
    """
    Create pending stay and booking from completed WhatsApp check-in flow.
    This creates the booking without room assignment, which will be handled
    by receptionists during the verification step.
    """
    from guest.models import Booking, Stay
    from django.utils import timezone
    from datetime import timedelta

    try:
        with transaction.atomic():
            # Create booking record to group the stay
            # Use current date as check-in, tomorrow as check-out (can be modified by staff)
            booking = Booking.objects.create(
                hotel=conversation.hotel,
                primary_guest=guest,
                check_in_date=timezone.now().date(),
                check_out_date=(timezone.now() + timedelta(days=1)).date(),
                status='pending',  # Will be confirmed by staff after room assignment
                guest_names=[guest.full_name] if guest.full_name else [],
                total_amount=0,  # Will be calculated based on assigned room
                is_via_whatsapp=True  # This booking was created via WhatsApp check-in flow
            )

            # Create pending stay record without room assignment
            stay = Stay.objects.create(
                booking=booking,
                hotel=conversation.hotel,
                guest=guest,
                room=None,  # No room assigned yet - will be assigned by receptionist
                register_number=None,  # Will be assigned during verification
                check_in_date=timezone.now().date(),
                check_out_date=(timezone.now() + timedelta(days=1)).date(),
                number_of_guests=1,  # Default, can be updated by staff
                guest_names=[guest.full_name] if guest.full_name else [],
                status='pending',  # Pending room assignment and verification
                identity_verified=False,  # Documents uploaded but not verified
                documents_uploaded=True,  # Documents have been uploaded via WhatsApp
                actual_check_in=None  # Will be set when actually checked in
            )

            # Update guest status
            guest.status = 'pending_verification'
            guest.save(update_fields=['status'])

            logger.info(f"Created pending booking {booking.id} and stay {stay.id} for guest {guest.id} from WhatsApp flow")

            return booking, stay

    except Exception as e:
        logger.error(f"Error creating pending stay from flow: {e}", exc_info=True)
        raise
