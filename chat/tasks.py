import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from guest.models import Guest, GuestIdentityDocument
# TODO: GuestSession and GuestMessage models don't exist yet
# from chat.models import GuestSession, GuestMessage
from chat.utils.ocr.ocr_service import extract_text, extract_text_from_document
from chat.utils.ocr.id_parser import IndianIDParser, extract_text_from_ocr_result


logger = logging.getLogger(__name__)

# TODO: Temporary placeholder for GuestSession since model doesn't exist yet
class MockGuestSession:
    def __init__(self, session_id):
        self.id = session_id
        self.phone_number = None
        self.guest = None
        self.session_data = {}
    
    @classmethod
    def objects(cls):
        class MockObjects:
            def get(self, id):
                return MockGuestSession(id)
        return MockObjects()
    
    def save(self, update_fields=None):
        pass

# Use MockGuestSession in place of GuestSession for now
GuestSession = MockGuestSession

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=300,  # 5 minutes timeout
    time_limit=600        # 10 minutes hard timeout
)
def process_id_document_ocr_task(self, guest_session_id: int, document_id: int, document_type: str) -> Dict[str, Any]:
    """
    Process ID document with AWS Textract OCR asynchronously.
    
    This task handles the complete OCR processing pipeline:
    1. Download document from storage
    2. Process with AWS Textract (AnalyzeID or DetectText)
    3. Parse extracted data using ID parser
    4. Update database with results
    5. Notify user about processing status
    
    Args:
        guest_session_id: ID of the guest session
        document_id: ID of the GuestIdentityDocument record
        document_type: Type of document (AADHAR, DRIVING_LICENSE, etc.)
        
    Returns:
        Dictionary containing processing results and metadata
    """
    logger.info(f"process_id_document_ocr_task: Starting OCR processing for document_id={document_id}, document_type={document_type}")
    
    try:
        # Step 1: Retrieve guest session and document
        try:
            guest_session = GuestSession.objects.get(id=guest_session_id)
            document = GuestIdentityDocument.objects.get(id=document_id)
        except (GuestIdentityDocument.DoesNotExist) as e:
            logger.error(f"process_id_document_ocr_task: Document not found: {e}")
            return {
                'success': False,
                'error': f'Record not found: {e}',
                'task_id': self.request.id
            }
        
        # Step 2: Update document processing status
        # Note: GuestIdentityDocument model doesn't have verification_status field
        # We'll proceed without status update for now
        pass
        
        # Step 3: Get document paths
        front_image_path = document.document_file.name if document.document_file else None
        back_image_path = document.document_file_back.name if document.document_file_back else None
        
        if not front_image_path:
            logger.error(f"process_id_document_ocr_task: No front image found for document_id={document_id}")
            return {
                'success': False,
                'error': 'No front image found',
                'task_id': self.request.id
            }
        
        # Note: Processing notification handled by checkin flow
        pass
        
        # Step 5: Process with OCR
        logger.info(f"process_id_document_ocr_task: Processing document {front_image_path} with OCR")
        ocr_result = process_id_document_with_ocr(front_image_path, back_image_path)
        
        if not ocr_result['success']:
            logger.error(f"process_id_document_ocr_task: OCR processing failed for document_id={document_id}: {ocr_result.get('error')}")
            # Note: Mark verification as failed using is_verified field
            document.is_verified = False
            document.save(update_fields=['is_verified'])
            
            # Note: Error notification handled by checkin flow
            
            return {
                'success': False,
                'error': ocr_result.get('error', 'OCR processing failed'),
                'task_id': self.request.id,
                'api_used': ocr_result.get('api_used'),
                'processing_method': ocr_result.get('processing_method')
            }
        
        # Step 6: Extract and structure the data
        extracted_data = ocr_result['data']
        
        # Create a clean data structure for the guest
        guest_data = _extract_guest_data_from_ocr(extracted_data, document_type)
        
        # Debug: Log OCR extracted data for troubleshooting
        logger.info(f"DEBUG: OCR extracted data for document_id={document_id}: {guest_data}")
        logger.info(f"DEBUG: Raw OCR result keys: {list(extracted_data.keys())}")
        if 'confidence_scores' in extracted_data:
            logger.info(f"DEBUG: OCR confidence scores: {extracted_data['confidence_scores']}")
        
        # Step 7: Update document with OCR results
        # Note: Don't set is_verified=True here since OCR extraction != verification
        # Verification will be done separately after guest confirms the data
        # Note: GuestIdentityDocument model doesn't have these fields:
        # extracted_data, ocr_confidence, ocr_api_used, processed_at
        # No save needed since we're not changing any fields yet
        pass
        
        # Step 8: Update or create guest record
        _update_guest_record(guest_session, guest_data, document_type)
        
        # Note: Success notification handled by checkin flow
        
        logger.info(f"process_id_document_ocr_task: Successfully processed document_id={document_id}")
        
        return {
            'success': True,
            'guest_session_id': guest_session_id,
            'document_id': document_id,
            'document_type': document_type,
            'extracted_data': guest_data,
            'api_used': ocr_result.get('api_used'),
            'processing_method': ocr_result.get('processing_method'),
            'confidence_scores': ocr_result.get('confidence_scores', {}),
            'task_id': self.request.id
        }
        
    except Exception as e:
        logger.error(f"process_id_document_ocr_task: Unexpected error for document_id={document_id}: {e}", exc_info=True)
        
        # Update document status to failed if we can
        try:
            document = GuestIdentityDocument.objects.get(id=document_id)
            document.is_verified = False
            document.save(update_fields=['is_verified'])
        except Exception:
            pass  # Document might not exist or other DB error
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=180,
    time_limit=300
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
    retry_kwargs={'max_retries': 1},
    soft_time_limit=60,
    time_limit=120
)
def handle_ocr_completion_task(self, guest_session_id: int, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle completion of OCR processing and update checkin flow.
    
    This task is called after successful OCR processing to
    update the guest session and continue the checkin flow.
    
    Args:
        guest_session_id: ID of the guest session
        ocr_result: Result from the OCR processing task
        
    Returns:
        Dictionary containing completion status and next steps
    """
    logger.info(f"handle_ocr_completion_task: Handling OCR completion for session {guest_session_id}")
    
    try:
        # Retrieve guest session
        try:
            guest_session = GuestSession.objects.get(id=guest_session_id)
        except GuestSession.DoesNotExist:
            logger.error(f"handle_ocr_completion_task: Guest session not found: {guest_session_id}")
            return {
                'success': False,
                'error': 'Guest session not found',
                'task_id': self.request.id
            }
        
        # Update session with OCR results
        if ocr_result.get('success'):
            guest_data = ocr_result.get('extracted_data', {})
            
            # Store extracted data in session for later use
            session_data = guest_session.session_data or {}
            session_data['ocr_extracted_data'] = guest_data
            session_data['document_verified'] = True
            session_data['ocr_processing_completed'] = timezone.now().isoformat()
            
            guest_session.session_data = session_data
            guest_session.save(update_fields=['session_data'])
            
            # Trigger next step in checkin flow
            _continue_checkin_flow_after_ocr(guest_session, guest_data)
            
            logger.info(f"handle_ocr_completion_task: Successfully handled OCR completion for session {guest_session_id}")
            
            return {
                'success': True,
                'guest_session_id': guest_session_id,
                'next_step': 'guest_data_confirmation',
                'extracted_fields': len(guest_data),
                'task_id': self.request.id
            }
        else:
            # Handle OCR failure
            logger.error(f"handle_ocr_completion_task: OCR processing failed for session {guest_session_id}: {ocr_result.get('error')}")
            
            # Update session to indicate failure
            session_data = guest_session.session_data or {}
            session_data['ocr_processing_failed'] = True
            session_data['ocr_error'] = ocr_result.get('error', 'Unknown error')
            
            guest_session.session_data = session_data
            guest_session.save(update_fields=['session_data'])
            
            # Note: Manual verification notification handled by checkin flow
            
            return {
                'success': False,
                'error': ocr_result.get('error'),
                'guest_session_id': guest_session_id,
                'requires_manual_verification': True,
                'task_id': self.request.id
            }
        
    except Exception as e:
        logger.error(f"handle_ocr_completion_task: Error handling OCR completion: {e}", exc_info=True)
        
        return {
            'success': False,
            'error': str(e),
            'guest_session_id': guest_session_id,
            'task_id': self.request.id
        }


@shared_task(
    bind=True,
    soft_time_limit=300,
    time_limit=600
)
def process_batch_ocr_documents_task(self, document_ids: List[int]) -> Dict[str, Any]:
    """
    Process multiple ID documents with OCR in batch.
    
    This task can be used for bulk processing of documents,
    such as for periodic re-processing or manual verification workflows.
    
    Args:
        document_ids: List of GuestIdentityDocument IDs to process
        
    Returns:
        Dictionary containing batch processing results
    """
    logger.info(f"process_batch_ocr_documents_task: Starting batch processing for {len(document_ids)} documents")
    
    results = []
    successful_count = 0
    failed_count = 0
    
    for document_id in document_ids:
        try:
            document = GuestIdentityDocument.objects.get(id=document_id)
            
            # Process this document
            ocr_result = process_id_document_with_ocr(
                document.document_file.name if document.document_file else None,
                document.document_file_back.name if document.document_file_back else None
            )
            
            if ocr_result['success']:
                # Debug: Log OCR extracted data for troubleshooting
                logger.info(f"DEBUG: Batch OCR extracted data for document_id={document_id}: {ocr_result.get('data', {})}")
                logger.info(f"DEBUG: Batch OCR API used: {ocr_result.get('api_used', 'Unknown')}")
                logger.info(f"DEBUG: Batch OCR processing method: {ocr_result.get('processing_method', 'Unknown')}")
                
                # Note: Don't set is_verified=True here since OCR extraction != verification
                # Verification will be done separately after guest confirms the data
                pass
                
                successful_count += 1
                results.append({
                    'document_id': document_id,
                    'success': True,
                    'api_used': ocr_result.get('api_used')
                })
            else:
                # Mark as failed
                document.is_verified = False
                document.save(update_fields=['is_verified'])
                
                failed_count += 1
                results.append({
                    'document_id': document_id,
                    'success': False,
                    'error': ocr_result.get('error', 'Unknown error')
                })
                
        except Exception as e:
            logger.error(f"process_batch_ocr_documents_task: Error processing document {document_id}: {e}")
            failed_count += 1
            results.append({
                'document_id': document_id,
                'success': False,
                'error': str(e)
            })
    
    logger.info(f"process_batch_ocr_documents_task: Completed batch processing: {successful_count} successful, {failed_count} failed")
    
    return {
        'success': True,
        'total_documents': len(document_ids),
        'successful_count': successful_count,
        'failed_count': failed_count,
        'results': results,
        'task_id': self.request.id
    }


# Helper functions

def _extract_guest_data_from_ocr(extracted_data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
    """
    Extract and structure guest data from OCR results.
    
    Args:
        extracted_data: Raw OCR data
        document_type: Type of document processed
        
    Returns:
        Structured guest data dictionary
    """
    logger.info(f"DEBUG: _extract_guest_data_from_ocr called with document_type: {document_type}")
    logger.info(f"DEBUG: extracted_data contains {len(extracted_data)} keys: {list(extracted_data.keys())}")
    
    guest_data = {}
    
    # Extract common fields from Textract data
    textract_fields = {
        'first_name': 'given_name',
        'last_name': 'surname', 
        'full_name': 'name',
        'date_of_birth': 'date_of_birth',
        'gender': 'gender',
        'address': 'address',
        'document_number': 'id_number'
    }
    
    for guest_field, textract_field in textract_fields.items():
        # Try Textract fields first
        textract_key = f"textract_{textract_field}"
        if textract_key in extracted_data:
            guest_data[guest_field] = extracted_data[textract_key]
        
        # Fall back to parsed fields
        parsed_key = f"parsed_{textract_field}"
        if parsed_key in extracted_data and guest_field not in guest_data:
            guest_data[guest_field] = extracted_data[parsed_key]
        
        # Direct field lookup
        if textract_field in extracted_data and guest_field not in guest_data:
            guest_data[guest_field] = extracted_data[textract_field]
    
    # Add document-specific fields
    if document_type.upper() == 'AADHAR':
        if 'parsed_aadhaar_number' in extracted_data:
            guest_data['id_number'] = extracted_data['parsed_aadhaar_number']
    elif document_type.upper() == 'DRIVING_LICENSE':
        if 'parsed_dl_number' in extracted_data:
            guest_data['id_number'] = extracted_data['parsed_dl_number']
        if 'parsed_valid_till' in extracted_data:
            guest_data['id_expiry'] = extracted_data['parsed_valid_till']
    elif document_type.upper() == 'PASSPORT':
        if 'parsed_passport_number' in extracted_data:
            guest_data['id_number'] = extracted_data['parsed_passport_number']
        if 'parsed_date_of_expiry' in extracted_data:
            guest_data['id_expiry'] = extracted_data['parsed_date_of_expiry']
    
    # Add document type
    guest_data['document_type'] = document_type
    
    # Clean up names
    if 'full_name' in guest_data and isinstance(guest_data['full_name'], str):
        guest_data['full_name'] = guest_data['full_name'].strip().title()
    
    # Debug: Log final structured guest data
    logger.info(f"DEBUG: Final structured guest_data: {guest_data}")
    
    return guest_data


def _extract_text_from_textract_data(textract_data: Dict[str, Any]) -> str:
    """
    Extract raw text from Textract structured data.
    
    Args:
        textract_data: Structured data from Textract
        
    Returns:
        Raw text string
    """
    text_parts = []
    
    for key, value in textract_data.items():
        if isinstance(value, str):
            text_parts.append(f"{key}: {value}")
        elif isinstance(value, dict) and 'value' in value:
            text_parts.append(f"{key}: {value['value']}")
    
    return '\n'.join(text_parts)


def _update_guest_record(guest_session: GuestSession, guest_data: Dict[str, Any], document_type: str):
    """
    Update or create guest record with extracted data.
    
    Args:
        guest_session: Guest session instance
        guest_data: Extracted guest data
        document_type: Type of document processed
    """
    try:
        # Try to find existing guest by phone number
        guest = Guest.objects.filter(whatsapp_number=guest_session.phone_number).first()
        
        if not guest:
            # Create new guest
            guest = Guest.objects.create(
                whatsapp_number=guest_session.phone_number,
                full_name=guest_data.get('full_name', ''),
                date_of_birth=guest_data.get('date_of_birth'),
                nationality=guest_data.get('nationality', ''),
                # Note: Guest model doesn't have first_name, last_name, gender, address, id_type, id_number, id_expiry, created_at fields
            )
            logger.info(f"_update_guest_record: Created new guest {guest.id} for session {guest_session.id}")
        else:
            # Update existing guest with new data
            if 'full_name' in guest_data:
                guest.full_name = guest_data['full_name']
            if 'date_of_birth' in guest_data:
                guest.date_of_birth = guest_data['date_of_birth']
            if 'nationality' in guest_data:
                guest.nationality = guest_data['nationality']
            
            # Note: Guest model doesn't have first_name, last_name, gender, address, id_type, id_number, id_expiry, updated_at fields
            # Only update fields that exist in the model
            guest.save(update_fields=['full_name', 'date_of_birth', 'nationality'])
            logger.info(f"_update_guest_record: Updated existing guest {guest.id} for session {guest_session.id}")
        
        # Link guest to session
        guest_session.guest = guest
        guest_session.save(update_fields=['guest'])
        
    except Exception as e:
        logger.error(f"_update_guest_record: Error updating guest record: {e}", exc_info=True)


# WhatsApp messaging functions removed - notifications handled by checkin flow


def _continue_checkin_flow_after_ocr(guest_session: GuestSession, guest_data: Dict[str, Any]):
    """
    Continue the checkin flow after successful OCR processing.
    
    This would typically trigger the next step in the checkin process,
    such as showing the confirmation message or proceeding to room selection.
    
    Args:
        guest_session: Guest session instance
        guest_data: Extracted guest data
    """
    try:
        # Update session data to indicate OCR completion
        session_data = guest_session.session_data or {}
        session_data['ocr_completed'] = True
        session_data['current_step'] = 'guest_confirmation'
        session_data['extracted_guest_data'] = guest_data
        
        guest_session.session_data = session_data
        guest_session.save(update_fields=['session_data'])
        
        # The checkin flow controller will pick up from here
        # based on the current_step in session_data
        
    except Exception as e:
        logger.error(f"_continue_checkin_flow_after_ocr: Error continuing checkin flow: {e}", exc_info=True)