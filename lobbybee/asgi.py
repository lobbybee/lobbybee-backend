'''
ASGI config for lobbybee project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
'''

import os
from django.core.asgi import get_asgi_application

# Get the environment from an environment variable
env = os.environ.get('DJANGO_ENV', 'development')

# Set the settings module based on the environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'lobbybee.config.{env}')

application = get_asgi_application()