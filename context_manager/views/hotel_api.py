from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import HotelFlowConfiguration, FlowTemplate, FlowStepTemplate, FlowStep
from ..serializers import HotelFlowConfigurationSerializer
from hotel.models import Hotel
import logging

logger = logging.getLogger(__name__)

class HotelFlowConfigurationListView(generics.ListAPIView):
    """
    View for listing FlowTemplate configurations available to a hotel.
    """
    serializer_class = HotelFlowConfigurationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Return HotelFlowConfiguration records for the specified hotel.
        """
        hotel_id = self.kwargs['hotel_id']
        return HotelFlowConfiguration.objects.filter(hotel_id=hotel_id)

class HotelFlowCustomizeView(generics.UpdateAPIView):
    """
    View for customizing a flow template for a specific hotel.
    """
    serializer_class = HotelFlowConfigurationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'template_id'
    
    def get_queryset(self):
        """
        Return HotelFlowConfiguration records for the specified hotel and template.
        """
        hotel_id = self.kwargs['hotel_id']
        template_id = self.kwargs['template_id']
        return HotelFlowConfiguration.objects.filter(hotel_id=hotel_id, flow_template_id=template_id)
    
    def update(self, request, *args, **kwargs):
        """
        Update the customization data for a hotel's flow template.
        """
        hotel_id = self.kwargs['hotel_id']
        template_id = self.kwargs['template_id']
        
        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            return Response(
                {'error': 'Hotel not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            flow_template = FlowTemplate.objects.get(id=template_id)
        except FlowTemplate.DoesNotExist:
            return Response(
                {'error': 'Flow template not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get or create the hotel flow configuration
        configuration, created = HotelFlowConfiguration.objects.get_or_create(
            hotel=hotel,
            flow_template=flow_template,
            defaults={
                'customization_data': request.data.get('customization_data', {})
            }
        )
        
        if not created:
            # Update existing configuration
            configuration.customization_data = request.data.get('customization_data', {})
            configuration.save()
        
        serializer = self.get_serializer(configuration)
        return Response(serializer.data)