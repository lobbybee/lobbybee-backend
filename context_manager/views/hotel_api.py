from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import FlowTemplate, FlowStepTemplate, FlowStep
from ..serializers import FlowStepTemplateSerializer, FlowStepTemplateDropdownSerializer
from hotel.models import Hotel
from hotel.permissions import IsHotelAdmin  # Import hotel admin permission
import logging

logger = logging.getLogger(__name__)


class CustomizableStepTemplateListView(generics.ListAPIView):
    """
    View for hotel admins to list all FlowStepTemplate records that are marked as customizable.
    """
    serializer_class = FlowStepTemplateSerializer
    permission_classes = [IsAuthenticated, IsHotelAdmin]

    def get_queryset(self):
        """
        Return all FlowStepTemplate records where is_customizable is True.
        """
        return FlowStepTemplate.objects.filter(is_customizable=True)


class FlowStepTemplateDropdownListView(generics.ListAPIView):
    """
    View for hotel admins to list all FlowStepTemplate records for dropdowns.
    Returns only id and step_name.
    """
    serializer_class = FlowStepTemplateDropdownSerializer
    permission_classes = [IsAuthenticated, IsHotelAdmin]
    pagination_class = None

    def get_queryset(self):
        """
        Return all FlowStepTemplate records.
        """
        return FlowStepTemplate.objects.all()
