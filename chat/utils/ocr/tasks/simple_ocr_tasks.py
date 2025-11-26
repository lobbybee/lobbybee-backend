"""
Simplified OCR tasks using Gemini 3.
Extract ID document data with a simple function call.
"""

import logging
from typing import Dict, Any, Optional
from celery import shared_task

from chat.utils.ocr.gemini_ocr import extract_id_document

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
