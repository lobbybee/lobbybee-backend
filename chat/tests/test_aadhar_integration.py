"""
Quick test for AADHAR QR extraction with test images
Run with: poetry run python chat/tests/test_aadhar_integration.py
"""

import os
import sys

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_aadhar_qr_extraction():
    """Test AADHAR QR extraction with real test images"""
    
    # Configure Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lobbybee.settings')
    
    try:
        import django
        django.setup()
    except Exception as e:
        print(f"Django setup failed: {e}")
        print("Make sure you're running this from the project root with Poetry")
        return False
    
    from chat.utils.adhaar import decode_aadhaar_qr_from_image
    
    print("🔍 Testing AADHAR QR Extraction")
    print("=" * 40)
    
    # Test image paths
    test_image_dir = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/chat/docs/img"
    front_path = os.path.join(test_image_dir, "id_front.jpg")
    back_path = os.path.join(test_image_dir, "id_back.jpg")
    
    # Check if images exist
    print(f"Front image path: {front_path}")
    print(f"Front image exists: {os.path.exists(front_path)}")
    print(f"Back image path: {back_path}")
    print(f"Back image exists: {os.path.exists(back_path)}")
    
    if not os.path.exists(front_path) or not os.path.exists(back_path):
        print("❌ Test images not found!")
        return False
    
    # Test front image
    print("\n📸 Testing front image...")
    try:
        with open(front_path, 'rb') as f:
            front_data = f.read()
        
        front_result = decode_aadhaar_qr_from_image(front_data)
        if front_result:
            print("✅ Front image QR code extracted successfully!")
            print(f"Extracted data keys: {list(front_result.keys())}")
            for key, value in front_result.items():
                print(f"  {key}: {value}")
        else:
            print("❌ No QR code found in front image")
    except Exception as e:
        print(f"❌ Error processing front image: {e}")
    
    # Test back image
    print("\n📸 Testing back image...")
    try:
        with open(back_path, 'rb') as f:
            back_data = f.read()
        
        back_result = decode_aadhaar_qr_from_image(back_data)
        if back_result:
            print("✅ Back image QR code extracted successfully!")
            print(f"Extracted data keys: {list(back_result.keys())}")
            for key, value in back_result.items():
                print(f"  {key}: {value}")
        else:
            print("❌ No QR code found in back image")
    except Exception as e:
        print(f"❌ Error processing back image: {e}")
    
    return True

def test_basic_checkin_flow():
    """Test basic check-in flow functionality"""
    
    print("\n🧪 Testing Basic Check-in Flow")
    print("=" * 40)
    
    try:
        from chat.utils.flows.checkin_flow import check_in_flow, CheckinFlow
        
        # Test new flow start
        print("Testing new flow start...")
        result = check_in_flow("test_flow", {"message": "start"}, None)
        
        print(f"✅ Flow started successfully!")
        print(f"Step ID: {result['step_id']}")
        print(f"Response type: {result['response']['response_type']}")
        print(f"Message preview: {result['response']['text'][:100]}...")
        
        # Test CheckinResponse class
        print("\nTesting CheckinResponse class...")
        flow = CheckinFlow()
        
        # Test phone message
        phone_response = flow.get_phone_number_message()
        print(f"✅ Phone response type: {phone_response.response_type}")
        
        # Test ID type selection
        id_response = flow.get_id_type_selection()
        print(f"✅ ID selection response type: {id_response.response_type}")
        print(f"Available options: {len(id_response.options)} types")
        
        # Test response to dict conversion
        response_dict = phone_response.to_dict()
        print(f"✅ Response dict conversion: {list(response_dict.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in basic flow test: {e}")
        return False

def test_mock_flow_steps():
    """Test flow steps without database"""
    
    print("\n🎭 Testing Mock Flow Steps")
    print("=" * 40)
    
    try:
        from chat.utils.flows.checkin_flow import check_in_flow
        
        flow_id = "mock_test_flow"
        
        # Step 1: Start flow
        result = check_in_flow(flow_id, {"message": "start"}, None)
        print(f"✅ Step 1 - Flow started: {result['step_id']}")
        
        # Step 2: New phone number
        result = check_in_flow(flow_id, {"message": "+1234567890"}, result)
        print(f"✅ Step 2 - Phone processed: {result['step_id']}")
        print(f"Is existing customer: {result['flow_data'].get('is_existing_customer', 'unknown')}")
        
        # Step 3: Select ID type
        result = check_in_flow(flow_id, {"message": "AADHAR ID"}, result)
        print(f"✅ Step 3 - ID selected: {result['step_id']}")
        print(f"Selected type: {result['flow_data'].get('selected_document_type', 'unknown')}")
        
        # Step 4: Front upload (simulate with test data)
        test_image_dir = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/chat/docs/img"
        front_path = os.path.join(test_image_dir, "id_front.jpg")
        
        if os.path.exists(front_path):
            with open(front_path, 'rb') as f:
                test_image = f.read()
            
            result = check_in_flow(flow_id, {"media_data": test_image}, result)
            print(f"✅ Step 4 - Front uploaded: {result['step_id']}")
            
            # Step 5: Back upload
            back_path = os.path.join(test_image_dir, "id_back.jpg")
            if os.path.exists(back_path):
                with open(back_path, 'rb') as f:
                    test_back_image = f.read()
                
                result = check_in_flow(flow_id, {"media_data": test_back_image}, result)
                print(f"✅ Step 5 - Back uploaded: {result['step_id']}")
                print(f"Next action: {result.get('next_action', 'unknown')}")
            else:
                print("❌ Back image not found")
        else:
            print("❌ Front image not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in mock flow test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🏨 Check-in Flow Integration Tests")
    print("=" * 50)
    
    success = True
    
    # Test AADHAR QR extraction
    if not test_aadhar_qr_extraction():
        success = False
    
    # Test basic flow functionality
    if not test_basic_checkin_flow():
        success = False
    
    # Test mock flow steps
    if not test_mock_flow_steps():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All integration tests completed!")
    else:
        print("❌ Some tests failed!")
    
    print("\n💡 To run full Django tests:")
    print("   poetry run python manage.py test chat.tests.test_checkin_flow")