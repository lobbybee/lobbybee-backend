#!/usr/bin/env python
"""
Test script for check-in reminder Celery tasks
"""
import os
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lobbybee.config.development')
django.setup()

from guest.tasks import send_extend_checkin_reminder, schedule_checkin_reminder
from guest.models import Stay

def test_extension_message():
    """Test sending extension message directly"""
    print("Testing extension check-in reminder...")
    
    # Get an active stay
    stay = Stay.objects.filter(status='active').select_related('guest').first()
    
    if not stay:
        print("No active stays found.")
        return
    
    print(f"Using stay: {stay.id}")
    print(f"Guest: {stay.guest.full_name}")
    print(f"WhatsApp: {stay.guest.whatsapp_number}")
    print(f"Hotel: {stay.hotel.name}")
    print(f"24-hour stay: {stay.hours_24}")
    
    # Send extension message immediately
    result = send_extend_checkin_reminder.delay(stay.id)
    print(f"\nTask submitted: {result.id}")
    
    # Wait for result
    try:
        task_result = result.get(timeout=10)
        print(f"Task result: {task_result}")
    except Exception as e:
        print(f"Task failed: {e}")

def test_scheduling():
    """Test scheduling extension reminder"""
    print("\n\nTesting scheduling of extension reminder...")
    
    # Get an active stay
    stay = Stay.objects.filter(status='active').first()
    
    if not stay:
        print("No active stays found")
        return
    
    print(f"Scheduling extension reminder for stay {stay.id}")
    print(f"Hours_24: {stay.hours_24}")
    
    # Schedule extension reminder
    result = schedule_checkin_reminder.delay(stay.id)
    print(f"Scheduling task submitted: {result.id}")
    
    # Get scheduling result
    try:
        schedule_result = result.get(timeout=5)
        print(f"Scheduling result: {schedule_result}")
        
        if schedule_result['status'] == 'success':
            hours = schedule_result['countdown_hours']
            print(f"\n✅ Extension reminder scheduled successfully!")
            print(f"   - Message will be sent in {hours} hours")
        
    except Exception as e:
        print(f"Scheduling failed: {e}")

def test_quick_message():
    """Test extension message with short delay for immediate testing"""
    print("\n\nTesting extension message with 5-second delay...")
    
    stay = Stay.objects.filter(status='active').first()
    
    if not stay:
        print("No active stays found")
        return
    
    # Send extension message with 5 second delay for testing
    result = send_extend_checkin_reminder.apply_async(
        args=[stay.id],
        countdown=5
    )
    print(f"Extension message task submitted: {result.id}")
    print("Message will be sent in 5 seconds...")

if __name__ == "__main__":
    print("=" * 60)
    print("Check-in Extension Reminder Tasks Test")
    print("=" * 60)
    print("\nChoose test option:")
    print("1. Send extension message immediately")
    print("2. Schedule extension reminder (11/23 hours)")
    print("3. Send extension message with 5-second delay (for testing)")
    print("4. Run all tests")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == '1':
        test_extension_message()
    elif choice == '2':
        test_scheduling()
    elif choice == '3':
        test_quick_message()
    elif choice == '4':
        test_extension_message()
        test_scheduling()
        test_quick_message()
    else:
        print("Running default test (option 1)...")
        test_extension_message()
    
    print("\n\nTest completed! Check your WhatsApp for messages.")
    print("Make sure Celery worker is running: celery -A lobbybee worker -l info")