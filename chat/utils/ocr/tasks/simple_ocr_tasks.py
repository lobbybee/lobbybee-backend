"""
Simplified OCR tasks using Gemini 3.
Extract ID document data with a simple function call.
"""

import logging
from typing import Dict, Any, Optional
from celery import shared_task

from chat.utils.ocr.gemini_ocr import extract_id_document, detect_document_type

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=120,
    time_limit=180
)
def extract_id_document_task(
    self,
    image_path: str,
    document_type: str,
    back_image_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract structured data from ID document using Gemini 3.

    Args:
        image_path: Path to the front image of ID document
        document_type: Type of document (AADHAR, DRIVING_LICENSE, PASSPORT, etc.)
        back_image_path: Optional path to back image

    Returns:
        Dictionary containing extracted ID data:
        {
            'success': bool,
            'data': {
                'id_number': str,
                'full_name': str,
                'date_of_birth': str,
                'gender': str,
                'address': str,
                'expiry_date': str,
                'issue_date': str,
                'document_type': str
            },
            'api_used': str,
            'processing_method': str,
            'task_id': str
        }
    """
    logger.info(f"extract_id_document_task: Processing {document_type} document from {image_path}")

    try:
        result = extract_id_document(
            image_path=image_path,
            document_type=document_type,
            back_image_path=back_image_path
        )

        if result['success']:
            extracted_data = result['data']
            logger.info(
                f"extract_id_document_task: Successfully extracted {len(extracted_data)} fields "
                f"for {document_type}: {list(extracted_data.keys())}"
            )
        else:
            logger.error(f"extract_id_document_task: Extraction failed: {result.get('error')}")

        result['task_id'] = self.request.id
        return result

    except Exception as e:
        logger.error(f"extract_id_document_task: Unexpected error: {e}", exc_info=True)

        return {
            'success': False,
            'error': str(e),
            'data': {},
            'task_id': self.request.id
        }


def extract_id_document_sync(
    image_path: str,
    document_type: str,
    back_image_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous version - extract ID data without Celery.
    Use this for API endpoints that need immediate results.

    Args:
        image_path: Path to front image
        document_type: Document type
        back_image_path: Optional back image path

    Returns:
        Extracted data dictionary
    """
    return extract_id_document(image_path, document_type, back_image_path)


def detect_and_extract_id_document(
    image_path: str,
    back_image_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect document type and extract data in a single API call.

    Args:
        image_path: Path to front image
        back_image_path: Optional back image path

    Returns:
        Dictionary with:
        {
            'success': bool,
            'detected_type': str,
            'confidence': float,
            'data': dict with extracted fields,
            'error': str (if failed)
        }
    """
    logger.info(f"detect_and_extract_id_document: Processing document from {image_path}")
    
    # Single API call that detects and extracts
    result = extract_id_document(image_path, None, back_image_path)
    
    if result.get('success'):
        data = result.get('data', {})
        detected_type = data.get('detected_type', 'other')
        confidence = data.get('confidence', 0)
        
        # Map the detected type to the database format
        type_mapping = {
            'aadhar': 'aadhar_id',
            'aadhaar': 'aadhar_id', 
            'driving_license': 'driving_license',
            'license': 'driving_license',
            'national_id': 'national_id',
            'voter_id': 'voter_id',
            'voter': 'voter_id',
            'epic': 'voter_id'
        }
        
        # Get the mapped type or use the detected type directly
        mapped_type = None
        for key, value in type_mapping.items():
            if key in detected_type.lower():
                mapped_type = value
                break
        
        if not mapped_type:
            # If no mapping found, check if detected_type is already valid
            valid_types = ['aadhar_id', 'driving_license', 'national_id', 'voter_id', 'other']
            mapped_type = detected_type if detected_type in valid_types else 'other'
        
        logger.info(f"Auto-detected document type: {mapped_type} with confidence: {confidence}")
        
        return {
            'success': True,
            'detected_type': mapped_type,
            'confidence': confidence,
            'data': data,
            'error': None
        }
    else:
        logger.error(f"Document detection and extraction failed: {result.get('error')}")
        return {
            'success': False,
            'error': result.get('error', 'Unknown error'),
            'detected_type': None,
            'confidence': 0,
            'data': {}
        }
