# flows/send_id_docs_flow.py

import logging
import os
import tempfile

from django.core.files.base import ContentFile
from django.db import transaction

logger = logging.getLogger(__name__)

from ..utils.whatsapp_utils import download_whatsapp_media
from chat.utils.ocr.tasks.simple_ocr_tasks import detect_and_extract_id_document


def process_send_id_docs_flow(guest, conversation=None, flow_data=None):
    """
    Process Send ID Documents flow for collecting accompanying guest ID documents.

    States:
    - Initial (no messages yet): Send upload instructions
    - Image received: Process silently (OCR -> dedupe -> save), no WhatsApp response
    - Re-selection from menu: Silent, flow continues
    - Non-image media: Warn about unsupported format
    - Text received: Exit flow, show confirmation + department menu
    """
    message_type = flow_data.get('message_type', 'text') if flow_data else 'text'
    message_text = flow_data.get('message', '') if flow_data else ''
    media_id = flow_data.get('media_id') if flow_data else None

    has_messages = conversation.messages.exists() if conversation else False

    # STATE 1: Initial - show upload instructions
    if not has_messages:
        save_system_message(
            conversation,
            "Send ID Documents flow started",
            flow_step='initial',
            flow_id='send_id_docs'
        )
        conversation.update_last_message("Send ID Documents flow started")
        return [{
            "type": "text",
            "text": (
                "\u2709\ufe0f *Send ID Documents*\n\n"
                "Please upload clear photos of your accompanying guests' "
                "ID documents one by one.\n\n"
                "\u2022 Send multiple images \u2014 we'll process each one\n"
                "\u2022 Type any text when you're done\n\n"
                "Our system will automatically extract the information."
            )
        }]

    # STATE 2: Re-selection from menu - silent, flow continues
    if message_text == 'dept_send_id_docs':
        save_guest_message(conversation, message_text, None, None, 're_selection')
        conversation.update_last_message(message_text)
        return []

    # STATE 3: Image received - process silently
    if message_type == 'image' and media_id:
        save_guest_message(conversation, "📷 ID document image", None, media_id, 'image_uploaded')
        _process_id_image(guest, conversation, media_id, flow_data)
        save_system_message(
            conversation,
            "ID document image processed",
            flow_step='image_processed',
            flow_id='send_id_docs'
        )
        conversation.update_last_message("ID document image processed")
        return []  # Silent - no WhatsApp response

    # STATE 4: Non-image media - warn
    if message_type in ['video', 'audio', 'document']:
        save_guest_message(conversation, f"Unsupported media type: {message_type}", None, None, 'unsupported')
        conversation.update_last_message(f"Unsupported media type: {message_type}")
        return [{
            "type": "text",
            "text": (
                "\u26a0\ufe0f Unsupported format. "
                "Please send an image (photo) of the ID document."
            )
        }]

    # STATE 5: Text received - exit flow
    from guest.models import Guest as GuestModel
    acc_count = GuestModel.objects.filter(
        whatsapp_number__startswith=f"ACC_{guest.whatsapp_number}_",
        is_primary_guest=False
    ).count() if guest else 0

    conversation.status = 'closed'
    conversation.save(update_fields=['status'])

    from ..utils.whatsapp_flow_utils import generate_department_menu_payload
    from guest.name_utils import get_first_name_from_full_name

    guest_name = get_first_name_from_full_name(guest.full_name) if guest else 'Guest'
    recipient = guest.whatsapp_number if guest else ''

    return [
        {
            "type": "text",
            "text": (
                f"\u2705 {acc_count} accompanying guest ID "
                f"document(s) collected. You can continue using hotel services."
            )
        },
        generate_department_menu_payload(recipient, guest_name)
    ]


def _process_id_image(primary_guest, conversation, media_id, flow_data):
    """Download, OCR, deduplicate, and store an ID document image."""
    from guest.models import Guest, GuestIdentityDocument, Stay

    try:
        media_data = download_whatsapp_media(media_id)
        if not media_data or not media_data.get('content'):
            logger.warning(f"send_id_docs_flow: Failed to download media {media_id}")
            return
    except Exception as e:
        logger.error(f"send_id_docs_flow: Error downloading media {media_id}: {e}")
        return

    # Write to temp file for OCR
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(media_data['content'])
            tmp_path = tmp.name

        result = detect_and_extract_id_document(image_path=tmp_path)
    except Exception as e:
        logger.error(f"send_id_docs_flow: OCR failed: {e}")
        result = {'success': False, 'data': {}}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    extracted_name = ''
    extracted_id_number = ''

    if result.get('success') and result.get('data'):
        extracted_name = (result['data'].get('full_name') or '').strip()
        extracted_id_number = (result['data'].get('id_number') or '').strip()

    name = extracted_name or 'Unknown'

    # DUPLICATE CHECK: same name + same id_number -> skip
    if name and extracted_id_number:
        dup_exists = GuestIdentityDocument.objects.filter(
            guest__whatsapp_number__startswith=f"ACC_{primary_guest.whatsapp_number}_",
            guest__full_name__iexact=name,
            document_number__iexact=extracted_id_number,
            is_accompanying_guest=True
        ).exists()
        if dup_exists:
            logger.info(
                f"send_id_docs_flow: Duplicate ID skipped "
                f"(name={name}, id={extracted_id_number})"
            )
            return

    # Find or create accompanying guest by name
    acc_guest = _find_or_create_accompanying_guest(primary_guest, name, extracted_id_number)

    # Store document
    with transaction.atomic():
        doc = GuestIdentityDocument.objects.create(
            guest=acc_guest,
            document_type='other',
            document_number=extracted_id_number or '',
            document_file=ContentFile(media_data['content'], name=media_data['filename']),
            is_accompanying_guest=True,
            is_primary=not GuestIdentityDocument.objects.filter(
                guest=acc_guest, is_primary=True
            ).exists()
        )

    # Update guest name if OCR succeeded and guest had generic name
    if extracted_name and acc_guest.full_name != extracted_name:
        # Only update if the current name is generic/placeholder
        current_name_lower = (acc_guest.full_name or '').lower()
        if current_name_lower in ('unknown', ''):
            acc_guest.full_name = extracted_name
            acc_guest.save(update_fields=['full_name'])

    # Ensure name in active stay's guest_names
    active_stay = Stay.objects.filter(guest=primary_guest, status='active').first()
    if active_stay and name and name != 'Unknown':
        names = list(active_stay.guest_names or [])
        if name not in names:
            names.append(name)
            active_stay.guest_names = names
            active_stay.save(update_fields=['guest_names'])

    logger.info(
        f"send_id_docs_flow: Stored ID doc for {name} "
        f"(guest_id={acc_guest.id}, doc_id={doc.id})"
    )


def _find_or_create_accompanying_guest(primary_guest, name, id_number=''):
    """Find existing accompanying guest by name match, or create new."""
    from guest.models import Guest

    # Try to find matching guest by name
    existing = Guest.objects.filter(
        whatsapp_number__startswith=f"ACC_{primary_guest.whatsapp_number}_",
        is_primary_guest=False,
        full_name__iexact=name
    ).first()

    if existing:
        return existing

    # Create new accompanying guest
    counter = Guest.objects.filter(
        whatsapp_number__startswith=f"ACC_{primary_guest.whatsapp_number}_"
    ).count() + 1

    return Guest.objects.create(
        full_name=name,
        is_primary_guest=False,
        status='checked_in',
        whatsapp_number=f"ACC_{primary_guest.whatsapp_number}_{counter}"
    )


def save_system_message(conversation, content, flow_step='initial', flow_id='send_id_docs', is_success=True):
    """Save system/bot response message in the flow conversation."""
    from chat.models import Message

    Message.objects.create(
        conversation=conversation,
        sender_type='staff',
        message_type='system',
        content=content,
        is_flow=True,
        flow_id=flow_id,
        flow_step=flow_step,
        is_flow_step_success=is_success
    )


def save_guest_message(conversation, message_text, message_id, media_id, flow_step):
    """Save incoming guest message in the flow conversation."""
    from chat.models import Message

    msg = Message.objects.create(
        conversation=conversation,
        sender_type='guest',
        message_type='text',
        content=message_text,
        whatsapp_message_id=message_id,
        is_flow=True,
        flow_id='send_id_docs',
        flow_step=flow_step
    )
    if message_id:
        msg.whatsapp_message_id = message_id
        msg.save(update_fields=['whatsapp_message_id'])

    conversation.update_last_message(message_text)
