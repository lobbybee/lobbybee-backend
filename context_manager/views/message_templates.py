from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from ..models import ScheduledMessageTemplate
from ..serializers import ScheduledMessageTemplateSerializer
from hotel.models import Hotel
from hotel.permissions import IsHotelAdmin  # Import hotel admin permission
import logging

logger = logging.getLogger(__name__)

class ScheduledMessageTemplateListView(generics.ListCreateAPIView):
    """
    View for listing and creating ScheduledMessageTemplate records for the authenticated user's hotel.
    """
    serializer_class = ScheduledMessageTemplateSerializer
    permission_classes = [IsAuthenticated, IsHotelAdmin]  # Add IsHotelAdmin permission
    
    def get_queryset(self):
        """
        Filter ScheduledMessageTemplate records by the authenticated user's hotel.
        """
        # Use the hotel from the authenticated user
        return ScheduledMessageTemplate.objects.filter(hotel=self.request.user.hotel)
    
    def perform_create(self, serializer):
        """
        Create a new ScheduledMessageTemplate record with the authenticated user's hotel.
        """
        # Use the hotel from the authenticated user
        serializer.save(hotel=self.request.user.hotel)
    
    def create(self, request, *args, **kwargs):
        """
        Handle POST request to create a new ScheduledMessageTemplate.
        """
        # Check if user has a hotel assigned
        if not self.request.user.hotel:
            return Response(
                {'error': 'User is not associated with a hotel.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # No need to add hotel to request data anymore
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class ScheduledMessageTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating, and deleting a specific ScheduledMessageTemplate record for the authenticated user's hotel.
    """
    serializer_class = ScheduledMessageTemplateSerializer
    permission_classes = [IsAuthenticated, IsHotelAdmin]  # Add IsHotelAdmin permission
    lookup_field = 'pk'
    
    def get_queryset(self):
        """
        Filter ScheduledMessageTemplate records by the authenticated user's hotel.
        """
        # Use the hotel from the authenticated user
        return ScheduledMessageTemplate.objects.filter(hotel=self.request.user.hotel)
    
    def update(self, request, *args, **kwargs):
        """
        Handle PUT request to update a ScheduledMessageTemplate.
        """
        # Check if user has a hotel assigned
        if not self.request.user.hotel:
            return Response(
                {'error': 'User is not associated with a hotel.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
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
        # Check if user has a hotel assigned
        if not self.request.user.hotel:
            return Response(
                {'error': 'User is not associated with a hotel.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
