from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import FlowTemplate, FlowStepTemplate, FlowAction
from ..serializers import FlowTemplateSerializer, FlowStepTemplateSerializer, FlowActionSerializer
import logging

logger = logging.getLogger(__name__)

class FlowTemplateListView(generics.ListCreateAPIView):
    """
    View for listing and creating FlowTemplate records.
    """
    serializer_class = FlowTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Return all FlowTemplate records.
        """
        return FlowTemplate.objects.all()

class FlowTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating, and deleting a specific FlowTemplate record.
    """
    serializer_class = FlowTemplateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        """
        Return all FlowTemplate records.
        """
        return FlowTemplate.objects.all()

class FlowStepTemplateListView(generics.ListCreateAPIView):
    """
    View for listing and creating FlowStepTemplate records.
    """
    serializer_class = FlowStepTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Return all FlowStepTemplate records, ordered by the 'order' field,
        then by ID. Optionally filtered by flow_template.
        """
        queryset = FlowStepTemplate.objects.all()
        flow_template_id = self.request.query_params.get('flow_template', None)
        if flow_template_id:
            queryset = queryset.filter(flow_template_id=flow_template_id)
        return queryset.order_by('order', 'id')

class FlowStepTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating, and deleting a specific FlowStepTemplate record.
    """
    serializer_class = FlowStepTemplateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        """
        Return all FlowStepTemplate records.
        """
        return FlowStepTemplate.objects.all()

class FlowActionListView(generics.ListCreateAPIView):
    """
    View for listing and creating FlowAction records.
    """
    serializer_class = FlowActionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Return all FlowAction records.
        """
        return FlowAction.objects.all()

class FlowActionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View for retrieving, updating, and deleting a specific FlowAction record.
    """
    serializer_class = FlowActionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        """
        Return all FlowAction records.
        """
        return FlowAction.objects.all()

