import requests
from django.conf import settings
import logging
import mimetypes
from django.core.files.base import ContentFile
from ..models import Message


logger = logging.getLogger(__name__)

def upload_whatsapp_media(file_field):
    """
    Uploads a media file from a Django FileField to the WhatsApp API.
    This can be used for any file stored via Django's storage system (e.g., S3).

    Args:
        file_field: A Django FileField object (e.g., from a model instance).

    Returns:
        The WhatsApp media ID string, or None if the upload fails.
    """
    phone_number_id = settings.PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_KEY
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/media"

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    payload = {
        'messaging_product': 'whatsapp'
    }

    try:
        # Open the file in binary mode to read its content
        with file_field.open('rb') as f:
            mime_type = mimetypes.guess_type(file_field.name)[0] or 'application/octet-stream'
            files = {
                'file': (file_field.name, f.read(), mime_type)
            }
            response = requests.post(url, headers=headers, data=payload, files=files)
            response.raise_for_status()

            media_id = response.json().get('id')
            logger.info(f"Successfully uploaded media {file_field.name} to WhatsApp. Media ID: {media_id}")
            return media_id

    except requests.exceptions.RequestException as e:
        logger.error(f"Error uploading media to WhatsApp: {e}")
        logger.error(f"Response body: {e.response.text if e.response else 'No response'}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during WhatsApp media upload: {e}")
        raise


def get_whatsapp_media_info(media_id: str):
    """
    Retrieves media information from WhatsApp to check if the ID is still valid.

    Args:
        media_id: The WhatsApp Media ID to validate.

    Returns:
        A dictionary containing media info if the ID is valid, otherwise None.
    """
    access_token = settings.WHATSAPP_ACCESS_KEY
    url = f"https://graph.facebook.com/v22.0/{media_id}"  # Updated version
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, headers=headers)
        # A 404 Not Found error indicates the media ID has expired or is invalid.
        if response.status_code == 404:
            logger.info(f"WhatsApp Media ID {media_id} is expired or invalid.")
            return None

        response.raise_for_status()

        media_info = response.json()
        logger.info(f"Successfully validated WhatsApp Media ID {media_id}.")
        return media_info

    except requests.exceptions.RequestException as e:
        logger.error(f"Error validating WhatsApp media ID {media_id}: {e}")
        return None


def send_whatsapp_template_message(recipient_number: str, template_name: str, components: list = None, language_code: str = "en_US"):
    """
    Sends a WhatsApp message using a pre-approved template.
    """
    phone_number_id = settings.PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_KEY
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"  # Updated version

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",  # Added required field
        "to": recipient_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }

    if components:
        payload["template"]["components"] = components

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"WhatsApp message sent to {recipient_number} using template {template_name}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending WhatsApp message to {recipient_number}: {e}")
        logger.error(f"Response body: {e.response.text if e.response else 'No response'}")
        raise


def download_whatsapp_media(media_id: str, conversation_id: int = None):
    """
    Downloads media from WhatsApp and saves it to S3 as a Message media file.

    Args:
        media_id: The WhatsApp Media ID to download
        conversation_id: Optional conversation ID to associate with the message

    Returns:
        The Message instance with the downloaded media, or None if download fails
    """
    phone_number_id = settings.PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_KEY

    # Step 1: Get Media URL
    url = f"https://graph.facebook.com/v22.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Add phone_number_id as query parameter
    params = {"phone_number_id": phone_number_id}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        media_info = response.json()
        media_url = media_info['url']
        mime_type = media_info['mime_type']
        file_size = media_info.get('file_size', 0)

        # Step 2: Download media content
        download_response = requests.get(media_url, headers=headers)
        download_response.raise_for_status()
        file_content = download_response.content

        # Step 3: Determine message type based on mime_type
        if mime_type.startswith('image/'):
            message_type = 'image'
        elif mime_type.startswith('video/'):
            message_type = 'video'
        elif mime_type.startswith('audio/'):
            message_type = 'audio'
        else:
            message_type = 'document'

        # Create file extension
        extension = mimetypes.guess_extension(mime_type) or ''
        file_name = f"whatsapp_{media_id}{extension}"

        # Create a temporary message instance to save the file
        temp_message = Message(
            conversation_id=conversation_id or 1,
            sender_type='guest',
            message_type=message_type,
            content='',
        )

        # Save the file to the message
        temp_message.media_file.save(file_name, ContentFile(file_content), save=True)

        logger.info(f"Successfully downloaded WhatsApp media {media_id} and saved to {temp_message.media_file.name}")
        return temp_message

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading WhatsApp media {media_id}: {e}")
        logger.error(f"Response body: {e.response.text if e.response else 'No response'}")
        raise


def send_whatsapp_message_with_media(recipient_number: str, message_content: str, media_id: str = None, media_file=None):
    """
    Sends a WhatsApp message with optional media attachment.

    Args:
        recipient_number: The WhatsApp number to send to
        message_content: The text content of the message (used as caption for media)
        media_id: Optional WhatsApp media ID (for media already uploaded to WhatsApp)
        media_file: Optional Django FileField to upload to WhatsApp first

    Returns:
        The response from WhatsApp API
    """
    phone_number_id = settings.PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_KEY
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # If media_file is provided, upload it first
    if media_file and not media_id:
        media_id = upload_whatsapp_media(media_file)

    if media_id:
        # Determine media type
        if media_file:
            mime_type = mimetypes.guess_type(media_file.name)[0] or 'application/octet-stream'
        else:
            # If no media_file provided, default to document
            mime_type = 'application/octet-stream'

        # Determine message type based on mime type
        if mime_type.startswith('image/'):
            media_type = 'image'
        elif mime_type.startswith('video/'):
            media_type = 'video'
        elif mime_type.startswith('audio/'):
            media_type = 'audio'
        else:
            media_type = 'document'

        # Build media object
        media_object = {"id": media_id}
        if message_content and media_type in ['image', 'video', 'document']:
            media_object["caption"] = message_content

        # Send media message
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",  # Added required field
            "to": recipient_number,
            "type": media_type,
            media_type: media_object
        }
    else:
        # Send text message
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",  # Added required field
            "to": recipient_number,
            "type": "text",
            "text": {
                "body": message_content
            }
        }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"WhatsApp message sent to {recipient_number}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending WhatsApp message to {recipient_number}: {e}")
        logger.error(f"Response body: {e.response.text if e.response else 'No response'}")
        raise
