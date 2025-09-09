from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from ..models import FlowStep, FlowStepTemplate
from ..serializers import FlowStepSerializer, FlowStepUpdateSerializer
from hotel.models import Hotel
from hotel.permissions import IsHotelAdmin  # Import hotel admin permission
import logging

logger = logging.getLogger(__name__)

class FlowStepListView(generics.ListCreateAPIView):
    """
    View for listing and creating FlowStep records for the authenticated user's hotel.
    """
    serializer_class = FlowStepSerializer
    permission_classes = [IsAuthenticated, IsHotelAdmin]  # Add IsHotelAdmin permission
    
    def get_queryset(self):
        """
        Filter FlowStep records by the authenticated user's hotel.
        """
        # Use the hotel from the authenticated user
        return FlowStep.objects.filter(hotel=self.request.user.hotel)
    
    def create(self, request, *args, **kwargs):
        """
        Handle POST request to create a new FlowStep for a hotel by copying a FlowStepTemplate.
        This is the entry point for a hotel admin to customize a template.
        """
        hotel = request.user.hotel
        if not hotel:
            return Response(
                {'error': 'User is not associated with a hotel.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        template_id = request.data.get('template')
        if not template_id:
            return Response(
                {'error': 'FlowStepTemplate ID must be provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            template = FlowStepTemplate.objects.get(id=template_id)
        except FlowStepTemplate.DoesNotExist:
            return Response(
                {'error': 'FlowStepTemplate not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not template.is_customizable:
            return Response(
                {'error': 'This FlowStepTemplate is not customizable.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if a FlowStep for this hotel and template already exists
        if FlowStep.objects.filter(hotel=hotel, template=template).exists():
            return Response(
                {'error': 'A customized FlowStep for this template already exists for your hotel.'},
                status=status.HTTP_409_CONFLICT
            )

        # Create the hotel-specific FlowStep by copying from the template
        flow_step = FlowStep.objects.create(
            hotel=hotel,
            template=template,
            step_id=template.step_name.lower().replace(' ', '_'), # Generate a step_id
            message_template=template.message_template,
            message_type=template.message_type,
            options=template.options,
            media=template.media # Copy the media file reference
        )

        serializer = self.get_serializer(flow_step)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class FlowStepDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating, and deleting a specific FlowStep record for the authenticated user's hotel.
    """
    serializer_class = FlowStepUpdateSerializer
    permission_classes = [IsAuthenticated, IsHotelAdmin]  # Add IsHotelAdmin permission
    lookup_field = 'pk'
    
    def get_queryset(self):
        """
        Filter FlowStep records by the authenticated user's hotel.
        """
        # Use the hotel from the authenticated user
        return FlowStep.objects.filter(hotel=self.request.user.hotel)
    
    def update(self, request, *args, **kwargs):
        """
        Handle PUT request to update a FlowStep.
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
        Handle DELETE request to remove a FlowStep.
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
