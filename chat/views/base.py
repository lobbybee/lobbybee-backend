"""
Base imports and utilities for all view modules.
"""

import logging
import uuid
import time
import os
from rest_framework import status, views, response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.files.base import ContentFile

from ..models import Conversation, Message, ConversationParticipant
from guest.models import Guest, Stay
from ..serializers import (
    ConversationSerializer, MessageSerializer, GuestMessageSerializer,
    ConversationCreateSerializer, MessageReadSerializer, TypingIndicatorSerializer,
    FlowMessageSerializer
)
from ..consumers import notify_new_conversation_to_department, notify_conversation_update_to_department
from ..utils.phone_utils import normalize_phone_number
from ..utils.whatsapp_utils import download_whatsapp_media
from ..utils.pydub import convert_audio_for_whatsapp

# Common utilities
User = get_user_model()
logger = logging.getLogger(__name__)

# Common response function
def create_response(data, status_code=status.HTTP_200_OK):
    """Create a standardized response"""
    return response.Response(data, status=status_code)