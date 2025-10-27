import requests
from django.conf import settings
import logging
import mimetypes
from django.core.files.base import ContentFile
from urllib.parse import urlparse
from ..models import Message


logger = logging.getLogger(__name__)

"""
WhatsApp Media Sending Options
==============================

This module supports two methods for sending media via WhatsApp:

1. UPLOAD METHOD (Original):
   - Upload file to WhatsApp servers first, get media ID, then send
   - Use: upload_whatsapp_media() + send_whatsapp_message_with_media()
   - Recommended for: files behind authentication, dynamic content, guaranteed delivery

2. DIRECT LINK METHOD (New):
   - Provide direct HTTP/HTTPS URL to media file
   - Use: send_whatsapp_*_with_link() functions
   - Recommended for: publicly accessible files, CDN-hosted content, simpler implementation

Media Type Support:
- Image: JPEG, PNG (max 5MB)
- Video: MP4, 3GPP (max 16MB) 
- Audio: AAC, MP4, MPEG, AMR, OGG (max 16MB)
- Document: PDF, Word, Excel, etc. (max 100MB)
- Sticker: WebP only (max 100KB)

Performance Notes:
- Direct link method is faster (no upload step)
- Upload method is more reliable for sensitive content
- Both methods support all media types listed above
"""

# WhatsApp Media Size Limits (in bytes)
WHATSAPP_MEDIA_LIMITS = {
    'image': 5 * 1024 * 1024,      # 5 MB
    'video': 16 * 1024 * 1024,     # 16 MB  
    'audio': 16 * 1024 * 1024,     # 16 MB
    'document': 100 * 1024 * 1024, # 100 MB
    'sticker': 100 * 1024,         # 100 KB
}

# Supported MIME types for each media category
WHATSAPP_MIME_TYPES = {
    'image': ['image/jpeg', 'image/png'],
    'video': ['video/mp4', 'video/3gpp'],
    'audio': ['audio/aac', 'audio/mp4', 'audio/mpeg', 'audio/amr', 'audio/ogg'],
    'document': ['text/plain', 'application/pdf', 'application/msword', 
                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                 'application/vnd.ms-excel', 
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
    'sticker': ['image/webp']
}

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


def download_whatsapp_media(media_id: str):
    """
    Downloads media from WhatsApp and returns file content and metadata.

    Args:
        media_id: The WhatsApp Media ID to download

    Returns:
        A dictionary containing:
        - content: File content bytes
        - message_type: The message type (image, video, audio, document)
        - filename: The generated filename
        - mime_type: The MIME type of the file
        or None if download fails
    """
    logger.info(f"download_whatsapp_media: Starting download for media_id: {media_id}")
    phone_number_id = settings.PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_KEY
    logger.info(f"download_whatsapp_media: Using phone_number_id: {phone_number_id}")

    # Step 1: Get Media URL
    url = f"https://graph.facebook.com/v22.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Add phone_number_id as query parameter
    params = {"phone_number_id": phone_number_id}

    try:
        logger.info(f"download_whatsapp_media: Getting media info from URL: {url}")
        response = requests.get(url, headers=headers, params=params)
        logger.info(f"download_whatsapp_media: Media info response status: {response.status_code}")
        response.raise_for_status()
        media_info = response.json()
        logger.info(f"download_whatsapp_media: Media info received: {media_info}")
        media_url = media_info['url']
        mime_type = media_info['mime_type']
        file_size = media_info.get('file_size', 0)
        logger.info(f"download_whatsapp_media: Media details - URL exists: {bool(media_url)}, MIME type: {mime_type}, Size: {file_size} bytes")

        # Step 2: Download media content
        logger.info(f"download_whatsapp_media: Downloading media content from: {media_url}")
        download_response = requests.get(media_url, headers=headers)
        logger.info(f"download_whatsapp_media: Download response status: {download_response.status_code}, Content-Length: {download_response.headers.get('Content-Length')}")
        download_response.raise_for_status()
        file_content = download_response.content
        logger.info(f"download_whatsapp_media: Downloaded {len(file_content)} bytes of content")

        # Step 3: Determine message type based on mime_type
        if mime_type.startswith('image/'):
            message_type = 'image'
        elif mime_type.startswith('video/'):
            message_type = 'video'
        elif mime_type.startswith('audio/'):
            message_type = 'audio'
        else:
            message_type = 'document'

        # Create file extension and filename
        extension = mimetypes.guess_extension(mime_type) or ''
        filename = f"whatsapp_{media_id}{extension}"

        result = {
            'content': file_content,
            'message_type': message_type,
            'filename': filename,
            'mime_type': mime_type,
            'file_size': file_size
        }

        logger.info(f"download_whatsapp_media: Successfully downloaded WhatsApp media {media_id} ({message_type}, {file_size} bytes, filename: {filename})")
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"download_whatsapp_media: Request exception downloading WhatsApp media {media_id}: {e}")
        if e.response:
            logger.error(f"download_whatsapp_media: Response status: {e.response.status_code}")
            logger.error(f"download_whatsapp_media: Response body: {e.response.text}")
        else:
            logger.error(f"download_whatsapp_media: No response received: {e}")
        return None
    except Exception as e:
        logger.error(f"download_whatsapp_media: Unexpected error downloading WhatsApp media {media_id}: {e}", exc_info=True)
        return None


def validate_media_url(url: str, media_type: str):
    """
    Validates a media URL for WhatsApp compatibility.
    
    Args:
        url: The URL to validate
        media_type: The type of media (image, video, audio, document, sticker)
        
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format"
        
        if parsed.scheme not in ['http', 'https']:
            return False, "URL must use HTTP or HTTPS protocol"
            
        return True, None
    except Exception as e:
        return False, f"URL validation error: {str(e)}"


def send_whatsapp_media_with_link(recipient_number: str, media_url: str, media_type: str, 
                                 caption: str = None, filename: str = None):
    """
    Sends a WhatsApp message with media using a direct link/URL.
    
    Args:
        recipient_number: The WhatsApp number to send to
        media_url: Direct HTTP/HTTPS URL to the media file
        media_type: Type of media - 'image', 'video', 'audio', 'document', or 'sticker'
        caption: Optional caption for image, video, or document
        filename: Optional filename for documents
        
    Returns:
        The response from WhatsApp API
        
    Raises:
        ValueError: If media_type is invalid or URL validation fails
        requests.exceptions.RequestException: If API request fails
    """
    if media_type not in WHATSAPP_MEDIA_LIMITS:
        raise ValueError(f"Invalid media type: {media_type}. Must be one of: {list(WHATSAPP_MEDIA_LIMITS.keys())}")
    
    # Validate URL
    is_valid, error_msg = validate_media_url(media_url, media_type)
    if not is_valid:
        raise ValueError(f"Invalid media URL: {error_msg}")
    
    phone_number_id = settings.PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_KEY
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Build media object with link
    media_object = {"link": media_url}
    
    # Add optional parameters based on media type
    if caption and media_type in ['image', 'video', 'document']:
        media_object["caption"] = caption
    
    if filename and media_type == 'document':
        media_object["filename"] = filename

    # Build payload
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": media_type,
        media_type: media_object
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"WhatsApp media message sent to {recipient_number} using link: {media_url}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending WhatsApp media message to {recipient_number}: {e}")
        logger.error(f"Response body: {e.response.text if e.response else 'No response'}")
        raise


def send_whatsapp_image_with_link(recipient_number: str, image_url: str, caption: str = None):
    """
    Sends a WhatsApp message with an image using a direct link.
    
    Args:
        recipient_number: The WhatsApp number to send to
        image_url: Direct HTTP/HTTPS URL to the image file
        caption: Optional caption for the image
        
    Returns:
        The response from WhatsApp API
    """
    return send_whatsapp_media_with_link(recipient_number, image_url, 'image', caption)


def send_whatsapp_video_with_link(recipient_number: str, video_url: str, caption: str = None):
    """
    Sends a WhatsApp message with a video using a direct link.
    
    Args:
        recipient_number: The WhatsApp number to send to
        video_url: Direct HTTP/HTTPS URL to the video file
        caption: Optional caption for the video
        
    Returns:
        The response from WhatsApp API
    """
    return send_whatsapp_media_with_link(recipient_number, video_url, 'video', caption)


def send_whatsapp_audio_with_link(recipient_number: str, audio_url: str):
    """
    Sends a WhatsApp message with audio using a direct link.
    
    Args:
        recipient_number: The WhatsApp number to send to
        audio_url: Direct HTTP/HTTPS URL to the audio file
        
    Returns:
        The response from WhatsApp API
    """
    return send_whatsapp_media_with_link(recipient_number, audio_url, 'audio')


def send_whatsapp_document_with_link(recipient_number: str, document_url: str, 
                                    caption: str = None, filename: str = None):
    """
    Sends a WhatsApp message with a document using a direct link.
    
    Args:
        recipient_number: The WhatsApp number to send to
        document_url: Direct HTTP/HTTPS URL to the document file
        caption: Optional caption for the document
        filename: Optional filename for the document
        
    Returns:
        The response from WhatsApp API
    """
    return send_whatsapp_media_with_link(recipient_number, document_url, 'document', 
                                        caption, filename)


def send_whatsapp_sticker_with_link(recipient_number: str, sticker_url: str):
    """
    Sends a WhatsApp message with a sticker using a direct link.
    
    Args:
        recipient_number: The WhatsApp number to send to
        sticker_url: Direct HTTP/HTTPS URL to the sticker file (must be WebP format)
        
    Returns:
        The response from WhatsApp API
    """
    return send_whatsapp_media_with_link(recipient_number, sticker_url, 'sticker')


def test_media_link_validation():
    """
    Test function to validate media link functionality.
    This can be used for debugging and testing the new media link features.
    
    Returns:
        dict: Test results with validation status for different scenarios
    """
    test_cases = [
        ("https://example.com/image.jpg", "image", True),
        ("http://example.com/video.mp4", "video", True), 
        ("ftp://example.com/file.pdf", "document", False),  # Invalid protocol
        ("not-a-url", "image", False),  # Invalid URL
        ("https://example.com/audio.mp3", "audio", True),
    ]
    
    results = {}
    
    for url, media_type, expected in test_cases:
        is_valid, error_msg = validate_media_url(url, media_type)
        test_passed = is_valid == expected
        results[f"{media_type}_{url}"] = {
            "url": url,
            "media_type": media_type,
            "expected": expected,
            "actual": is_valid,
            "passed": test_passed,
            "error": error_msg if not is_valid else None
        }
    
    logger.info(f"Media link validation test results: {results}")
    return results


def send_whatsapp_message_with_media(recipient_number: str, message_content: str, media_id: str = None, media_file=None, media_url: str = None):
    """
    Sends a WhatsApp message with optional media attachment.

    Args:
        recipient_number: The WhatsApp number to send to
        message_content: The text content of the message (used as caption for media)
        media_id: Optional WhatsApp media ID (for media already uploaded to WhatsApp)
        media_file: Optional Django FileField to upload to WhatsApp first
        media_url: Optional direct URL to media file (bypasses upload)

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

    # Handle media URL (direct link method)
    if media_url and not media_id:
        # Try to detect media type from URL if possible
        media_type = 'document'  # default
        try:
            parsed_url = urlparse(media_url)
            file_path = parsed_url.path.lower()
            if file_path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                media_type = 'image'
            elif file_path.endswith(('.mp4', '.3gp', '.mov')):
                media_type = 'video'
            elif file_path.endswith(('.mp3', '.aac', '.ogg', '.amr', '.m4a')):
                media_type = 'audio'
            elif file_path.endswith('.webp') and 'sticker' in file_path:
                media_type = 'sticker'
        except Exception:
            pass  # Keep default 'document' type
        
        # Only use caption for media types that support it
        caption = message_content if media_type in ['image', 'video', 'document'] else None
        return send_whatsapp_media_with_link(recipient_number, media_url, media_type, caption)

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
