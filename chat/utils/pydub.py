import logging
import io
from pydub import AudioSegment
from typing import Optional, Union

logger = logging.getLogger(__name__)


def convert_webm_to_ogg(webm_audio_data: Union[bytes, io.BytesIO]) -> Optional[bytes]:
    """
    Convert WebM audio data to OGG format with Opus codec for WhatsApp compatibility.
    
    This function converts incoming WebM audio files to OGG format using the Opus codec
    with specific parameters optimized for WhatsApp voice messages.
    
    Args:
        webm_audio_data: WebM audio data as bytes or BytesIO object
        
    Returns:
        Converted OGG audio data as bytes, or None if conversion fails
        
    Example:
        >>> with open('audio.webm', 'rb') as f:
        ...     webm_data = f.read()
        >>> ogg_data = convert_webm_to_ogg(webm_data)
        >>> if ogg_data:
        ...     # Use the converted OGG data
        ...     pass
    """
    try:
        logger.info("Starting WebM to OGG conversion")
        
        # Convert bytes to BytesIO if needed
        if isinstance(webm_audio_data, bytes):
            webm_stream = io.BytesIO(webm_audio_data)
        else:
            webm_stream = webm_audio_data
            
        # Load WebM audio
        logger.info("Loading WebM audio data")
        audio = AudioSegment.from_file(webm_stream, format="webm")
        
        # Create output buffer
        output_buffer = io.BytesIO()
        
        # Export to OGG with Opus codec and specified parameters
        logger.info("Exporting to OGG format with Opus codec")
        audio.export(
            output_buffer,
            format='ogg',
            codec='libopus',
            bitrate='32k',
            parameters=['-application', 'voip']
        )
        
        # Get the converted data
        ogg_data = output_buffer.getvalue()
        output_buffer.close()
        
        logger.info(f"Successfully converted WebM to OGG. Output size: {len(ogg_data)} bytes")
        return ogg_data
        
    except Exception as e:
        logger.error(f"Error converting WebM to OGG: {str(e)}", exc_info=True)
        return None


def is_webm_audio(mime_type: str) -> bool:
    """
    Check if the MIME type represents WebM audio.
    
    Args:
        mime_type: The MIME type to check
        
    Returns:
        True if it's WebM audio, False otherwise
    """
    return mime_type in ['audio/webm', 'audio/webm;codecs=opus']


def convert_audio_for_whatsapp(audio_data: bytes, mime_type: str) -> Optional[bytes]:
    """
    Convert audio data to WhatsApp-compatible format if needed.
    
    This function checks if the audio is in WebM format and converts it to OGG
    with Opus codec for WhatsApp compatibility.
    
    Args:
        audio_data: Audio data as bytes
        mime_type: The MIME type of the audio data
        
    Returns:
        Converted audio data as bytes, or original data if no conversion needed
    """
    if is_webm_audio(mime_type):
        logger.info(f"Converting WebM audio ({mime_type}) to OGG for WhatsApp")
        return convert_webm_to_ogg(audio_data)
    else:
        logger.info(f"Audio format {mime_type} doesn't require conversion for WhatsApp")
        return audio_data