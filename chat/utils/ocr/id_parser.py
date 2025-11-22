import re
import logging

logger = logging.getLogger(__name__)


class IndianIDParser:
    """
    Simple parser for extracting text from Indian ID documents.
    This parser is completely independent and doesn't use any models.
    It just takes text input and returns structured data.
    """

    @staticmethod
    def detect_document_type(text):
        """Detect which Indian ID document this is based on text content."""
        text_upper = text.upper()

        if 'AADHAAR' in text_upper or 'UIDAI' in text_upper:
            return 'AADHAAR'
        elif 'DRIVING LICENCE' in text_upper or 'DRIVING LICENSE' in text_upper:
            return 'DRIVING_LICENSE'
        elif 'ELECTION COMMISSION' in text_upper or 'VOTER' in text_upper or 'EPIC' in text_upper:
            return 'VOTER_ID'
        elif 'INCOME TAX' in text_upper or 'PERMANENT ACCOUNT NUMBER' in text_upper:
            return 'PAN'
        elif 'PASSPORT' in text_upper or 'REPUBLIC OF INDIA' in text_upper:
            return 'PASSPORT'

        return 'UNKNOWN'

    @staticmethod
    def parse_aadhaar(text):
        """Parse Aadhaar Card to extract relevant fields."""
        fields = {}

        # Aadhaar number (12 digits with spaces)
        aadhaar_match = re.search(r'\b(\d{4}\s\d{4}\s\d{4})\b', text)
        if aadhaar_match:
            fields['aadhaar_number'] = aadhaar_match.group(1).replace(' ', '')

        # Name
        name_match = re.search(r'(?:Name[:\s]*|^)([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)', text, re.MULTILINE)
        if name_match:
            fields['name'] = name_match.group(1).strip()

        # Date of Birth / Year of Birth
        dob_match = re.search(r'(?:DOB|Birth|YOB)[:\s]*(\d{2}[/-]\d{2}[/-]\d{4}|\d{4})', text, re.IGNORECASE)
        if dob_match:
            fields['dob'] = dob_match.group(1)

        # Gender
        gender_match = re.search(r'\b(Male|Female|MALE|FEMALE|M|F)\b', text)
        if gender_match:
            fields['gender'] = gender_match.group(1).upper()

        # Address
        address_match = re.search(r'(?:Address[:\s]*)?([A-Z0-9][^\n]+(?:\n[A-Z0-9][^\n]+)*?)(?=\d{4}\s\d{4}\s\d{4}|$)', text, re.IGNORECASE)
        if address_match:
            fields['address'] = address_match.group(1).strip()

        fields['document_type'] = 'AADHAAR'
        return fields

    @staticmethod
    def parse_driving_license(text):
        """Parse Driving License to extract relevant fields."""
        fields = {}

        # DL Number
        dl_match = re.search(r'([A-Z]{2}[-\s]?\d{2}[-\s]?\d{4}[-\s]?\d{7})', text)
        if dl_match:
            fields['dl_number'] = dl_match.group(1).replace(' ', '').replace('-', '')

        # Name
        name_match = re.search(r'(?:Name[:\s]*)([A-Z][A-Z\s]+?)(?=\n|DOB|S/O|D/O|W/O)', text, re.IGNORECASE)
        if name_match:
            fields['name'] = name_match.group(1).strip()

        # Father's/Husband's name
        parent_match = re.search(r'(?:S/O|D/O|W/O)[:\s]*([A-Z][A-Z\s]+?)(?=\n|DOB)', text, re.IGNORECASE)
        if parent_match:
            fields['parent_name'] = parent_match.group(1).strip()

        # Date of Birth
        dob_match = re.search(r'(?:DOB|Birth)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        if dob_match:
            fields['dob'] = dob_match.group(1)

        # Date of Issue
        doi_match = re.search(r'(?:DOI|Issue)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        if doi_match:
            fields['date_of_issue'] = doi_match.group(1)

        # Valid Till
        valid_match = re.search(r'(?:Valid Till|Validity)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        if valid_match:
            fields['valid_till'] = valid_match.group(1)

        # Blood Group
        blood_match = re.search(r'\b(A\+|A-|B\+|B-|AB\+|AB-|O\+|O-)\b', text)
        if blood_match:
            fields['blood_group'] = blood_match.group(1)

        # Address
        address_match = re.search(r'(?:Address[:\s]*)(.+?)(?=\n(?:DOB|DL|Vehicle)|\Z)', text, re.IGNORECASE | re.DOTALL)
        if address_match:
            fields['address'] = ' '.join(address_match.group(1).split())

        fields['document_type'] = 'DRIVING_LICENSE'
        return fields

    @staticmethod
    def parse_voter_id(text):
        """Parse Voter ID (EPIC) to extract relevant fields."""
        fields = {}

        # EPIC Number
        epic_match = re.search(r'\b([A-Z]{3}\d{7})\b', text)
        if epic_match:
            fields['epic_number'] = epic_match.group(1)

        # Name
        name_match = re.search(r'(?:Name[:\s]*)([A-Z][A-Z\s]+?)(?=\n|Father|Husband|House)', text, re.IGNORECASE)
        if name_match:
            fields['name'] = name_match.group(1).strip()

        # Father's/Husband's name
        parent_match = re.search(r'(?:Father|Husband)[\'s\s]*Name[:\s]*([A-Z][A-Z\s]+?)(?=\n|House|Age)', text, re.IGNORECASE)
        if parent_match:
            fields['parent_name'] = parent_match.group(1).strip()

        # Date of Birth / Age
        dob_match = re.search(r'(?:DOB|Birth)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        if dob_match:
            fields['dob'] = dob_match.group(1)
        else:
            age_match = re.search(r'Age[:\s]*(\d{2})', text, re.IGNORECASE)
            if age_match:
                fields['age'] = age_match.group(1)

        # Gender
        gender_match = re.search(r'\b(Male|Female|MALE|FEMALE)\b', text)
        if gender_match:
            fields['gender'] = gender_match.group(1).upper()

        # Address/House Number
        house_match = re.search(r'(?:House No|Address)[:\s.]*(.+?)(?=\n[A-Z]{3}|\Z)', text, re.IGNORECASE | re.DOTALL)
        if house_match:
            fields['address'] = ' '.join(house_match.group(1).split())

        fields['document_type'] = 'VOTER_ID'
        return fields

    @staticmethod
    def parse_pan(text):
        """Parse PAN Card to extract relevant fields."""
        fields = {}

        # PAN Number
        pan_match = re.search(r'\b([A-Z]{5}\d{4}[A-Z])\b', text)
        if pan_match:
            fields['pan_number'] = pan_match.group(1)

        # Name
        name_match = re.search(r'(?:Name[:\s]*)([A-Z][A-Z\s]+?)(?=\n|Father|Date)', text, re.IGNORECASE)
        if name_match:
            fields['name'] = name_match.group(1).strip()

        # Father's Name
        father_match = re.search(r'(?:Father)[\'s\s]*Name[:\s]*([A-Z][A-Z\s]+?)(?=\n|Date)', text, re.IGNORECASE)
        if father_match:
            fields['father_name'] = father_match.group(1).strip()

        # Date of Birth
        dob_match = re.search(r'(?:DOB|Birth)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        if dob_match:
            fields['dob'] = dob_match.group(1)

        fields['document_type'] = 'PAN'
        return fields

    @staticmethod
    def parse_passport(text):
        """Parse Indian Passport to extract relevant fields."""
        fields = {}

        # Passport Number
        passport_match = re.search(r'\b([A-Z]\d{7})\b', text)
        if passport_match:
            fields['passport_number'] = passport_match.group(1)

        # Surname
        surname_match = re.search(r'(?:Surname|Sur Name)[:\s]*([A-Z]+)', text, re.IGNORECASE)
        if surname_match:
            fields['surname'] = surname_match.group(1).strip()

        # Given Name
        given_match = re.search(r'(?:Given Name|Name)[:\s]*([A-Z][A-Z\s]+?)(?=\n|Sex|Date)', text, re.IGNORECASE)
        if given_match:
            fields['given_name'] = given_match.group(1).strip()

        # Date of Birth
        dob_match = re.search(r'(?:DOB|Birth|Date of Birth)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        if dob_match:
            fields['dob'] = dob_match.group(1)

        # Place of Birth
        pob_match = re.search(r'(?:Place of Birth|POB)[:\s]*([A-Z][A-Za-z\s]+?)(?=\n|Date)', text, re.IGNORECASE)
        if pob_match:
            fields['place_of_birth'] = pob_match.group(1).strip()

        # Date of Issue
        doi_match = re.search(r'(?:Date of Issue|Issue)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        if doi_match:
            fields['date_of_issue'] = doi_match.group(1)

        # Date of Expiry
        doe_match = re.search(r'(?:Date of Expiry|Expiry)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        if doe_match:
            fields['date_of_expiry'] = doe_match.group(1)

        # Place of Issue
        poi_match = re.search(r'(?:Place of Issue)[:\s]*([A-Z][A-Za-z\s]+?)(?=\n|File)', text, re.IGNORECASE)
        if poi_match:
            fields['place_of_issue'] = poi_match.group(1).strip()

        # Gender/Sex
        gender_match = re.search(r'(?:Sex)[:\s]*(M|F|Male|Female)', text, re.IGNORECASE)
        if gender_match:
            fields['gender'] = gender_match.group(1).upper()

        # File Number
        file_match = re.search(r'(?:File No)[:\s]*([A-Z0-9]+)', text, re.IGNORECASE)
        if file_match:
            fields['file_number'] = file_match.group(1)

        fields['document_type'] = 'PASSPORT'
        return fields

    @staticmethod
    def parse(text):
        """
        Auto-detect and parse Indian ID document.
        
        Args:
            text: Raw text extracted from ID document
            
        Returns:
            Dictionary with parsed fields and document type
        """
        doc_type = IndianIDParser.detect_document_type(text)
        
        # Debug logging for document type detection
        logger.info(f"ID Parser detected document type: {doc_type}")
        logger.info(f"ID Parser input text length: {len(text)} characters")
        logger.info(f"ID Parser input text preview: {text[:200]}...")

        if doc_type == 'AADHAAR':
            parsed_data = IndianIDParser.parse_aadhaar(text)
        elif doc_type == 'DRIVING_LICENSE':
            parsed_data = IndianIDParser.parse_driving_license(text)
        elif doc_type == 'VOTER_ID':
            parsed_data = IndianIDParser.parse_voter_id(text)
        elif doc_type == 'PAN':
            parsed_data = IndianIDParser.parse_pan(text)
        elif doc_type == 'PASSPORT':
            parsed_data = IndianIDParser.parse_passport(text)
        else:
            parsed_data = {
                'document_type': 'UNKNOWN',
                'raw_text': text
            }
        
        # Debug logging for parsed results
        logger.info(f"ID Parser extracted {len(parsed_data)} fields")
        logger.info(f"ID Parser extracted fields: {list(parsed_data.keys())}")
        logger.info(f"ID Parser parsed data: {parsed_data}")
        
        return parsed_data

    @staticmethod
    def parse_with_type(text, document_type):
        """
        Parse Indian ID document using the provided document type.
        
        Args:
            text: Raw text extracted from ID document
            document_type: The document type provided by the user (from models.GuestIdentityDocument)
            
        Returns:
            Dictionary with parsed fields and document type
        """
        # Convert frontend document types to parser document types
        type_mapping = {
            'aadhar_id': 'AADHAAR',
            'driving_license': 'DRIVING_LICENSE', 
            'voter_id': 'VOTER_ID',
            'national_id': 'UNKNOWN',  # Will need to be handled based on the actual document
            'other': 'UNKNOWN'
        }
        
        doc_type = type_mapping.get(document_type, 'UNKNOWN')
        
        # Debug logging for document type
        logger.info(f"ID Parser using provided document type: {document_type} -> {doc_type}")
        logger.info(f"ID Parser input text length: {len(text)} characters")
        logger.info(f"ID Parser input text preview: {text[:200]}...")

        if doc_type == 'AADHAAR':
            parsed_data = IndianIDParser.parse_aadhaar(text)
        elif doc_type == 'DRIVING_LICENSE':
            parsed_data = IndianIDParser.parse_driving_license(text)
        elif doc_type == 'VOTER_ID':
            parsed_data = IndianIDParser.parse_voter_id(text)
        elif doc_type == 'PAN':
            parsed_data = IndianIDParser.parse_pan(text)
        elif doc_type == 'PASSPORT':
            parsed_data = IndianIDParser.parse_passport(text)
        else:
            # For unknown types, try to auto-detect as fallback
            logger.info(f"Unknown or unsupported document type {document_type}, attempting auto-detection")
            parsed_data = IndianIDParser.parse(text)
        
        # Debug logging for parsed results
        logger.info(f"ID Parser extracted {len(parsed_data)} fields")
        logger.info(f"ID Parser extracted fields: {list(parsed_data.keys())}")
        logger.info(f"ID Parser parsed data: {parsed_data}")
        
        return parsed_data


def extract_text_from_ocr_result(ocr_result):
    """
    Extract text from OCR result.
    
    Args:
        ocr_result: Result from OCR service containing extracted text
        
    Returns:
        Raw text string or None if extraction fails
    """
    if not ocr_result or not isinstance(ocr_result, dict):
        logger.error("OCR result is not a valid dictionary")
        return None
        
    if not ocr_result.get('success', False):
        logger.error(f"OCR processing failed: {ocr_result.get('error', 'Unknown error')}")
        return None
        
    # Extract text from different possible OCR result formats
    if 'text' in ocr_result:
        return ocr_result['text']
    elif 'data' in ocr_result and 'full_text' in ocr_result['data']:
        return ocr_result['data']['full_text']
    elif 'data' in ocr_result and isinstance(ocr_result['data'], dict):
        # Try to extract text from structured data
        text_parts = []
        for key, value in ocr_result['data'].items():
            if isinstance(value, dict) and 'value' in value:
                text_parts.append(f"{key}: {value['value']}")
            elif isinstance(value, str):
                text_parts.append(value)
        return '\n'.join(text_parts)
    
    logger.error("Could not extract text from OCR result")
    return None


def get_document_type(text):
    """
    Simple function to detect document type from text.
    
    Args:
        text: Raw text extracted from an ID document
        
    Returns:
        String representing document type or 'UNKNOWN'
    """
    return IndianIDParser.detect_document_type(text)