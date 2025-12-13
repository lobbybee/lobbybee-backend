import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
# Use development settings by default for local development
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'lobbybee.config.development')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

app = Celery('lobbybee')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()