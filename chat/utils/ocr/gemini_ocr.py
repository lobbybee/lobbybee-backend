"""
Gemini-based OCR service for ID document extraction.
Simple, AI-powered - no regex, no complex parsing.
"""

import logging
import json
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.files.storage import default_storage
import google.generativeai as genai
from PIL import Image
import io

logger = logging.getLogger(__name__)


class GeminiOCRService:
    """
    Simple Gemini-based OCR for Indian ID documents.
    Pass image + document type → Get structured JSON back.
    """

    # Document type mapping for better prompts
    DOCUMENT_TYPES = {
        'AADHAR': 'Indian Aadhaar Card',
        'AADHAAR': 'Indian Aadhaar Card',
        'DRIVING_LICENSE': 'Indian Driving License',
        'PASSPORT': 'Passport',
        'VOTER_ID': 'Indian Voter ID (EPIC)',
        'PAN': 'Indian PAN Card',
        'NATIONAL_ID': 'Indian National ID Card',
    }

    def __init__(self):
        """Initialize Gemini client."""
        api_key = getattr(settings, 'GOOGLE_GEMINI_API_KEY', None)
        if not api_key:
            logger.error("GeminiOCRService: GOOGLE_GEMINI_API_KEY not configured")
            self.model = None
            return

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-flash-latest')
            logger.info("GeminiOCRService: Successfully initialized Gemini Flash")
        except Exception as e:
            logger.error(f"GeminiOCRService: Failed to initialize: {e}")
            self.model = None

    def _load_image(self, image_path: str) -> Optional[Image.Image]:
        """
        Load image from Django storage or local path.

        Args:
            image_path: Path to image (Django storage path or local file path)

        Returns:
            PIL Image object or None if loading fails
        """
        try:
            # Check if it's a Django storage path (doesn't start with /)
            if not image_path.startswith('/'):
                # Load from Django storage (S3, local storage, etc.)
                image_file = default_storage.open(image_path)
                image_data = image_file.read()
                return Image.open(io.BytesIO(image_data))
            else:
                # Local file path
                return Image.open(image_path)
        except Exception as e:
            logger.error(f"GeminiOCRService: Failed to load image from {image_path}: {e}")
            return None

    def extract_id_data(
        self,
        image_path: str,
        document_type: str = None,
        back_image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from ID document using Gemini 3.
        If document_type is None, will auto-detect the type first.

        Args:
            image_path: Path to front image of ID document
            document_type: Type of document (AADHAR, DRIVING_LICENSE, etc.) - optional
            back_image_path: Optional path to back side of document

        Returns:
            Dictionary with:
                - success: bool
                - data: dict with extracted fields
                - api_used: str
                - processing_method: str
                - error: str (only if success=False)
        """
        if not self.model:
            return {
                'success': False,
                'error': 'Gemini client not initialized. Check GOOGLE_GEMINI_API_KEY in settings.',
                'data': {}
            }

        try:
            # Load the front image
            front_image = self._load_image(image_path)
            if not front_image:
                return {
                    'success': False,
                    'error': f'Failed to load front image: {image_path}',
                    'data': {}
                }

            # Create prompt that handles both detection and extraction
            if document_type:
                # Document type is known, use specific extraction
                doc_type_upper = document_type.upper()
                doc_type_desc = self.DOCUMENT_TYPES.get(
                    doc_type_upper,
                    f"{document_type} ID document"
                )
                prompt = self._create_extraction_prompt(doc_type_upper, doc_type_desc)
            else:
                # Auto-detect and extract in one go
                prompt = """You are an expert at identifying and extracting information from Indian ID documents.

FIRST: Identify what type of ID document this is from:
- aadhar_id: Indian Aadhaar Card (has Aadhaar logo, 12-digit number)
- driving_license: Indian Driving License (has "Driving License" text, state name)
- national_id: Any other national ID card
- voter_id: Indian Voter ID Card (EPIC)
- other: Any other government ID

THEN: Extract ALL visible information based on the identified document type.

Return ONLY a valid JSON object with these fields:
{
    "detected_type": "one of: aadhar_id, driving_license, national_id, voter_id, other",
    "confidence": 0.95,
    "id_number": "the ID/document number",
    "full_name": "complete name exactly as shown",
    "date_of_birth": "date of birth in DD/MM/YYYY format",
    "gender": "MALE or FEMALE or null",
    "address": "complete address if present",
    "expiry_date": "expiry/validity date in DD/MM/YYYY format if present",
    "issue_date": "issue date in DD/MM/YYYY format if present"
}

For Aadhaar Card specifically:
- The Aadhaar number is a 12-digit number (format: XXXX XXXX XXXX)
- Remove spaces from the Aadhaar number in your response
- Look for "DOB" or "Year of Birth" for date_of_birth

For Driving License specifically:
- DL Number format is typically: XX-XXXXXXXXXX or XX00XXXX0000000
- Look for "DOB" for date of birth
- "Valid Till" or "NT Valid Till" is the expiry_date

CRITICAL RULES:
1. Extract EXACTLY what you see - don't invent or guess information
2. Use DD/MM/YYYY format for all dates when possible
3. Return ONLY the JSON object - no markdown formatting
4. If text is unclear or missing, use null for that field
5. Preserve the exact spelling and capitalization of names
6. Remove spaces from ID numbers (e.g., "1234 5678 9012" becomes "123456789012")

Return the JSON now:"""

            # Prepare content for API call
            content = [prompt, front_image]

            # Add back image if provided
            if back_image_path:
                back_image = self._load_image(back_image_path)
                if back_image:
                    content.append("\n\nHere is the BACK side of the document:")
                    content.append(back_image)
                    logger.info(f"GeminiOCRService: Processing both front and back images")

            # Call Gemini API
            logger.info(f"GeminiOCRService: Extracting data from document" + 
                       (f" (type: {document_type})" if document_type else " (auto-detecting type)"))
            response = self.model.generate_content(
                content,
                generation_config={
                    'temperature': 0.1,  # Low temperature for consistent extraction
                    'max_output_tokens': 2048,
                }
            )

            # Parse the response
            response_text = response.text.strip()
            logger.debug(f"GeminiOCRService: Raw response: {response_text[:200]}...")

            # Clean up response - remove markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Remove last line if it's ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                response_text = '\n'.join(lines).strip()

            # Parse JSON
            extracted_data = json.loads(response_text)

            # Add document type to extracted data if not auto-detected
            if document_type and 'detected_type' not in extracted_data:
                extracted_data['detected_type'] = document_type.lower()
                extracted_data['confidence'] = 1.0  # High confidence for specified type
            elif 'document_type' in extracted_data and 'detected_type' not in extracted_data:
                # Backward compatibility
                extracted_data['detected_type'] = extracted_data.get('document_type', '').lower()
                extracted_data['confidence'] = 1.0

            logger.info(f"GeminiOCRService: Successfully extracted {len(extracted_data)} fields")
            if 'detected_type' in extracted_data:
                logger.info(f"GeminiOCRService: Detected type: {extracted_data['detected_type']}")
            logger.debug(f"GeminiOCRService: Extracted data: {extracted_data}")

            return {
                'success': True,
                'data': extracted_data,
                'api_used': 'gemini-3-pro',
                'processing_method': 'ai_vision'
            }

        except json.JSONDecodeError as e:
            logger.error(f"GeminiOCRService: Failed to parse JSON response: {e}")
            logger.error(f"GeminiOCRService: Raw response was: {response_text}")
            return {
                'success': False,
                'error': f'Invalid JSON response from Gemini: {str(e)}',
                'data': {},
                'raw_response': response_text[:500]  # Include snippet for debugging
            }
        except Exception as e:
            logger.error(f"GeminiOCRService: Extraction failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Gemini extraction error: {str(e)}',
                'data': {}
            }

    def _create_extraction_prompt(self, doc_type: str, doc_type_desc: str) -> str:
        """
        Create extraction prompt based on document type.

        Args:
            doc_type: Document type code (AADHAR, DRIVING_LICENSE, etc.)
            doc_type_desc: Human-readable document description

        Returns:
            Formatted prompt string
        """
        base_prompt = f"""You are an expert at extracting information from Indian ID documents.

Analyze this {doc_type_desc} image carefully and extract ALL visible information.

Return ONLY a valid JSON object with these fields (use null for any missing/unreadable fields):
{{
    "id_number": "the ID/document number (Aadhaar number, DL number, Passport number, etc.)",
    "full_name": "complete name exactly as shown on document",
    "date_of_birth": "date of birth in DD/MM/YYYY format (or YYYY if only year is shown)",
    "gender": "MALE or FEMALE or null",
    "address": "complete address if present",
    "expiry_date": "expiry/validity date in DD/MM/YYYY format if present",
    "issue_date": "issue date in DD/MM/YYYY format if present"
}}"""

        # Add document-specific instructions
        if doc_type in ['AADHAR', 'AADHAAR']:
            base_prompt += """

For Aadhaar Card specifically:
- The Aadhaar number is a 12-digit number (format: XXXX XXXX XXXX)
- Remove spaces from the Aadhaar number in your response
- Look for "DOB" or "Year of Birth" for date_of_birth
- Gender is usually shown as "Male"/"Female" or "M"/"F"
"""
        elif doc_type == 'DRIVING_LICENSE':
            base_prompt += """

For Driving License specifically:
- DL Number format is typically: XX-XXXXXXXXXX or XX00XXXX0000000
- Look for "DOB" for date of birth
- "Valid Till" or "NT Valid Till" is the expiry_date
- "DOI" or "Date of Issue" is the issue_date
"""
        elif doc_type == 'PASSPORT':
            base_prompt += """

For Passport specifically:
- Passport number is usually 8 characters (1 letter + 7 digits)
- Look for "Surname" and "Given Name(s)" - combine them for full_name
- "Date of Birth" is clearly labeled
- "Date of Issue" and "Date of Expiry" are on the document
"""
        elif doc_type == 'PAN':
            base_prompt += """

For PAN Card specifically:
- PAN number is 10 characters (5 letters + 4 digits + 1 letter)
- Look for name below PAN number
- Father's name is usually shown
- Date of birth is typically shown
"""

        base_prompt += """

CRITICAL RULES:
1. Extract EXACTLY what you see - don't invent or guess information
2. Use DD/MM/YYYY format for all dates when possible
3. Return ONLY the JSON object - no markdown formatting, no explanations
4. If text is unclear or missing, use null for that field
5. Preserve the exact spelling and capitalization of names
6. Remove spaces from ID numbers (e.g., "1234 5678 9012" becomes "123456789012")

Return the JSON now:"""

        return base_prompt


# Create singleton instance
gemini_ocr_service = GeminiOCRService()


def extract_id_document(
    image_path: str,
    document_type: str = None,
    back_image_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Simple function to extract ID document data using Gemini.
    If document_type is None, will auto-detect the type.

    Args:
        image_path: Path to front image
        document_type: Document type (AADHAR, DRIVING_LICENSE, etc.) - optional
        back_image_path: Optional path to back image

    Returns:
        Dictionary with extracted data:
        {
            'success': bool,
            'data': {
                'id_number': str,
                'full_name': str,
                'date_of_birth': str,
                'gender': str,
                'address': str,
                ...
                'detected_type': str,  # Auto-detected type
                'confidence': float,  # Detection confidence
            },
            'api_used': str,
            'processing_method': str
        }
    """
    return gemini_ocr_service.extract_id_data(
        image_path,
        document_type,
        back_image_path
    )


def extract_text_from_image(image_path: str) -> str:
    """
    Simple function to extract just raw text from an image.
    Uses Gemini for text extraction.

    Args:
        image_path: Path to image

    Returns:
        Extracted text as string

    Raises:
        ValueError: If extraction fails
    """
    if not gemini_ocr_service.model:
        raise ValueError("Gemini client not initialized")

    try:
        # Load image
        image = gemini_ocr_service._load_image(image_path)
        if not image:
            raise ValueError(f"Failed to load image: {image_path}")

        # Simple prompt for text extraction
        prompt = "Extract all text from this image. Return only the text, preserving line breaks."

        # Call Gemini
        response = gemini_ocr_service.model.generate_content(
            [prompt, image],
            generation_config={'temperature': 0.1}
        )

        return response.text.strip()

    except Exception as e:
        logger.error(f"extract_text_from_image: Failed to extract text: {e}")
        raise ValueError(f"Text extraction failed: {str(e)}")


def detect_document_type(image_path: str) -> Dict[str, Any]:
    """
    Detect document type using AI without requiring manual selection.

    Args:
        image_path: Path to image of ID document

    Returns:
        Dictionary with detected document type:
        {
            'success': bool,
            'document_type': str,  # One of: aadhar_id, driving_license, national_id, voter_id, other
            'confidence': float,  # 0-1 confidence score
            'error': str (only if success=False)
        }
    """
    if not gemini_ocr_service.model:
        return {
            'success': False,
            'error': 'Gemini client not initialized',
            'document_type': None,
            'confidence': 0
        }

    try:
        # Load image
        image = gemini_ocr_service._load_image(image_path)
        if not image:
            return {
                'success': False,
                'error': f'Failed to load image: {image_path}',
                'document_type': None,
                'confidence': 0
            }

        # Create prompt for document type detection
        prompt = """You are an expert at identifying Indian government ID documents.

Analyze this image and determine what type of ID document it is.

Respond with ONLY a valid JSON object in this format:
{
    "document_type": "one of: aadhar_id, driving_license, national_id, voter_id, other",
    "confidence": 0.95,
    "reasoning": "Brief explanation of why you identified it this way"
}

Valid document types:
- aadhar_id: Indian Aadhaar Card (has Aadhaar logo, 12-digit number)
- driving_license: Indian Driving License (has "Driving License" text, state name)
- national_id: Any other national ID card
- voter_id: Indian Voter ID Card (EPIC)
- other: Any other government ID not listed above

Look for:
- Official logos and emblems
- Document titles and headings
- Unique identification number formats
- Issuing authority information

Return the JSON now:"""

        # Call Gemini
        response = gemini_ocr_service.model.generate_content(
            [prompt, image],
            generation_config={
                'temperature': 0.1,  # Low temperature for consistent results
                'max_output_tokens': 500,
            }
        )

        # Parse response
        response_text = response.text.strip()
        
        # Clean up response - remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response_text = '\n'.join(lines).strip()

        # Parse JSON
        result = json.loads(response_text)
        
        # Validate document_type
        valid_types = ['aadhar_id', 'driving_license', 'national_id', 'voter_id', 'other']
        doc_type = result.get('document_type', 'other')
        if doc_type not in valid_types:
            doc_type = 'other'
        
        # Validate confidence
        confidence = float(result.get('confidence', 0))
        confidence = max(0, min(1, confidence))  # Clamp between 0 and 1

        logger.info(f"GeminiOCRService: Detected document type '{doc_type}' with confidence {confidence}")

        return {
            'success': True,
            'document_type': doc_type,
            'confidence': confidence,
            'reasoning': result.get('reasoning', '')
        }

    except json.JSONDecodeError as e:
        logger.error(f"GeminiOCRService: Failed to parse JSON response: {e}")
        return {
            'success': False,
            'error': 'Invalid response from AI',
            'document_type': None,
            'confidence': 0
        }
    except Exception as e:
        logger.error(f"GeminiOCRService: Document type detection failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'document_type': None,
            'confidence': 0
        }
