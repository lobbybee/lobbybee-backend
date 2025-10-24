from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from urllib.parse import parse_qs
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

@database_sync_to_async
def get_user_from_token(token_string):
    """Validate JWT token and return user"""
    try:
        # Decode and validate the token
        access_token = AccessToken(token_string)
        user_id = access_token['user_id']

        # Get the user from database
        user = User.objects.get(id=user_id)
        logger.info(f"JWT Auth successful for user: {user}")
        return user
    except (InvalidToken, TokenError) as e:
        logger.error(f"Invalid token: {e}")
        return AnonymousUser()
    except User.DoesNotExist:
        logger.error(f"User not found for token")
        return AnonymousUser()
    except Exception as e:
        logger.error(f"Unexpected error in JWT auth: {e}")
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    """Custom middleware to authenticate WebSocket connections using JWT"""

    async def __call__(self, scope, receive, send):
        # Close old database connections to prevent usage across threads
        from django.db import close_old_connections
        close_old_connections()

        token = None

        # Try to get token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        # If no token in query string, try headers (some WebSocket clients support this)
        if not token:
            headers = dict(scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode()
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        # Authenticate user with token
        if token:
            scope['user'] = await get_user_from_token(token)
            logger.info(f"Token found, user set to: {scope['user']}")
        else:
            scope['user'] = AnonymousUser()
            logger.warning("No token found in WebSocket connection")

        return await super().__call__(scope, receive, send)

def JWTAuthMiddlewareStack(inner):
    """Helper function to wrap the inner ASGI application with JWT auth"""
    return JWTAuthMiddleware(inner)
