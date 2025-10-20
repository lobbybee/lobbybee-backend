import os
import django
from django.conf import settings

# Set the environment
os.environ.setdefault('DJANGO_ENV', 'development')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lobbybee.settings')

# Setup Django
django.setup()

# Print the settings
print("DJANGO_ENV:", os.environ.get('DJANGO_ENV'))
print("DJANGO_SETTINGS_MODULE:", os.environ.get('DJANGO_SETTINGS_MODULE'))
print("SECURE_SSL_REDIRECT:", getattr(settings, 'SECURE_SSL_REDIRECT', 'Not set'))
print("DEBUG:", getattr(settings, 'DEBUG', 'Not set'))