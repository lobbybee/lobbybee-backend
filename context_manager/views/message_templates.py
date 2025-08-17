from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from ..models import ScheduledMessageTemplate
from ..serializers import ScheduledMessageTemplateSerializer
from hotel.models import Hotel
import logging

logger = logging.getLogger(__name__)

class ScheduledMessageTemplateListView(generics.ListCreateAPIView):
    """
    View for listing and creating ScheduledMessageTemplate records.
    """
    serializer_class = ScheduledMessageTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter ScheduledMessageTemplate records by hotel_id from URL parameter.
        """
        hotel_id = self.kwargs['hotel_id']
        return ScheduledMessageTemplate.objects.filter(hotel_id=hotel_id)
    
    def perform_create(self, serializer):
        """
        Create a new ScheduledMessageTemplate record with the hotel from URL parameter.
        """
        hotel_id = self.kwargs['hotel_id']
        try:
            hotel = Hotel.objects.get(id=hotel_id)
            serializer.save(hotel=hotel)
        except Hotel.DoesNotExist:
            logger.error(f"Hotel with id {hotel_id} does not exist")
            raise ValidationError("Invalid hotel ID")
    
    def create(self, request, *args, **kwargs):
        """
        Handle POST request to create a new ScheduledMessageTemplate.
        """
        hotel_id = self.kwargs['hotel_id']
        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            return Response(
                {'error': 'Hotel not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Add hotel to request data
        request_data = request.data.copy()
        request_data['hotel'] = str(hotel_id)
        
        serializer = self.get_serializer(data=request_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class ScheduledMessageTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating, and deleting a specific ScheduledMessageTemplate record.
    """
    serializer_class = ScheduledMessageTemplateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'
    
    def get_queryset(self):
        """
        Filter ScheduledMessageTemplate records by hotel_id from URL parameter.
        """
        hotel_id = self.kwargs['hotel_id']
        return ScheduledMessageTemplate.objects.filter(hotel_id=hotel_id)
    
    def update(self, request, *args, **kwargs):
        """
        Handle PUT request to update a ScheduledMessageTemplate.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """
        Handle DELETE request to remove a ScheduledMessageTemplate.
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
