'''
ASGI config for lobbybee project.
'''
import os
import environ
from pathlib import Path

# Initialize environ
environ_config = environ.Env(DEBUG=(bool, False))

BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file
environ.Env.read_env(BASE_DIR / '.env')

# Get environment from .env
django_env = environ_config('DJANGO_ENV', default='development')

# Set the settings module BEFORE any Django imports
if django_env == 'production':
    settings_module = 'lobbybee.config.production'
else:
    settings_module = 'lobbybee.config.development'

# Force set the settings module (don't use setdefault)
os.environ['DJANGO_SETTINGS_MODULE'] = settings_module

# NOW import Django
import django
from django.core.asgi import get_asgi_application

django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from chat.consumers import ChatConsumer, GuestChatConsumer
from lobbybee.middleware import JWTAuthMiddlewareStack  # Import your middleware

# WebSocket URL patterns
websocket_urlpatterns = [
    path('ws/chat/', ChatConsumer.as_asgi()),
    path('ws/guest/<str:whatsapp_number>/', GuestChatConsumer.as_asgi()),
]

# ASGI application configuration
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddlewareStack(  # Use JWT middleware instead of AuthMiddlewareStack
            URLRouter(
                websocket_urlpatterns
            )
        )

})
