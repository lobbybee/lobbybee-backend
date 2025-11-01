"""
Media upload and handling views for chat functionality.
"""

import os
import uuid
import logging
from rest_framework.permissions import IsAuthenticated
from . import (
    APIView, status, Response, logger, User, transaction, timezone,
    Conversation, Message, ConversationParticipant, convert_audio_for_whatsapp
)
from django.core.files.base import ContentFile


class ChatMediaUploadView(APIView):
    """
    API endpoint for uploading media files for chat messages
    Handles file uploads from department staff with validation and access control
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle media file upload for chat messages"""
        logger.info(f"ChatMediaUploadView: Received upload request from user {request.user.username}")
        
        try:
            # Validate required fields
            conversation_id = request.data.get('conversation_id')
            caption = request.data.get('caption', '')
            
            if not conversation_id:
                logger.error("ChatMediaUploadView: Missing conversation_id")
                return Response(
                    {'error': 'conversation_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if 'file' not in request.FILES:
                logger.error("ChatMediaUploadView: No file provided")
                return Response(
                    {'error': 'file is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            uploaded_file = request.FILES['file']
            logger.info(f"ChatMediaUploadView: Processing file {uploaded_file.name} for conversation {conversation_id}")
            
            # Validate file size (10MB limit)
            max_size = 10 * 1024 * 1024  # 10MB
            if uploaded_file.size > max_size:
                logger.error(f"ChatMediaUploadView: File too large: {uploaded_file.size} bytes")
                return Response(
                    {'error': 'File size exceeds 10MB limit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf', 
                           'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                           'video/mp4', 'video/avi', 'video/mov', 'audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/webm', 'audio/ogg']
            
            if uploaded_file.content_type not in allowed_types:
                logger.error(f"ChatMediaUploadView: Unsupported file type: {uploaded_file.content_type}")
                return Response(
                    {'error': f'File type {uploaded_file.content_type} is not supported'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate user permissions and conversation access
            user = request.user
            
            if user.user_type != 'department_staff':
                logger.error(f"ChatMediaUploadView: Access denied for user {user.username} - not department staff")
                return Response(
                    {'error': 'Access denied. Only department staff can upload media.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                conversation = Conversation.objects.select_related('hotel', 'guest').get(id=conversation_id)
                
                # Validate user can access this conversation
                user_departments = user.department or []
                if (conversation.hotel != user.hotel or
                    conversation.department not in user_departments):
                    logger.error(f"ChatMediaUploadView: Access denied for user {user.username} to conversation {conversation_id}")
                    return Response(
                        {'error': 'Access denied to this conversation'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                    
            except Conversation.DoesNotExist:
                logger.error(f"ChatMediaUploadView: Conversation {conversation_id} not found")
                return Response(
                    {'error': 'Conversation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Process and save the file
            with transaction.atomic():
                try:
                    # Handle audio file conversion for WhatsApp compatibility
                    processed_file, message_type, filename = self._process_uploaded_file(uploaded_file)
                    
                    # Create message with media
                    message = Message.objects.create(
                        conversation=conversation,
                        sender=user,
                        sender_type='staff',
                        message_type=message_type,
                        content=caption or f"Shared a {message_type.replace('_', ' ')}",
                        media_file=processed_file,
                        media_filename=filename
                    )
                    
                    # Update conversation
                    conversation.update_last_message(message.content)
                    
                    # Add user as participant if not already
                    participant, created = ConversationParticipant.objects.get_or_create(
                        conversation=conversation,
                        staff=user,
                        defaults={'is_active': True}
                    )
                    
                    if not created and not participant.is_active:
                        participant.is_active = True
                        participant.save()
                    
                    logger.info(f"ChatMediaUploadView: Successfully created message {message.id} with media")
                    
                    # Prepare response data
                    response_data = {
                        'success': True,
                        'message_id': message.id,
                        'conversation_id': conversation.id,
                        'message_type': message.message_type,
                        'content': message.content,
                        'media_url': message.get_media_url,
                        'media_filename': message.media_filename,
                        'created_at': message.created_at.isoformat(),
                        'file_info': {
                            'original_name': uploaded_file.name,
                            'size': uploaded_file.size,
                            'content_type': uploaded_file.content_type,
                        }
                    }
                    
                    # Broadcast message via WebSocket (this would be handled by the message creation consumer)
                    logger.info(f"ChatMediaUploadView: Upload completed successfully")
                    return Response(response_data, status=status.HTTP_201_CREATED)
                    
                except Exception as process_error:
                    logger.error(f"ChatMediaUploadView: Error processing file: {process_error}", exc_info=True)
                    return Response(
                        {'error': 'Error processing uploaded file', 'details': str(process_error)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                    
        except Exception as e:
            logger.error(f"ChatMediaUploadView: Unexpected error: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_uploaded_file(self, uploaded_file):
        """
        Process uploaded file for chat usage
        Returns: (processed_file, message_type, filename)
        """
        filename = uploaded_file.name
        content_type = uploaded_file.content_type
        
        # Generate unique filename
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        
        # Determine message type based on content type
        if content_type.startswith('image/'):
            message_type = 'image'
        elif content_type.startswith('video/'):
            message_type = 'video'
        elif content_type.startswith('audio/'):
            message_type = 'audio'
            # Convert audio for WhatsApp compatibility
            try:
                logger.info(f"ChatMediaUploadView: Converting audio file {filename} for WhatsApp compatibility")
                converted_content, converted_filename = convert_audio_for_whatsapp(uploaded_file)
                processed_file = ContentFile(converted_content, name=converted_filename)
                unique_filename = converted_filename
                logger.info(f"ChatMediaUploadView: Audio conversion completed: {converted_filename}")
            except Exception as audio_error:
                logger.warning(f"ChatMediaUploadView: Audio conversion failed, using original: {audio_error}")
                processed_file = uploaded_file
        elif content_type == 'application/pdf':
            message_type = 'document'
        elif content_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            message_type = 'document'
        elif content_type == 'text/plain':
            message_type = 'document'
        else:
            message_type = 'document'
        
        if 'processed_file' not in locals():
            processed_file = uploaded_file
        
        return processed_file, message_type, unique_filename