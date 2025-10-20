'''
ASGI config for lobbybee project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
'''

import os

# Set the settings module to use the settings switcher
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lobbybee.settings')

# Import Django and set up the application after environment is configured
import django
from django.core.asgi import get_asgi_application

django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
