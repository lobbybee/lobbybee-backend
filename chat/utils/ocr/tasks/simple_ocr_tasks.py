"""
Simple OCR tasks without model dependencies.
These tasks just extract text from images and parse ID documents.
"""

import logging
from typing import Dict, Any, Optional
from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings

from ..ocr_service import extract_text
from ..id_parser import IndianIDParser

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=60,
    time_limit=120
)
def extract_text_from_image_task(self, image_path: str) -> Dict[str, Any]:
    """
    Simple task to extract text from an image without any model dependencies.
    
    Args:
        image_path: Path to the image file (can be local or S3 path)
        
    Returns:
        Dictionary with extracted text or error information
    """
    logger.info(f"extract_text_from_image_task: Processing image {image_path}")
    
    try:
        # Extract text using our simple OCR service
        text = extract_text(image_path)
        
        logger.info(f"extract_text_from_image_task: Successfully extracted {len(text)} characters")
        
        return {
            'success': True,
            'text': text,
            'char_count': len(text),
            'word_count': len(text.split()),
            'line_count': text.count('\n') + 1,
            'task_id': self.request.id
        }
        
    except Exception as e:
        logger.error(f"extract_text_from_image_task: Error extracting text from {image_path}: {e}", exc_info=True)
        
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id
        }


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=60,
    time_limit=120
)
def parse_id_document_task(self, text: str) -> Dict[str, Any]:
    """
    Parse ID document from raw text using the ID parser.
    
    This is a standalone task that just parses text from an ID document
    without any model dependencies. It takes text input and returns
    structured data extracted from the text.
    
    Args:
        text: Raw text extracted from an ID document
        
    Returns:
        Dictionary containing the parsed ID data or error information
    """
    logger.info(f"parse_id_document_task: Parsing ID document from text")
    
    try:
        # Parse ID data from text
        parsed_data = IndianIDParser.parse(text)
        
        logger.info(f"parse_id_document_task: Successfully parsed document type: {parsed_data.get('document_type', 'Unknown')}")
        logger.info(f"parse_id_document_task: Extracted {len(parsed_data)} fields: {list(parsed_data.keys())}")
        
        return {
            'success': True,
            'parsed_data': parsed_data,
            'document_type': parsed_data.get('document_type', 'Unknown'),
            'fields_count': len(parsed_data),
            'task_id': self.request.id
        }
        
    except Exception as e:
        logger.error(f"parse_id_document_task: Error parsing ID document: {e}", exc_info=True)
        
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id
        }


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=120,
    time_limit=180
)
def process_id_document_image_task(self, image_path: str) -> Dict[str, Any]:
    """
    Complete task to process an ID document image - extract text and parse it.
    
    This combines both text extraction and ID parsing in one task.
    
    Args:
        image_path: Path to the ID document image
        
    Returns:
        Dictionary containing both the extracted text and parsed ID data
    """
    logger.info(f"process_id_document_image_task: Processing ID document {image_path}")
    
    try:
        # First extract text from the image
        text_result = extract_text_from_image_task(image_path)
        
        if not text_result.get('success', False):
            # Return the error from text extraction
            return text_result
        
        text = text_result['text']
        
        # Then parse the ID data from the extracted text
        parsed_result = parse_id_document_task(text)
        
        # Combine results
        return {
            'success': parsed_result.get('success', False),
            'text_extraction': {
                'char_count': text_result.get('char_count', 0),
                'word_count': text_result.get('word_count', 0),
                'line_count': text_result.get('line_count', 0)
            },
            'parsed_data': parsed_result.get('parsed_data', {}),
            'document_type': parsed_result.get('document_type', 'Unknown'),
            'fields_count': parsed_result.get('fields_count', 0),
            'error': parsed_result.get('error'),
            'task_id': self.request.id
        }
        
    except Exception as e:
        logger.error(f"process_id_document_image_task: Error processing ID document {image_path}: {e}", exc_info=True)
        
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id
        }