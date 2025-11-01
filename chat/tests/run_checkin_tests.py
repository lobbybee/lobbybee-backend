#!/usr/bin/env python3
"""
Test runner for check-in flow tests
Usage: python run_checkin_tests.py
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lobbybee_backend.settings')
django.setup()

def run_checkin_flow_tests():
    """Run all check-in flow tests"""
    
    print("🧪 Running Check-in Flow Tests")
    print("=" * 50)
    
    # Import the test module
    from chat.tests.test_checkin_flow import CheckinFlowTestCase, CheckinFlowIntegrationTestCase
    
    import unittest
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(CheckinFlowTestCase))
    suite.addTest(unittest.makeSuite(CheckinFlowIntegrationTestCase))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.failures:
        print("\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n💥 Errors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return True
    else:
        print("\n❌ Some tests failed!")
        return False

def test_real_aadhar_images():
    """Test the real AADHAR images to see if QR codes can be extracted"""
    
    print("🔍 Testing Real AADHAR Images")
    print("=" * 30)
    
    from chat.utils.adhaar import decode_aadhaar_qr_from_image
    
    test_image_dir = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/chat/docs/img"
    front_path = os.path.join(test_image_dir, "id_front.jpg")
    back_path = os.path.join(test_image_dir, "id_back.jpg")
    
    if not os.path.exists(front_path) or not os.path.exists(back_path):
        print("❌ Test images not found!")
        return False
    
    # Test front image
    print("📸 Testing front image...")
    with open(front_path, 'rb') as f:
        front_data = f.read()
    
    front_result = decode_aadhaar_qr_from_image(front_data)
    if front_result:
        print("✅ Front image QR code extracted successfully!")
        print(f"Data: {front_result}")
    else:
        print("❌ No QR code found in front image")
    
    # Test back image
    print("\n📸 Testing back image...")
    with open(back_path, 'rb') as f:
        back_data = f.read()
    
    back_result = decode_aadhaar_qr_from_image(back_data)
    if back_result:
        print("✅ Back image QR code extracted successfully!")
        print(f"Data: {back_result}")
    else:
        print("❌ No QR code found in back image")
    
    return bool(front_result or back_result)

def run_manual_flow_demo():
    """Run a manual demonstration of the flow"""
    
    print("\n🎭 Manual Flow Demonstration")
    print("=" * 40)
    
    from chat.utils.flows.checkin_flow import check_in_flow
    
    flow_id = "demo_flow"
    
    # Start flow
    result = check_in_flow(flow_id, {"message": "start checkin"}, None)
    print(f"Step: {result['step_id']}")
    print(f"Message: {result['response']['text']}")
    print("-" * 40)
    
    # Simulate new customer
    result = check_in_flow(flow_id, {"message": "+9876543210"}, result)
    print(f"Step: {result['step_id']}")
    print(f"Message: {result['response']['text']}")
    if result['response'].get('options'):
        print(f"Options: {result['response']['options']}")
    print("-" * 40)
    
    # Select AADHAR
    result = check_in_flow(flow_id, {"message": "AADHAR ID"}, result)
    print(f"Step: {result['step_id']}")
    print(f"Message: {result['response']['text']}")
    print("-" * 40)
    
    print("🎭 Demo completed!")

if __name__ == "__main__":
    print("🏨 Check-in Flow Test Suite")
    print("=" * 50)
    
    # Test real AADHAR images first
    aadhar_success = test_real_aadhar_images()
    
    print("\n")
    
    # Run the main test suite
    test_success = run_checkin_flow_tests()
    
    # Run manual demo
    run_manual_flow_demo()
    
    # Exit with appropriate code
    exit_code = 0 if test_success else 1
    sys.exit(exit_code)