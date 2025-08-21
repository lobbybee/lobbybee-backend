from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import HotelFlowConfiguration, FlowTemplate, FlowStepTemplate, FlowStep
from ..serializers import HotelFlowConfigurationSerializer, HotelFlowDetailSerializer
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


class HotelFlowDetailView(generics.RetrieveAPIView):
    """
    Provides a detailed view of a flow template for hotel customization,
    including all steps and any existing customizations for that hotel.
    """
    serializer_class = HotelFlowDetailSerializer
    permission_classes = [IsAuthenticated]  # TODO: Replace with specific hotel permissions
    queryset = FlowTemplate.objects.all()
    lookup_url_kwarg = 'template_id'

    def get_serializer_context(self):
        """
        Passes the hotel object to the serializer.
        """
        context = super().get_serializer_context()
        try:
            hotel_id = self.kwargs['hotel_id']
            context['hotel'] = Hotel.objects.get(id=hotel_id)
        except (Hotel.DoesNotExist, KeyError):
            context['hotel'] = None
        return context

    def retrieve(self, request, *args, **kwargs):
        if 'hotel_id' not in self.kwargs:
            return Response(
                {'error': 'Hotel ID must be provided in the URL.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not self.get_serializer_context().get('hotel'):
            return Response(
                {'error': 'Hotel not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


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