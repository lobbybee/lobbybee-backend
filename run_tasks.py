#!/usr/bin/env python
"""
Run Celery tasks without blocking
Use this to test while worker runs in separate terminal
"""
from test_celery import long_running_task, quick_test
import time
import sys

def test_quick_task():
    """Test quick task"""
    print("Testing quick task...")
    result = quick_test.delay()
    print(f"Task ID: {result.id}")
    print(f"Result: {result.get(timeout=5)}")
    print("✅ Quick task works!\n")

def test_long_task():
    """Test long running task without blocking"""
    print("Submitting 30-second task...")
    task = long_running_task.delay()
    print(f"Task ID: {task.id}")
    print(f"Task status: {task.status}")
    
    # Check progress without blocking
    print("\nChecking task progress every 2 seconds...")
    for i in range(20):  # Check up to 40 seconds
        if task.ready():
            print(f"\n✅ Task completed in approximately {i*2} seconds!")
            print(f"Result: {task.get()}")
            return
        
        print(f"[{i*2}s] Task status: {task.status}, Ready: {task.ready()}")
        time.sleep(2)
    
    if not task.ready():
        print("\n⏳ Task still running after 40 seconds")
        print("Check the worker terminal for progress")
        
        # Still try to get the result with timeout
        try:
            print("\nTrying to get result with timeout...")
            result = task.get(timeout=10)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error getting result: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        test_quick_task()
    elif len(sys.argv) > 1 and sys.argv[1] == "long":
        test_long_task()
    else:
        print("Usage:")
        print("  poetry run python run_tasks.py quick  # Test quick task")
        print("  poetry run python run_tasks.py long   # Test 30-sec task")