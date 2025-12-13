from celery import Celery
import time
import os

# Configure Celery with Redis
app = Celery(
    'test_celery',
    broker='redis://127.0.0.1:6379/0',
    backend='redis://127.0.0.1:6379/0',
    include=['test_celery']
)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True,
)

# Simple task that takes 30 seconds
@app.task
def long_running_task():
    """
    A simple task that simulates 30 seconds of work
    """
    print("Task started: Processing for 30 seconds...")
    
    # Simulate work for 30 seconds
    for i in range(30):
        time.sleep(1)
        print(f"Working... {i+1}/30 seconds")
    
    result = {
        'status': 'completed',
        'message': '30-second task finished successfully!',
        'worker': os.uname()[1] if hasattr(os, 'uname') else 'unknown'
    }
    
    print(f"Task completed: {result}")
    return result

# Quick test task
@app.task
def quick_test():
    """
    Quick test task that returns immediately
    """
    return "Hello from Celery! It's working!"

if __name__ == '__main__':
    # Run worker directly
    app.start()