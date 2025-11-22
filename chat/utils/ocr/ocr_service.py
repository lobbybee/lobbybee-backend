import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.storage import default_storage
import boto3

logger = logging.getLogger(__name__)


class TextractOCRService:
    """
    AWS Textract OCR service for extracting text from documents.
    
    This service provides simple text extraction functionality using AWS Textract's
    DetectText API without any model dependencies.
    """
    
    def __init__(self):
        """Initialize Textract client using existing AWS credentials."""
        try:
            self.textract_client = boto3.client(
                'textract',
                aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
                aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            )
            logger.info("TextractOCRService: Successfully initialized Textract client")
        except Exception as e:
            logger.error(f"TextractOCRService: Failed to initialize Textract client: {e}")
            self.textract_client = None
    
    def _validate_service(self) -> bool:
        """Validate that Textract client is properly initialized."""
        if not self.textract_client:
            logger.error("TextractOCRService: Textract client not initialized")
            return False
        return True
    
    def _preprocess_image(self, file_path: str) -> Optional[str]:
        """
        Preprocess image for optimal Textract processing.
        
        Args:
            file_path: S3 path or local path to the image file
            
        Returns:
            Path to preprocessed image or None if preprocessing fails
        """
        try:
            # For now, just return the original path
            # In a more complex implementation, you might want to
            # resize, rotate, or optimize the image here
            return file_path
        except Exception as e:
            logger.error(f"TextractOCRService: Failed to preprocess image: {e}")
            return None
    
    def _download_from_s3(self, s3_path: str) -> Optional[bytes]:
        """
        Download image from S3 storage.
        
        Args:
            s3_path: S3 path to the image file
            
        Returns:
            Image data as bytes or None if download fails
        """
        try:
            return default_storage.open(s3_path).read()
        except Exception as e:
            logger.error(f"TextractOCRService: Failed to download from S3: {e}")
            return None
    
    def detect_document_text(self, image_path: str) -> Dict[str, Any]:
        """
        Extract text from a document image using Textract's DetectText API.
        
        Args:
            image_path: Path to the document image
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        if not self._validate_service():
            return {
                'success': False,
                'error': 'Textract client not initialized',
                'text': ''
            }
        
        try:
            # Check if textract client is available
            if not self.textract_client:
                return {
                    'success': False,
                    'error': 'Textract client not initialized',
                    'text': ''
                }
                
            # Preprocess the image if needed
            processed_path = self._preprocess_image(image_path)
            if not processed_path:
                return {
                    'success': False,
                    'error': 'Failed to preprocess image',
                    'text': ''
                }
            
            # Check if it's an S3 path or local file
            if image_path.startswith('s3://') or not image_path.startswith('/'):
                # It's likely an S3 path or Django storage path
                image_bytes = self._download_from_s3(image_path)
                if not image_bytes:
                    # Try using S3Object reference if bytes download fails
                    try:
                        response = self.textract_client.detect_document_text(
                            Document={'S3Object': {'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Name': image_path}}
                        )
                    except Exception as s3_error:
                        logger.error(f"TextractOCRService: Failed to process S3 object directly: {s3_error}")
                        return {
                            'success': False,
                            'error': 'Failed to download image from storage and S3 reference failed',
                            'text': ''
                        }
                else:
                    # Call Textract with bytes
                    response = self.textract_client.detect_document_text(
                        Document={'Bytes': image_bytes}
                    )
            else:
                # It's a local file path
                with open(image_path, 'rb') as image_file:
                    response = self.textract_client.detect_document_text(
                        Document={'Bytes': image_file.read()}
                    )
            
            # Extract text from response
            text_lines = []
            for block in response['Blocks']:
                if block['BlockType'] == 'LINE':
                    text_lines.append(block['Text'])
            
            extracted_text = '\n'.join(text_lines)
            
            logger.info(f"TextractOCRService: Successfully extracted {len(text_lines)} lines of text")
            
            return {
                'success': True,
                'text': extracted_text,
                'lines': text_lines,
                'confidence_scores': [
                    block.get('Confidence', 0) for block in response['Blocks'] 
                    if block['BlockType'] == 'LINE'
                ],
                'blocks': response.get('Blocks', [])
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"TextractOCRService: AWS Textract error: {error_code} - {error_message}")
            return {
                'success': False,
                'error': f'AWS Textract error: {error_code}',
                'text': ''
            }
        except Exception as e:
            logger.error(f"TextractOCRService: Unexpected error during text extraction: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': ''
            }


# Create a singleton instance for easy import
textract_ocr_service = TextractOCRService()


def extract_text_from_document(image_path: str) -> Dict[str, Any]:
    """
    Simple function to extract text from any document.
    
    Args:
        image_path: Path to the document image
        
    Returns:
        Dictionary containing extracted text and metadata
    """
    return textract_ocr_service.detect_document_text(image_path)


def extract_text(image_path: str) -> str:
    """
    Very simple function to extract just the text from an image.
    
    Args:
        image_path: Path to the document image
        
    Returns:
        Raw extracted text as a string
        
    Raises:
        ValueError: If text extraction fails
    """
    result = textract_ocr_service.detect_document_text(image_path)
    
    if result.get('success', False) and 'text' in result:
        return result['text']
    
    error_msg = result.get('error', 'Unknown error occurred during text extraction')
    raise ValueError(f"Failed to extract text: {error_msg}")