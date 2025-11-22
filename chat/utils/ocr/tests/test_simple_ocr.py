"""
Simple tests for the simplified OCR service.

These tests verify that the OCR functions work correctly without model dependencies.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

# Import the functions we want to test
from chat.utils.ocr.id_parser import (
    IndianIDParser, 
    get_document_type,
    extract_text_from_ocr_result
)
from chat.utils.ocr.ocr_service import (
    TextractOCRService,
    extract_text
)


class TestIndianIDParser(unittest.TestCase):
    """Test the Indian ID parser functions."""
    
    def test_detect_document_type_aadhaar(self):
        """Test detection of Aadhaar card."""
        text = "Aadhaar Card Government of India 1234 5678 9012 Name: John Doe DOB: 01/01/1990"
        doc_type = IndianIDParser.detect_document_type(text)
        self.assertEqual(doc_type, 'AADHAAR')
    
    def test_detect_document_type_driving_license(self):
        """Test detection of Driving License."""
        text = "Driving License DL-0420110012345 Name: John Doe DOB: 01/01/1990"
        doc_type = IndianIDParser.detect_document_type(text)
        self.assertEqual(doc_type, 'DRIVING_LICENSE')
    
    def test_detect_document_type_voter_id(self):
        """Test detection of Voter ID."""
        text = "Election Commission of India Voter ID ABC1234567 Name: John Doe"
        doc_type = IndianIDParser.detect_document_type(text)
        self.assertEqual(doc_type, 'VOTER_ID')
    
    def test_detect_document_type_pan(self):
        """Test detection of PAN card."""
        text = "Income Tax Department PAN ABCDE1234F Name: John Doe DOB: 01/01/1990"
        doc_type = IndianIDParser.detect_document_type(text)
        self.assertEqual(doc_type, 'PAN')
    
    def test_detect_document_type_passport(self):
        """Test detection of Passport."""
        text = "Republic of India Passport A1234567 Surname: DOE Given Name: JOHN"
        doc_type = IndianIDParser.detect_document_type(text)
        self.assertEqual(doc_type, 'PASSPORT')
    
    def test_detect_document_type_unknown(self):
        """Test detection of unknown document type."""
        text = "Some random text without any known document type keywords"
        doc_type = IndianIDParser.detect_document_type(text)
        self.assertEqual(doc_type, 'UNKNOWN')
    
    def test_parse_aadhaar(self):
        """Test parsing of Aadhaar card details."""
        text = "Aadhaar Card 1234 5678 9012 Name: John Doe DOB: 01/01/1990 Gender: Male Address: 123 Street, City"
        parsed = IndianIDParser.parse_aadhaar(text)
        
        self.assertEqual(parsed.get('document_type'), 'AADHAAR')
        self.assertEqual(parsed.get('aadhaar_number'), '123456789012')
        self.assertEqual(parsed.get('name'), 'John Doe')
        self.assertEqual(parsed.get('dob'), '01/01/1990')
        self.assertEqual(parsed.get('gender'), 'MALE')
    
    def test_parse_driving_license(self):
        """Test parsing of Driving License details."""
        text = "Driving License HR-0619850034761 Name: John Doe DOB: 01/01/1990 Valid Till: 01/01/2030"
        parsed = IndianIDParser.parse_driving_license(text)
        
        self.assertEqual(parsed.get('document_type'), 'DRIVING_LICENSE')
        self.assertEqual(parsed.get('dl_number'), 'HR0619850034761')
        self.assertEqual(parsed.get('name'), 'John Doe')
        self.assertEqual(parsed.get('dob'), '01/01/1990')
        self.assertEqual(parsed.get('valid_till'), '01/01/2030')
    
    def test_get_document_type(self):
        """Test the get_document_type helper function."""
        text = "Aadhaar Card Government of India 1234 5678 9012"
        doc_type = get_document_type(text)
        self.assertEqual(doc_type, 'AADHAAR')
    
    def test_extract_text_from_ocr_result(self):
        """Test extraction of text from OCR result."""
        # Test with text field
        ocr_result = {
            'success': True,
            'text': 'Extracted text from document'
        }
        text = extract_text_from_ocr_result(ocr_result)
        self.assertEqual(text, 'Extracted text from document')
        
        # Test with data.full_text field
        ocr_result = {
            'success': True,
            'data': {
                'full_text': 'Extracted full text from document'
            }
        }
        text = extract_text_from_ocr_result(ocr_result)
        self.assertEqual(text, 'Extracted full text from document')
        
        # Test with structured data
        ocr_result = {
            'success': True,
            'data': {
                'name': {'value': 'John Doe'},
                'age': '30'
            }
        }
        text = extract_text_from_ocr_result(ocr_result)
        self.assertEqual(text, 'name: John Doe\nage')
        
        # Test with failed OCR result
        ocr_result = {
            'success': False,
            'error': 'Processing failed'
        }
        text = extract_text_from_ocr_result(ocr_result)
        self.assertIsNone(text)
        
        # Test with invalid input
        text = extract_text_from_ocr_result(None)
        self.assertIsNone(text)


class TestTextractOCRService(unittest.TestCase):
    """Test the Textract OCR service functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = TextractOCRService()
    
    def test_init(self):
        """Test service initialization."""
        # Just test that it doesn't raise an exception
        service = TextractOCRService()
        self.assertIsNotNone(service)
    
    def test_validate_service_with_client(self):
        """Test service validation with client."""
        # Create a mock client
        service = TextractOCRService()
        service.textract_client = MagicMock()
        
        result = service._validate_service()
        self.assertTrue(result)
    
    def test_validate_service_without_client(self):
        """Test service validation without client."""
        # Create a service with no client
        service = TextractOCRService()
        service.textract_client = None
        
        result = service._validate_service()
        self.assertFalse(result)
    
    def test_preprocess_image(self):
        """Test image preprocessing."""
        result = self.service._preprocess_image("/path/to/image.jpg")
        self.assertEqual(result, "/path/to/image.jpg")
    
    @patch('chat.utils.ocr.ocr_service.default_storage.open')
    def test_download_from_s3(self, mock_open):
        """Test downloading from S3."""
        # Mock the file content
        mock_file = MagicMock()
        mock_file.read.return_value = b'image bytes'
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = self.service._download_from_s3("/path/to/image.jpg")
        self.assertEqual(result, b'image bytes')
    
    @patch('chat.utils.ocr.ocr_service.default_storage.open')
    def test_download_from_s3_exception(self, mock_open):
        """Test downloading from S3 with exception."""
        # Mock an exception
        mock_open.side_effect = Exception("File not found")
        
        result = self.service._download_from_s3("/path/to/image.jpg")
        self.assertIsNone(result)
    
    def test_detect_document_text_no_client(self):
        """Test detect_document_text with no client."""
        # Create a service with no client
        service = TextractOCRService()
        service.textract_client = None
        
        result = service.detect_document_text("/path/to/image.jpg")
        
        self.assertFalse(result.get('success', True))
        self.assertEqual(result.get('error'), 'Textract client not initialized')
        self.assertEqual(result.get('text'), '')
    
    @patch('chat.utils.ocr.ocr_service.extract_text')
    def test_extract_text_function(self, mock_extract):
        """Test the extract_text convenience function."""
        # Mock the service method
        mock_extract.return_value = "Sample text"
        
        # Call the function
        from chat.utils.ocr.ocr_service import extract_text as extract_text_func
        result = extract_text_func("/path/to/image.jpg")
        
        self.assertEqual(result, "Sample text")


if __name__ == '__main__':
    unittest.main()