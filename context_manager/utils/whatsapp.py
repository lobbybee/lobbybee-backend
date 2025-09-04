
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_whatsapp_template_message(recipient_number: str, template_name: str, components: list = None, language_code: str = "en_US"):
    """
    Sends a WhatsApp message using a pre-approved template.
    """
    phone_number_id = settings.PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_KEY
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
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


import mimetypes
from django.core.files.base import ContentFile
from context_manager.models import WhatsappMedia

def download_whatsapp_media(media_id: str):
    """
    Downloads media from WhatsApp and saves it to S3.
    """
    phone_number_id = settings.PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_KEY

    # Step 1: Get Media URL
    url = f"https://graph.facebook.com/v20.0/{media_id}?phone_number_id={phone_number_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        media_info = response.json()
        media_url = media_info['url']
        mime_type = media_info['mime_type']
        file_size = media_info['file_size']

        # Step 2: Download media content
        download_response = requests.get(media_url, headers=headers)
        download_response.raise_for_status()
        file_content = download_response.content

        # Step 3: Save to model
        if WhatsappMedia.objects.filter(whatsapp_media_id=media_id).exists():
            return WhatsappMedia.objects.get(whatsapp_media_id=media_id)

        extension = mimetypes.guess_extension(mime_type)
        file_name = f"{media_id}{extension}"

        media_instance = WhatsappMedia(
            whatsapp_media_id=media_id,
            mime_type=mime_type,
            file_size=file_size,
        )
        media_instance.file.save(file_name, ContentFile(file_content), save=True)

        return media_instance

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading WhatsApp media {media_id}: {e}")
        logger.error(f"Response body: {e.response.text if e.response else 'No response'}")
        raise
