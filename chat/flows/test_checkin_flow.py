"""
Tests for check-in flow functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from chat.flows.checkin_flow import (
    process_checkin_flow, 
    validate_name, 
    validate_email, 
    validate_dob, 
    validate_nationality, 
    validate_id_type,
    CheckinStep,
    DOCUMENT_TYPES
)

# Model imports
from chat.models import Hotel as ChatHotel, Guest as ChatGuest, Conversation, Message
from guest.models import Guest, GuestIdentityDocument
from hotel.models import Hotel


class TestCheckinFlowValidation(TestCase):
    """Test validation functions."""
    
    def test_validate_name(self):
        """Test name validation."""
        # Valid names
        is_valid, result = validate_name("John Doe")
        self.assertTrue(is_valid)
        self.assertEqual(result, "John Doe")
        
        is_valid, result = validate_name("A B")
        self.assertTrue(is_valid)
        self.assertEqual(result, "A B")
        
        # Invalid names
        is_valid, result = validate_name("A")
        self.assertFalse(is_valid)
        self.assertIn("at least 2 characters", result)
        
        is_valid, result = validate_name("")
        self.assertFalse(is_valid)
        self.assertIn("at least 2 characters", result)
    
    def test_validate_email(self):
        """Test email validation."""
        # Valid emails
        is_valid, result = validate_email("test@example.com")
        self.assertTrue(is_valid)
        self.assertEqual(result, "test@example.com")
        
        is_valid, result = validate_email("user.name+tag@domain.co.uk")
        self.assertTrue(is_valid)
        self.assertEqual(result, "user.name+tag@domain.co.uk")
        
        # Invalid emails
        is_valid, result = validate_email("invalid-email")
        self.assertFalse(is_valid)
        self.assertIn("valid email address", result)
        
        is_valid, result = validate_email("test@")
        self.assertFalse(is_valid)
        self.assertIn("valid email address", result)
    
    def test_validate_dob(self):
        """Test date of birth validation."""
        # Valid dates (person over 18)
        is_valid, parsed_date, error = validate_dob("15/01/1990")
        self.assertTrue(is_valid)
        self.assertEqual(parsed_date, date(1990, 1, 15))
        self.assertEqual(error, "")
        
        is_valid, parsed_date, error = validate_dob("15-01-1990")
        self.assertTrue(is_valid)
        self.assertEqual(parsed_date, date(1990, 1, 15))
        
        # Invalid dates
        is_valid, parsed_date, error = validate_dob("invalid")
        self.assertFalse(is_valid)
        self.assertIsNone(parsed_date)
        self.assertIn("valid date", error)
        
        # Under 18 (assuming current year is 2025)
        is_valid, parsed_date, error = validate_dob("15/01/2020")
        self.assertFalse(is_valid)
        self.assertIsNone(parsed_date)
        self.assertIn("at least 18", error)
    
    def test_validate_nationality(self):
        """Test nationality validation."""
        # Valid nationalities
        is_valid, result = validate_nationality("Indian")
        self.assertTrue(is_valid)
        self.assertEqual(result, "Indian")
        
        # Invalid nationalities
        is_valid, result = validate_nationality("A")
        self.assertFalse(is_valid)
        self.assertIn("valid nationality", result)
    
    def test_validate_id_type(self):
        """Test ID type validation."""
        # Valid ID types
        is_valid, id_type, error = validate_id_type("Driving License")
        self.assertTrue(is_valid)
        self.assertEqual(id_type, "driving_license")
        self.assertEqual(error, "")
        
        is_valid, id_type, error = validate_id_type("National ID")
        self.assertTrue(is_valid)
        self.assertEqual(id_type, "national_id")
        self.assertEqual(error, "")
        
        # Invalid ID types
        is_valid, id_type, error = validate_id_type("invalid")
        self.assertFalse(is_valid)
        self.assertIsNone(id_type)
        self.assertIn("valid ID document", error)


class TestCheckinFlowSteps(TestCase):
    """Test check-in flow steps."""
    
    def setUp(self):
        """Set up test data."""
        # Create test hotel
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            is_active=True,
            status="verified"
        )
        
        # Create test guest
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            status="pending_checkin"
        )
        
        # Create test conversation
        self.conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department="Reception",
            conversation_type="checkin",
            status="active"
        )
    
    def test_fresh_checkin_command_success(self):
        """Test fresh checkin command with valid hotel."""
        flow_data = {
            "whatsapp_number": "+1234567890",
            "message": "/checkin-1"
        }
        
        with patch('hotel.models.Hotel.objects.get') as mock_get_hotel:
            mock_get_hotel.return_value = self.hotel
            
            result = process_checkin_flow(
                guest=None,
                hotel_id=1,
                conversation=None,
                flow_data=flow_data,
                is_fresh_checkin_command=True
            )
            
            self.assertEqual(result["type"], "list")
            self.assertIn("Welcome to Test Hotel", result["text"])
            self.assertIn("Please select your ID document type", result["text"])
    
    def test_fresh_checkin_command_invalid_hotel(self):
        """Test fresh checkin command with invalid hotel."""
        flow_data = {
            "whatsapp_number": "+1234567890",
            "message": "/checkin-999"
        }
        
        with patch('hotel.models.Hotel.objects.get') as mock_get_hotel:
            mock_get_hotel.side_effect = Hotel.DoesNotExist()
            
            result = process_checkin_flow(
                guest=None,
                hotel_id=999,
                conversation=None,
                flow_data=flow_data,
                is_fresh_checkin_command=True
            )
            
            self.assertEqual(result["type"], "text")
            self.assertIn("Invalid hotel code", result["text"])
    
    def test_id_type_step_valid_input(self):
        """Test ID type step with valid input."""
        flow_data = {
            "message": "1",  # AADHAR ID
            "message_id": "msg_123"
        }
        
        # Create a flow message to set current step to ID_TYPE
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please select your ID document type:",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.ID_TYPE
        )
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "list")
        self.assertIn("Please upload an image", result["text"])
        
        # Check if GuestIdentityDocument was created
        doc = GuestIdentityDocument.objects.get(guest=self.guest, is_primary=True)
        self.assertEqual(doc.document_type, "aadhar_id")
    
    def test_name_step_invalid_input(self):
        """Test name step with invalid input."""
        flow_data = {
            "message": "A",  # Too short
            "message_id": "msg_123"
        }
        
        # Create a flow message to set current step to NAME
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please provide your full name:",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.NAME
        )
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "text")
        self.assertIn("at least 2 characters", result["text"])
    
    def test_email_step_valid_input(self):
        """Test email step with valid input."""
        # Set guest name first
        self.guest.full_name = "John Doe"
        self.guest.save()
        
        flow_data = {
            "message": "john@example.com",
            "message_id": "msg_123"
        }
        
        # Create a flow message to set current step to EMAIL
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please provide your email address:",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.EMAIL
        )
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "text")
        self.assertIn("Please provide your date of birth", result["text"])
        
        # Check if guest email was updated
        self.guest.refresh_from_db()
        self.assertEqual(self.guest.email, "john@example.com")
    
    def test_dob_step_valid_input(self):
        """Test date of birth step with valid input."""
        # Set guest name and email first
        self.guest.full_name = "John Doe"
        self.guest.email = "john@example.com"
        self.guest.save()
        
        flow_data = {
            "message": "15/01/1990",
            "message_id": "msg_123"
        }
        
        # Create a flow message to set current step to DOB
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please provide your date of birth:",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.DOB
        )
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "text")
        self.assertIn("Please provide your nationality", result["text"])
        
        # Check if guest DOB was updated
        self.guest.refresh_from_db()
        self.assertEqual(self.guest.date_of_birth, date(1990, 1, 15))
    
    def test_nationality_step_valid_input(self):
        """Test nationality step with valid input."""
        # Set guest details first
        self.guest.full_name = "John Doe"
        self.guest.email = "john@example.com"
        self.guest.date_of_birth = date(1990, 1, 15)
        self.guest.save()
        
        flow_data = {
            "message": "Indian",
            "message_id": "msg_123"
        }
        
        # Create a flow message to set current step to NATIONALITY
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please provide your nationality:",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.NATIONALITY
        )
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "list")
        self.assertEqual(result["text"], "Great! Please select your ID document type:")
        self.assertIn("options", result)
        
        # Check if guest nationality was updated
        self.guest.refresh_from_db()
        self.assertEqual(self.guest.nationality, "Indian")
    
    def test_id_type_step_valid_input(self):
        """Test ID type step with valid input."""
        # Set guest details first
        self.guest.full_name = "John Doe"
        self.guest.email = "john@example.com"
        self.guest.date_of_birth = date(1990, 1, 15)
        self.guest.nationality = "Indian"
        self.guest.save()
        
        flow_data = {
            "message": "Driving License",
            "message_id": "msg_123"
        }
        
        # Create a flow message to set current step to ID_TYPE
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please select your ID document type:",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.ID_TYPE
        )
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "text")
        self.assertIn("Please upload a clear photo", result["text"])
        self.assertIn("License", result["text"])
        
        # Check if document was created
        doc = GuestIdentityDocument.objects.get(guest=self.guest, is_primary=True)
        self.assertEqual(doc.document_type, "driving_license")
        self.assertFalse(doc.is_verified)


class TestCheckinFlowWithImages(TestCase):
    """Test check-in flow with image uploads."""
    
    def setUp(self):
        """Set up test data."""
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            is_active=True,
            status="verified"
        )
        
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            full_name="John Doe",
            email="john@example.com",
            date_of_birth=date(1990, 1, 15),
            nationality="Indian"
        )
        
        self.conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department="Reception",
            conversation_type="checkin",
            status="active"
        )
        
        # Create ID document
        self.doc = GuestIdentityDocument.objects.create(
            guest=self.guest,
            document_type="aadhar_id",
            is_primary=True,
            is_verified=False
        )
    
    @patch('chat.flows.checkin_flow.download_whatsapp_media')
    def test_id_upload_step_success(self, mock_download):
        """Test ID upload step with successful image download."""
        # Mock successful media download
        mock_download.return_value = {
            "content": b"fake_image_data",
            "filename": "front_id.jpg"
        }
        
        flow_data = {
            "media_url": "media_123",
            "message_type": "image",
            "selected_id_type": "aadhar_id",
            "document_name": "AADHAR"
        }
        
        # Create a flow message to set current step to ID_UPLOAD
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please upload ID:",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.ID_UPLOAD
        )
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "text")
        self.assertIn("back side", result["text"])
        
        # Verify front image was saved
        self.doc.refresh_from_db()
        self.assertTrue(bool(self.doc.document_file))
    
    @patch('chat.flows.checkin_flow.download_whatsapp_media')
    def test_id_upload_step_failure(self, mock_download):
        """Test ID upload step with failed image download."""
        # Mock failed media download
        mock_download.return_value = None
        
        flow_data = {
            "media_url": "media_123",
            "message_type": "image"
        }
        
        # Create a flow message to set current step to ID_UPLOAD
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please upload ID:",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.ID_UPLOAD
        )
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "text")
        self.assertIn("Failed to download", result["text"])


class TestCheckinFlowErrorHandling(TestCase):
    """Test error handling in check-in flow."""
    
    def setUp(self):
        """Set up test data."""
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            is_active=True,
            status="verified"
        )
        
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890"
        )
    
    def test_unknown_step_handling(self):
        """Test handling of unknown flow steps."""
        conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            conversation_type="checkin",
            status="active"
        )
        
        # Create a flow message with invalid step
        Message.objects.create(
            conversation=conversation,
            sender_type="staff",
            message_type="system",
            content="Unknown step",
            is_flow=True,
            flow_id="checkin",
            flow_step=999  # Invalid step
        )
        
        flow_data = {
            "message": "test message",
            "message_id": "msg_123"
        }
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=conversation,
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "text")
        self.assertIn("Something went wrong", result["text"])
    
    def test_no_conversation_error(self):
        """Test error when no active conversation exists."""
        flow_data = {
            "message": "test message"
        }
        
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=None,  # No conversation
            flow_data=flow_data,
            is_fresh_checkin_command=False
        )
        
        self.assertEqual(result["type"], "text")
        self.assertIn("No active conversation found", result["text"])


class TestAadharQrExtractionFlow(TestCase):
    """Test AADHAR QR extraction and auto-save functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            is_active=True,
            status="verified"
        )
        
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            full_name="",
            email="",
            date_of_birth=None,
            nationality=""
        )
        
        self.conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department="Reception",
            conversation_type="checkin",
            status="active"
        )
    
    @patch('chat.utils.adhaar.decode_aadhaar_qr_from_image')
    def test_aadhar_qr_extraction_and_auto_save(self, mock_decode_qr):
        """Test AADHAR QR extraction and automatic saving to Guest model."""
        
        # Mock QR extraction result
        mock_decode_qr.return_value = {
            "name": "John Doe",
            "dob": "15/01/1990",
            "address": "123 Test Street, Test City, Test State - 123456"
        }
        
        # Create ID document first
        from guest.models import GuestIdentityDocument
        doc = GuestIdentityDocument.objects.create(
            guest=self.guest,
            document_type="aadhar_id",
            document_number="",
            is_primary=True
        )
        
        # Test data for ID upload
        test_image_content = b"fake_image_data"
        flow_data = {
            "message": "Image message received",
            "message_type": "image",
            "media_id": "test_media_id",
            "id_front_image": test_image_content,
            "id_back_image": test_image_content
        }
        
        # Set up flow at ID_BACK_UPLOAD step
        Message.objects.create(
            conversation=self.conversation,
            sender_type="staff",
            message_type="system",
            content="Please upload the back side of your AADHAR ID",
            is_flow=True,
            flow_id="checkin",
            flow_step=CheckinStep.ID_BACK_UPLOAD
        )
        
        # Process AADHAR verification
        from chat.flows.checkin_flow import process_aadhar_verification
        result = process_aadhar_verification(
            conversation=self.conversation,
            guest=self.guest,
            flow_data=flow_data
        )
        
        # Verify QR was decoded
        mock_decode_qr.assert_called()
        
        # Verify Guest was updated with extracted data
        self.guest.refresh_from_db()
        self.assertEqual(self.guest.full_name, "John Doe")
        self.assertIsNotNone(self.guest.date_of_birth)
        self.assertEqual(self.guest.nationality, "123 Test Street, Test City, Test State - 123")
        
        # Verify confirmation was shown
        self.assertEqual(result["type"], "button")
        self.assertIn("AADHAR Information Extracted", result["text"])
        self.assertIn("John Doe", result["text"])
    
    @patch('chat.utils.adhaar.decode_aadhaar_qr_from_image')
    def test_aadhar_confirmation_yes_completes_flow(self, mock_decode_qr):
        """Test that AADHAR confirmation with 'yes' completes the flow."""
        
        # Mock QR extraction result
        mock_decode_qr.return_value = {
            "name": "Jane Smith",
            "dob": "20/05/1985",
            "address": "456 Sample Road"
        }
        
        # Create and save extracted data first
        self.guest.full_name = "Jane Smith"
        self.guest.save()
        
        flow_data = {
            "extracted_aadhar_info": {
                "name": "Jane Smith",
                "dob": "20/05/1985",
                "address": "456 Sample Road"
            }
        }
        
        # Test user confirmation "yes"
        result = process_checkin_flow(
            guest=self.guest,
            hotel_id=None,
            conversation=self.conversation,
            flow_data={"message": "yes", "message_id": "msg_123"},
            is_fresh_checkin_command=False
        )
        
        # This should show completion message
        self.assertEqual(result["type"], "text")
        self.assertIn("Thank you for confirming", result["text"])
        self.assertIn("receptionist will validate", result["text"])


class TestCheckinFlowCompleteJourney(TestCase):
    """Test complete check-in journey."""
    
    def setUp(self):
        """Set up test data."""
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            is_active=True,
            status="verified"
        )
        
        self.guest = Guest.objects.create(
            whatsapp_number="+1234567890"
        )
    
    @patch('hotel.models.Hotel.objects.get')
    def test_complete_flow_sequence(self, mock_get_hotel):
        """Test the complete flow from start to finish."""
        mock_get_hotel.return_value = self.hotel
        
        # Step 1: Initial check-in command
        flow_data = {
            "whatsapp_number": "+1234567890",
            "message": "/checkin-1"
        }
        
        result = process_checkin_flow(
            guest=None,
            hotel_id=1,
            conversation=None,
            flow_data=flow_data,
            is_fresh_checkin_command=True
        )
        
        # Should ask for name
        self.assertEqual(result["type"], "text")
        self.assertIn("Welcome to Test Hotel", result["text"])
        self.assertIn("full name", result["text"])
        
        # Get the created conversation
        conversation = Conversation.objects.get(guest=self.guest)
        
        # Step 2: Provide name
        flow_data = {"message": "John Doe", "message_id": "msg_1"}
        result = process_checkin_flow(
            guest=self.guest,
            conversation=conversation,
            flow_data=flow_data
        )
        self.assertIn("email address", result["text"])
        
        # Step 3: Provide email
        flow_data = {"message": "john@example.com", "message_id": "msg_2"}
        result = process_checkin_flow(
            guest=self.guest,
            conversation=conversation,
            flow_data=flow_data
        )
        self.assertIn("date of birth", result["text"])
        
        # Step 4: Provide DOB
        flow_data = {"message": "15/01/1990", "message_id": "msg_3"}
        result = process_checkin_flow(
            guest=self.guest,
            conversation=conversation,
            flow_data=flow_data
        )
        self.assertIn("nationality", result["text"])
        
        # Step 5: Provide nationality
        flow_data = {"message": "Indian", "message_id": "msg_4"}
        result = process_checkin_flow(
            guest=self.guest,
            conversation=conversation,
            flow_data=flow_data
        )
        self.assertEqual(result["type"], "list")
        self.assertIn("ID document type", result["text"])


if __name__ == "__main__":
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'django.contrib.auth',
                'guest',
                'hotel',
                'chat',
                'user',
            ],
            SECRET_KEY='test-secret-key',
            USE_TZ=True,
        )
        django.setup()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["chat.flows.test_checkin_flow"])
    
    if failures:
        print(f"\n❌ {failures} test(s) failed")
    else:
        print("\n✅ All tests passed!")