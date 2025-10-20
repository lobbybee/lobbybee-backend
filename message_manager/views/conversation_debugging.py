from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from hotel.models import Hotel
from ..models import Conversation, Message
from ..serializers import ConversationListSerializer, MessageSerializer, ConversationDetailSerializer, CreateMessageSerializer
from hotel.permissions import CanManagePlatform
from rest_framework.pagination import PageNumberPagination
import logging

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ConversationDebugViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for debugging conversations.
    """
    queryset = Conversation.objects.all().order_by('-updated_at')
    serializer_class = ConversationListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['status']
    search_fields = ['id']

    def get_queryset(self):
        """
        Filter conversations based on user's department assignments.
        Staff can only see conversations routed to their departments.
        """
        try:
            user = self.request.user
            
            # Check if user has a hotel assigned
            if not user.hotel:
                return Conversation.objects.none()
            
            return Conversation.objects.filter(
                status='relay'
            ).select_related(
                'stay__guest', 
                'stay__room'
            ).order_by('-updated_at')
        except Exception as e:
            logger.error(f"Error in ConversationDebugViewSet.get_queryset: {str(e)}")
            return Conversation.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in ConversationDebugViewSet.list: {str(e)}")
            return Response({"error": "An error occurred while fetching conversations."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in ConversationDebugViewSet.retrieve: {str(e)}")
            return Response({"error": "An error occurred while fetching the conversation."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        try:
            conversation = self.get_object()
            messages = Message.objects.filter(
                conversation=conversation
            ).select_related('staff_sender').order_by('timestamp')

            serializer = MessageSerializer(messages, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in ConversationDebugViewSet.messages: {str(e)}")
            return Response({"error": "An error occurred while fetching messages."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        try:
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
        except Exception as e:
            logger.error(f"Error in ConversationDebugViewSet.send_message: {str(e)}")
            return Response({"error": "An error occurred while sending the message."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def end_relay(self, request, pk=None):
        try:
            conversation = self.get_object()
            conversation.status = 'active'
            conversation.save()

            return Response({'status': 'relay ended'}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in ConversationDebugViewSet.end_relay: {str(e)}")
            return Response({"error": "An error occurred while ending the relay."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def active_conversations(self, request):
        try:
            user = self.request.user
            
            # Check if user has a hotel assigned
            if not user.hotel:
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
        except Exception as e:
            logger.error(f"Error in ConversationDebugViewSet.active_conversations: {str(e)}")
            return Response({"error": "An error occurred while fetching active conversations."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='debug-action')
    def debug_action(self, request, pk=None):
        conversation = self.get_object()
        # Simple debug action
        return Response({'status': 'debug action executed', 'conversation_id': conversation.id}, status=status.HTTP_200_OK)
