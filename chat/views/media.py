"""
Media upload and handling views for chat functionality.
"""

import os
import uuid
import logging
from rest_framework.permissions import IsAuthenticated
from .base import (
    APIView, status, Response, logger, User, transaction, timezone,
    Conversation, Message, ConversationParticipant, convert_audio_for_whatsapp
)
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


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
            
            # Allow all hotel staff types to upload media
            allowed_user_types = ['hotel_admin', 'manager', 'receptionist', 'department_staff', 'other_staff']
            
            if user.user_type not in allowed_user_types:
                logger.error(f"ChatMediaUploadView: Access denied for user {user.username} - not hotel staff")
                return Response(
                    {'error': 'Access denied. Only hotel staff can upload media.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                conversation = Conversation.objects.select_related('hotel', 'guest').get(id=conversation_id)
                
                # Validate user can access this conversation
                # Hotel admins and managers can access all conversations in their hotel
                if user.user_type in ['hotel_admin', 'manager']:
                    if conversation.hotel != user.hotel:
                        logger.error(f"ChatMediaUploadView: Access denied for user {user.username} - different hotel")
                        return Response(
                            {'error': 'Access denied to this conversation'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                else:
                    # Receptionists, department staff, and other staff can only access conversations in their departments
                    departments = user.department or []
                    
                    # Ensure departments is always a list
                    if isinstance(departments, str):
                        user_departments = [departments]
                    elif isinstance(departments, list):
                        user_departments = departments
                    else:
                        user_departments = []
                        
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
            
            # Process and save the file - no message creation
            with transaction.atomic():
                try:
                    # Handle audio file conversion for WhatsApp compatibility
                    processed_file, message_type, filename = self._process_uploaded_file(uploaded_file)
                    
                    # Generate unique filename and upload path
                    ext = filename.split('.')[-1]
                    unique_filename = f"{uuid.uuid4().hex}.{ext}"
                    upload_path = f"chat/hotel_{conversation.hotel.id}/conversation_{conversation.id}/{unique_filename}"
                    
                    # Save file directly to storage
                    saved_path = default_storage.save(upload_path, processed_file)
                    uploaded_file_url = default_storage.url(saved_path)
                    
                    logger.info(f"ChatMediaUploadView: Successfully uploaded file: {unique_filename}")
                    
                    # Prepare response data with file info only (no message)
                    response_data = {
                        'message': 'File uploaded successfully',
                        'file_url': uploaded_file_url,
                        'filename': unique_filename,
                        'file_type': message_type,
                        'conversation_id': conversation_id,
                        'file_info': {
                            'original_name': uploaded_file.name,
                            'size': uploaded_file.size,
                            'content_type': uploaded_file.content_type,
                        }
                    }
                    
                    logger.info(f"ChatMediaUploadView: Upload completed successfully, returning file URL")
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
                # Read the file content as bytes
                audio_content = uploaded_file.read()
                converted_content = convert_audio_for_whatsapp(audio_content, content_type)
                
                # Generate new filename for converted audio
                file_extension = os.path.splitext(filename)[1]
                if converted_content != audio_content:  # Audio was converted
                    converted_filename = f"{uuid.uuid4().hex}.ogg"
                    # Set correct content type for OGG audio files
                    processed_file = ContentFile(converted_content, name=converted_filename)
                    processed_file.content_type = 'audio/ogg'
                else:
                    converted_filename = f"{uuid.uuid4().hex}{file_extension}"
                    processed_file = ContentFile(converted_content, name=converted_filename)
                    # Preserve original content type for non-converted audio
                    processed_file.content_type = content_type
                
                unique_filename = converted_filename
                logger.info(f"ChatMediaUploadView: Audio conversion completed: {converted_filename} with content type: {processed_file.content_type}")
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


class TemplateMediaUploadView(APIView):
    """
    API endpoint for uploading media files for message templates
    Handles image uploads for hotel admins and platform staff
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle media file upload for message templates"""
        logger.info(f"TemplateMediaUploadView: Received upload request from user {request.user.username}")
        
        try:
            if 'file' not in request.FILES:
                logger.error("TemplateMediaUploadView: No file provided")
                return Response(
                    {'error': 'file is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            uploaded_file = request.FILES['file']
            logger.info(f"TemplateMediaUploadView: Processing file {uploaded_file.name}")
            
            # Validate file size (5MB limit for templates)
            max_size = 5 * 1024 * 1024  # 5MB
            if uploaded_file.size > max_size:
                logger.error(f"TemplateMediaUploadView: File too large: {uploaded_file.size} bytes")
                return Response(
                    {'error': 'File size exceeds 5MB limit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file type - only images for templates
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            
            if uploaded_file.content_type not in allowed_types:
                logger.error(f"TemplateMediaUploadView: Unsupported file type: {uploaded_file.content_type}")
                return Response(
                    {'error': f'File type {uploaded_file.content_type} is not supported. Only images are allowed.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate user permissions
            user = request.user
            
            # Only hotel admins, platform staff, and superusers can upload template media
            if user.user_type not in ['hotel_admin', 'platform_staff'] and not user.is_superuser:
                logger.error(f"TemplateMediaUploadView: Access denied for user {user.username}")
                return Response(
                    {'error': 'Access denied. Only hotel admins and platform staff can upload template media.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Process and save the file
            try:
                # Process the image file
                processed_file, file_type, filename = self._process_template_file(uploaded_file)
                
                # Generate upload path based on user type
                if user.user_type == 'hotel_admin' and hasattr(user, 'hotel'):
                    upload_path = f"templates/hotel_{user.hotel.id}/{filename}"
                else:
                    # Platform staff and superusers - global templates
                    upload_path = f"templates/global/{filename}"
                
                # Save file to storage
                saved_path = default_storage.save(upload_path, processed_file)
                file_url = default_storage.url(saved_path)
                
                logger.info(f"TemplateMediaUploadView: Successfully uploaded template file: {filename}")
                
                # Prepare response data
                response_data = {
                    'message': 'Template media uploaded successfully',
                    'file_url': file_url,
                    'filename': filename,
                    'file_type': file_type,
                    'file_info': {
                        'original_name': uploaded_file.name,
                        'size': uploaded_file.size,
                        'content_type': uploaded_file.content_type,
                    }
                }
                
                logger.info(f"TemplateMediaUploadView: Template media upload completed successfully")
                return Response(response_data, status=status.HTTP_201_CREATED)
                
            except Exception as process_error:
                logger.error(f"TemplateMediaUploadView: Error processing file: {process_error}", exc_info=True)
                return Response(
                    {'error': 'Error processing uploaded file', 'details': str(process_error)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"TemplateMediaUploadView: Unexpected error: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_template_file(self, uploaded_file):
        """
        Process uploaded file for template usage
        Returns: (processed_file, file_type, filename)
        """
        filename = uploaded_file.name
        content_type = uploaded_file.content_type
        
        # Generate unique filename with original extension
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"template_{uuid.uuid4().hex}{file_extension}"
        
        # Determine file type
        file_type = 'image'
        
        # For templates, we use the original file as-is (no audio conversion needed)
        processed_file = uploaded_file
        
        return processed_file, file_type, unique_filename