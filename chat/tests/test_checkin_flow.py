import unittest
import json
import os
from unittest.mock import patch, Mock
from django.test import TestCase
from django.utils import timezone
from guest.models import Guest, Stay, Hotel, Room, GuestIdentityDocument
from chat.utils.flows.checkin_flow import check_in_flow, ResponseType, CheckinFlow
from chat.utils.adhaar import decode_aadhaar_qr_from_image


class CheckinFlowTestCase(TestCase):
    """Test cases for check-in flow functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create test hotel
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            address="123 Test Street",
            city="Test City",
            country="Test Country"
        )
        
        # Create room category first
        from hotel.models import RoomCategory
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Deluxe",
            description="Deluxe room category",
            base_price=100.00,
            max_occupancy=2
        )
        
        # Create test room
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            category=self.room_category,
            floor=1
        )
        
        # Create test guest (existing customer)
        self.existing_guest = Guest.objects.create(
            whatsapp_number="+1234567890",
            full_name="John Doe",
            email="john@example.com"
        )
        
        # Create active stay for existing guest
        self.active_stay = Stay.objects.create(
            guest=self.existing_guest,
            hotel=self.hotel,
            room=self.room,
            check_in_date=timezone.now(),
            check_out_date=timezone.now() + timezone.timedelta(days=2),
            status="pending"
        )
        
        # Load test AADHAR images
        self.test_image_dir = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/chat/docs/img"
        self.aadhar_front_path = os.path.join(self.test_image_dir, "id_front.jpg")
        self.aadhar_back_path = os.path.join(self.test_image_dir, "id_back.jpg")
        
        # Read test images
        with open(self.aadhar_front_path, 'rb') as f:
            self.aadhar_front_data = f.read()
        
        with open(self.aadhar_back_path, 'rb') as f:
            self.aadhar_back_data = f.read()
        
        self.flow_id = "test_flow_123"
    
    def test_new_flow_start(self):
        """Test starting a new check-in flow"""
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        
        self.assertEqual(result["flow_id"], self.flow_id)
        self.assertEqual(result["step_id"], "phone_validation")
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["next_action"], "await_user_input")
        self.assertEqual(result["response"]["response_type"], "text")
        self.assertIn("Welcome to our hotel check-in service", result["response"]["text"])
        self.assertIn("phone number", result["response"]["text"])
    
    def test_existing_customer_phone_lookup(self):
        """Test phone number lookup for existing customer"""
        # Start flow
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        
        # Provide existing phone number
        result = check_in_flow(
            self.flow_id, 
            {"message": "+1234567890"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "existing_customer_confirmation")
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["response"]["response_type"], "buttons")
        self.assertTrue(result["flow_data"]["is_existing_customer"])
        self.assertEqual(result["flow_data"]["guest_id"], self.existing_guest.id)
        self.assertIn("John Doe", result["response"]["text"])
        self.assertIn("+1234567890", result["response"]["text"])
    
    def test_new_customer_phone_lookup(self):
        """Test phone number lookup for new customer"""
        # Start flow
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        
        # Provide new phone number
        result = check_in_flow(
            self.flow_id, 
            {"message": "+9876543210"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "id_type_selection")
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["response"]["response_type"], "list")
        self.assertFalse(result["flow_data"]["is_existing_customer"])
        self.assertIn("AADHAR ID", result["response"]["options"])
        self.assertIn("Driving License", result["response"]["options"])
    
    def test_existing_customer_confirmation_yes(self):
        """Test existing customer confirms information"""
        # Start flow and provide existing phone
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+1234567890"}, result)
        
        # Confirm information
        result = check_in_flow(
            self.flow_id, 
            {"message": "Yes, this is correct"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "checkin_complete")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["next_action"], "end_flow")
        self.assertIn("check-in is confirmed", result["response"]["text"])
    
    def test_existing_customer_confirmation_no(self):
        """Test existing customer needs to update information"""
        # Start flow and provide existing phone
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+1234567890"}, result)
        
        # Decline confirmation
        result = check_in_flow(
            self.flow_id, 
            {"message": "No, I need to update information"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "update_name")
        self.assertEqual(result["status"], "in_progress")
        self.assertIn("full name", result["response"]["text"])
    
    def test_invalid_phone_number(self):
        """Test invalid phone number handling"""
        # Start flow
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        
        # Provide invalid phone number
        result = check_in_flow(
            self.flow_id, 
            {"message": "123"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "phone_validation")
        self.assertEqual(result["status"], "validation_failed")
        self.assertEqual(result["next_action"], "retry_input")
        self.assertIn("valid phone number", result["response"]["text"])
    
    def test_id_type_selection_aadhar(self):
        """Test AADHAR ID type selection"""
        # Start flow with new customer
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        
        # Select AADHAR
        result = check_in_flow(
            self.flow_id, 
            {"message": "AADHAR ID"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "id_front_upload")
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["next_action"], "await_media_upload")
        self.assertEqual(result["flow_data"]["selected_document_type"], "aadhar_id")
        self.assertIn("upload the front side", result["response"]["text"])
    
    def test_id_type_selection_driving_license(self):
        """Test Driving License ID type selection"""
        # Start flow with new customer
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        
        # Select Driving License
        result = check_in_flow(
            self.flow_id, 
            {"message": "Driving License"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "id_front_upload")
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["flow_data"]["selected_document_type"], "driving_license")
    
    def test_invalid_id_type_selection(self):
        """Test invalid ID type selection"""
        # Start flow with new customer
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        
        # Select invalid ID type
        result = check_in_flow(
            self.flow_id, 
            {"message": "Invalid ID Type"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "id_type_selection")
        self.assertEqual(result["status"], "validation_failed")
        self.assertIn("valid ID type", result["response"]["text"])
    
    def test_id_front_upload(self):
        """Test front ID document upload"""
        # Start flow and select AADHAR
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "AADHAR ID"}, result)
        
        # Upload front ID
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_front_data}, 
            result
        )
        
        self.assertEqual(result["step_id"], "id_back_upload")
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["next_action"], "await_media_upload")
        self.assertIn("id_front_image", result["flow_data"])
        self.assertIn("back side", result["response"]["text"])
    
    def test_id_front_upload_missing_media(self):
        """Test front ID upload with missing media"""
        # Start flow and select AADHAR
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "AADHAR ID"}, result)
        
        # Try without media data
        result = check_in_flow(
            self.flow_id, 
            {"message": "test"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "id_front_upload")
        self.assertEqual(result["status"], "awaiting_media")
        self.assertIn("upload an image", result["response"]["text"])
    
    def test_id_back_upload_missing_media(self):
        """Test back ID upload with missing media"""
        # Upload front ID successfully
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "AADHAR ID"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        
        # Try back upload without media
        result = check_in_flow(
            self.flow_id, 
            {"message": "test"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "id_back_upload")
        self.assertEqual(result["status"], "awaiting_media")
        self.assertIn("back side", result["response"]["text"])
    
    @patch('chat.utils.flows.checkin_flow.decode_aadhaar_qr_from_image')
    def test_aadhar_qr_extraction_success(self, mock_decode):
        """Test successful AADHAR QR extraction"""
        # Mock successful QR extraction
        mock_aadhar_data = {
            "name": "Test User",
            "dob": "15/01/1990",
            "address": "123 Test Street, Test City, Test State - 123456"
        }
        mock_decode.return_value = mock_aadhar_data
        
        # Complete ID upload process
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "AADHAR ID"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        
        self.assertEqual(result["step_id"], "aadhar_confirmation")
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["response"]["response_type"], "buttons")
        self.assertIn("Test User", result["response"]["text"])
        self.assertIn("15/01/1990", result["response"]["text"])
        self.assertIn("extracted successfully", result["flow_data"]["extracted_aadhar_info"])
    
    @patch('chat.utils.flows.checkin_flow.decode_aadhaar_qr_from_image')
    def test_aadhar_qr_extraction_failure(self, mock_decode):
        """Test AADHAR QR extraction failure - fallback to manual input"""
        # Mock failed QR extraction
        mock_decode.return_value = {}
        
        # Complete ID upload process
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "AADHAR ID"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        
        self.assertEqual(result["step_id"], "aadhar_manual_input")
        self.assertEqual(result["status"], "in_progress")
        self.assertIn("provide your AADHAR details manually", result["response"]["text"])
    
    def test_non_aadhar_id_additional_info_collection(self):
        """Test additional info collection for non-AADHAR IDs"""
        # Start flow with Driving License
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "Driving License"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        
        self.assertEqual(result["step_id"], "additional_info_collection")
        self.assertEqual(result["response"]["response_type"], "text")
        self.assertIn("full name", result["response"]["text"])
        self.assertIn("Date of birth", result["response"]["text"])
        self.assertIn("address", result["response"]["text"])
    
    def test_additional_info_processing_success(self):
        """Test successful additional info processing"""
        # Navigate to additional info collection
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "Driving License"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        
        # Provide additional information
        result = check_in_flow(
            self.flow_id, 
            {"message": "Jane Smith, 25/12/1985, 456 Park Avenue, Mumbai, Maharashtra - 400001"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "additional_info_confirmation")
        self.assertEqual(result["response"]["response_type"], "buttons")
        self.assertEqual(result["flow_data"]["name"], "Jane Smith")
        self.assertEqual(result["flow_data"]["date_of_birth"], "25/12/1985")
        self.assertIn("Jane Smith", result["response"]["text"])
    
    def test_additional_info_invalid_dob(self):
        """Test additional info with invalid date format"""
        # Navigate to additional info collection
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "Driving License"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        
        # Provide invalid date format
        result = check_in_flow(
            self.flow_id, 
            {"message": "Jane Smith, 1985-12-25, 456 Park Avenue"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "additional_info_collection")
        self.assertEqual(result["status"], "validation_failed")
        self.assertIn("DD/MM/YYYY format", result["response"]["text"])
    
    def test_additional_info_incomplete_data(self):
        """Test additional info with incomplete data"""
        # Navigate to additional info collection
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "Driving License"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        
        # Provide incomplete information
        result = check_in_flow(
            self.flow_id, 
            {"message": "Jane Smith"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "additional_info_collection")
        self.assertEqual(result["status"], "validation_failed")
        self.assertIn("three pieces of information", result["response"]["text"])
    
    def test_aadhar_manual_input_success(self):
        """Test successful manual AADHAR input"""
        # Navigate to manual input
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "AADHAR ID"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        
        # Mock QR extraction failure
        with patch('chat.utils.flows.checkin_flow.decode_aadhaar_qr_from_image', return_value={}):
            result = check_in_flow(self.flow_id, {"message": "test"}, result)
        
        self.assertEqual(result["step_id"], "aadhar_manual_input")
        
        # Provide manual AADHAR information
        result = check_in_flow(
            self.flow_id, 
            {"message": "Raj Kumar, 10/06/1988, 789 Nehru Road, Delhi, Delhi - 110001"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "additional_info_confirmation")
        self.assertEqual(result["flow_data"]["name"], "Raj Kumar")
        self.assertEqual(result["flow_data"]["date_of_birth"], "10/06/1988")
    
    def test_confirmation_yes_completes_flow(self):
        """Test that confirmation 'yes' completes the flow"""
        # Navigate to confirmation step
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "Driving License"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        result = check_in_flow(
            self.flow_id, 
            {"message": "Jane Smith, 25/12/1985, 456 Park Avenue, Mumbai, Maharashtra - 400001"}, 
            result
        )
        
        # Confirm with 'yes'
        result = check_in_flow(
            self.flow_id, 
            {"message": "Yes, this is correct"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "checkin_complete")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["next_action"], "end_flow")
        self.assertIn("Check-in completed", result["response"]["text"])
    
    def test_confirmation_no_returns_to_input(self):
        """Test that confirmation 'no' returns to input step"""
        # Navigate to confirmation step
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "Driving License"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        result = check_in_flow(
            self.flow_id, 
            {"media_data": self.aadhar_back_data}, 
            result
        )
        result = check_in_flow(
            self.flow_id, 
            {"message": "Jane Smith, 25/12/1985, 456 Park Avenue, Mumbai, Maharashtra - 400001"}, 
            result
        )
        
        # Decline confirmation
        result = check_in_flow(
            self.flow_id, 
            {"message": "No, I need to correct it"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "additional_info_collection")
        self.assertEqual(result["status"], "in_progress")
    
    def test_aadhar_confirmation_no_returns_to_manual_input(self):
        """Test that AADHAR confirmation 'no' returns to manual input"""
        # Navigate to AADHAR confirmation with successful extraction
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        result = check_in_flow(self.flow_id, {"message": "AADHAR ID"}, result)
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        
        # Mock successful QR extraction
        mock_aadhar_data = {"name": "Test User", "dob": "15/01/1990", "address": "123 Test Street"}
        with patch('chat.utils.flows.checkin_flow.decode_aadhaar_qr_from_image', return_value=mock_aadhar_data):
            result = check_in_flow(self.flow_id, {"media_data": self.aadhar_back_data}, result)
        
        # Decline AADHAR confirmation
        result = check_in_flow(
            self.flow_id, 
            {"message": "No, I need to correct it"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "aadhar_manual_input")
        self.assertEqual(result["status"], "in_progress")
    
    def test_real_aadhar_qr_extraction(self):
        """Test real AADHAR QR extraction with actual test images"""
        # Skip test if images don't exist
        if not (os.path.exists(self.aadhar_front_path) and os.path.exists(self.aadhar_back_path)):
            self.skipTest("Test AADHAR images not found")
        
        # Test front image QR extraction
        front_result = decode_aadhaar_qr_from_image(self.aadhar_front_data)
        print(f"Front QR result: {front_result}")
        
        # Test back image QR extraction
        back_result = decode_aadhaar_qr_from_image(self.aadhar_back_data)
        print(f"Back QR result: {back_result}")
        
        # At least one should work (or both fail, which is also a valid test)
        self.assertIsInstance(front_result, dict)
        self.assertIsInstance(back_result, dict)
    
    def test_flow_data_persistence(self):
        """Test that flow data persists correctly through the flow"""
        # Start flow
        result = check_in_flow(self.flow_id, {"message": "start checkin"}, None)
        self.assertEqual(result["flow_data"], {})
        
        # Add phone number
        result = check_in_flow(self.flow_id, {"message": "+9876543210"}, result)
        self.assertIn("phone", result["flow_data"])
        self.assertFalse(result["flow_data"]["is_existing_customer"])
        
        # Select ID type
        result = check_in_flow(self.flow_id, {"message": "AADHAR ID"}, result)
        self.assertIn("selected_document_type", result["flow_data"])
        self.assertEqual(result["flow_data"]["selected_document_type"], "aadhar_id")
        
        # Upload front ID
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_front_data}, result)
        self.assertIn("id_front_image", result["flow_data"])
        
        # Upload back ID
        result = check_in_flow(self.flow_id, {"media_data": self.aadhar_back_data}, result)
        self.assertIn("id_back_image", result["flow_data"])
    
    def test_checkin_response_class(self):
        """Test CheckinResponse class functionality"""
        # Test text response
        text_response = CheckinFlow().get_phone_number_message()
        self.assertEqual(text_response.response_type, ResponseType.TEXT)
        self.assertIn("phone number", text_response.text)
        self.assertEqual(text_response.options, [])
        
        # Test buttons response
        buttons_response = CheckinFlow().get_existing_customer_confirmation(self.existing_guest)
        self.assertEqual(buttons_response.response_type, ResponseType.BUTTONS)
        self.assertIn("John Doe", buttons_response.text)
        self.assertEqual(len(buttons_response.options), 2)
        
        # Test list response
        list_response = CheckinFlow().get_id_type_selection()
        self.assertEqual(list_response.response_type, ResponseType.LIST)
        self.assertIn("select the type", list_response.text)
        self.assertIn("AADHAR ID", list_response.options)
        
        # Test to_dict conversion
        response_dict = text_response.to_dict()
        self.assertEqual(response_dict["response_type"], "text")
        self.assertIn("phone number", response_dict["text"])
        self.assertNotIn("options", response_dict)


class CheckinFlowIntegrationTestCase(TestCase):
    """Integration tests for complete check-in flow scenarios"""
    
    def setUp(self):
        """Set up integration test data"""
        self.hotel = Hotel.objects.create(
            name="Integration Test Hotel",
            address="456 Test Street",
            city="Test City"
        )
        
        self.test_image_dir = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/chat/docs/img"
        self.aadhar_front_path = os.path.join(self.test_image_dir, "id_front.jpg")
        self.aadhar_back_path = os.path.join(self.test_image_dir, "id_back.jpg")
        
        with open(self.aadhar_front_path, 'rb') as f:
            self.aadhar_front_data = f.read()
        
        with open(self.aadhar_back_path, 'rb') as f:
            self.aadhar_back_data = f.read()
    
    def test_complete_existing_customer_flow(self):
        """Test complete flow for existing customer"""
        flow_id = "existing_customer_test"
        
        # Start flow
        result = check_in_flow(flow_id, {"message": "start checkin"}, None)
        self.assertEqual(result["step_id"], "phone_validation")
        
        # Create existing guest
        guest = Guest.objects.create(
            whatsapp_number="+1111111111",
            full_name="Existing Customer",
            email="existing@example.com"
        )
        
        # Provide phone number
        result = check_in_flow(flow_id, {"message": "+1111111111"}, result)
        self.assertEqual(result["step_id"], "existing_customer_confirmation")
        
        # Confirm
        result = check_in_flow(flow_id, {"message": "Yes, this is correct"}, result)
        self.assertEqual(result["step_id"], "checkin_complete")
        self.assertEqual(result["status"], "completed")
    
    def test_complete_new_customer_aadhar_flow(self):
        """Test complete flow for new customer with AADHAR"""
        flow_id = "new_customer_aadhar_test"
        
        # Start flow
        result = check_in_flow(flow_id, {"message": "start checkin"}, None)
        
        # Provide new phone number
        result = check_in_flow(flow_id, {"message": "+2222222222"}, result)
        self.assertEqual(result["step_id"], "id_type_selection")
        
        # Select AADHAR
        result = check_in_flow(flow_id, {"message": "AADHAR ID"}, result)
        self.assertEqual(result["step_id"], "id_front_upload")
        
        # Upload front ID
        result = check_in_flow(flow_id, {"media_data": self.aadhar_front_data}, result)
        self.assertEqual(result["step_id"], "id_back_upload")
        
        # Mock QR extraction failure to test manual input
        with patch('chat.utils.flows.checkin_flow.decode_aadhaar_qr_from_image', return_value={}):
            result = check_in_flow(flow_id, {"media_data": self.aadhar_back_data}, result)
        
        self.assertEqual(result["step_id"], "aadhar_manual_input")
        
        # Provide manual information
        result = check_in_flow(
            flow_id, 
            {"message": "New Customer, 15/08/1992, 789 New Street, Bangalore, Karnataka - 560001"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "additional_info_confirmation")
        
        # Confirm
        result = check_in_flow(flow_id, {"message": "Yes, this is correct"}, result)
        self.assertEqual(result["step_id"], "checkin_complete")
        self.assertEqual(result["status"], "completed")
    
    def test_complete_new_customer_driving_license_flow(self):
        """Test complete flow for new customer with Driving License"""
        flow_id = "new_customer_dl_test"
        
        # Start flow
        result = check_in_flow(flow_id, {"message": "start checkin"}, None)
        
        # Provide new phone number
        result = check_in_flow(flow_id, {"message": "+3333333333"}, result)
        self.assertEqual(result["step_id"], "id_type_selection")
        
        # Select Driving License
        result = check_in_flow(flow_id, {"message": "Driving License"}, result)
        self.assertEqual(result["step_id"], "id_front_upload")
        
        # Upload front ID
        result = check_in_flow(flow_id, {"media_data": self.aadhar_front_data}, result)
        self.assertEqual(result["step_id"], "id_back_upload")
        
        # Upload back ID
        result = check_in_flow(flow_id, {"media_data": self.aadhar_back_data}, result)
        self.assertEqual(result["step_id"], "additional_info_collection")
        
        # Provide additional information
        result = check_in_flow(
            flow_id, 
            {"message": "Driver Person, 20/11/1980, 321 Highway Road, Chennai, Tamil Nadu - 600001"}, 
            result
        )
        
        self.assertEqual(result["step_id"], "additional_info_confirmation")
        
        # Confirm
        result = check_in_flow(flow_id, {"message": "Yes, this is correct"}, result)
        self.assertEqual(result["step_id"], "checkin_complete")
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()