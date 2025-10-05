from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
import json
import logging
from .services.message_handler import MessageHandler
from .models import Conversation, Message
from .serializers import (
    ConversationListSerializer, 
    MessageSerializer, 
    ConversationDetailSerializer,
    CreateMessageSerializer
)
from hotel.models import Department

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)

            # Extract WhatsApp message details
            phone_number = self.extract_phone_number(data)
            message_content = self.extract_message_content(data)

            if not phone_number or not message_content:
                return JsonResponse({'status': 'ignored'})

            # Process message
            handler = MessageHandler()
            response = handler.process_message(phone_number, message_content)

            # Send response back to WhatsApp (implement WhatsApp API call)
            if response.get('message'):
                self.send_whatsapp_message(phone_number, response['message'])

            return JsonResponse({'status': 'processed'})

        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({'status': 'error'})

    def extract_phone_number(self, data):
        # Implement WhatsApp webhook payload parsing
        # This is a placeholder - in a real implementation, you would parse the actual WhatsApp payload
        # For now, we'll return a dummy phone number for testing
        return "+1234567890"

    def extract_message_content(self, data):
        # Implement WhatsApp webhook payload parsing
        # This is a placeholder - in a real implementation, you would parse the actual WhatsApp payload
        # For now, we'll return a dummy message for testing
        return "Hello"

    def send_whatsapp_message(self, phone_number, message):
        # Implement WhatsApp API call
        # This is a placeholder - in a real implementation, you would call the WhatsApp Business API
        logger.info(f"Sending WhatsApp message to {phone_number}: {message}")
        pass


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationListSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def get_queryset(self):
        """
        Filter conversations based on user's department assignments.
        Staff can only see conversations routed to their departments.
        """
        user = self.request.user
        
        # Check if user has a hotel assigned
        if not user.hotel:
            return Conversation.objects.none()
        
        # Get departments for the user's hotel
        user_departments = Department.objects.filter(
            hotel=user.hotel
        )
        
        if not user_departments.exists():
            return Conversation.objects.none()
            
        return Conversation.objects.filter(
            status='relay',
            department__in=user_departments
        ).select_related(
            'stay__guest', 
            'stay__room', 
            'department'
        ).order_by('-updated_at')

    def retrieve(self, request, *args, **kwargs):
        """Get detailed conversation information"""
        conversation = self.get_object()
        serializer = ConversationDetailSerializer(conversation)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get all messages for a conversation"""
        conversation = self.get_object()
        messages = Message.objects.filter(
            conversation=conversation
        ).select_related('staff_sender').order_by('timestamp')

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a message from staff to guest"""
        conversation = self.get_object()
        serializer = CreateMessageSerializer(data=request.data)
        
        if serializer.is_valid():
            # Create the message
            message = Message.objects.create(
                conversation=conversation,
                content=serializer.validated_data['text'],
                sender_type='staff',
                staff_sender=request.user
            )
            
            # Update conversation timestamp
            conversation.save(update_fields=['updated_at'])
            
            # Return the created message
            message_serializer = MessageSerializer(message)
            return Response(message_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def end_relay(self, request, pk=None):
        """End the relay and return conversation to active status"""
        conversation = self.get_object()
        conversation.status = 'active'
        conversation.department = None
        conversation.save()

        return Response({'status': 'relay ended'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def active_conversations(self, request):
        """Get all active conversations (not in relay status)"""
        user = self.request.user
        
        # Check if user has a hotel assigned
        if not user.hotel:
            return Response([])
        
        # Get departments for the user's hotel
        user_departments = Department.objects.filter(
            hotel=user.hotel
        )
        
        if not user_departments.exists():
            return Response([])
            
        conversations = Conversation.objects.filter(
            status='active',
            stay__hotel=user.hotel
        ).select_related(
            'stay__guest', 
            'stay__room'
        ).order_by('-updated_at')

        serializer = self.get_serializer(conversations, many=True)
        return Response(serializer.data)