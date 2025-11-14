"""
Template management views for MessageTemplate and CustomMessageTemplate.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from django.shortcuts import get_object_or_404

from ..models import MessageTemplate, CustomMessageTemplate
from ..serializers import MessageTemplateSerializer, CustomMessageTemplateSerializer
from user.permissions import IsSuperUserOrPlatformStaff, IsHotelAdmin
from ..utils.template_util import get_template_variables


class MessageTemplateListCreateView(ListCreateAPIView):
    """
    List all message templates or create a new one.
    Only superusers and platform staff can create/update global templates.
    """
    queryset = MessageTemplate.objects.all().order_by('name')
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            self.permission_classes = [IsAuthenticated, IsSuperUserOrPlatformStaff]
        return super().get_permissions()


class MessageTemplateDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a message template.
    Only superusers and platform staff can update/delete global templates.
    """
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            self.permission_classes = [IsAuthenticated, IsSuperUserOrPlatformStaff]
        return super().get_permissions()


class CustomMessageTemplateListCreateView(ListCreateAPIView):
    """
    List all custom message templates for the hotel or create a new one.
    Only hotel admins can create/update custom templates for their hotel.
    """
    serializer_class = CustomMessageTemplateSerializer
    permission_classes = [IsAuthenticated, IsHotelAdmin]

    def get_queryset(self):
        # Only return templates for the user's hotel
        if hasattr(self.request.user, 'hotel'):
            return CustomMessageTemplate.objects.filter(
                hotel=self.request.user.hotel
            ).order_by('name')
        return CustomMessageTemplate.objects.none()

    def perform_create(self, serializer):
        # Automatically set the hotel to the user's hotel
        if hasattr(self.request.user, 'hotel'):
            serializer.save(hotel=self.request.user.hotel)


class CustomMessageTemplateDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a custom message template.
    Only hotel admins can update/delete custom templates for their hotel.
    """
    serializer_class = CustomMessageTemplateSerializer
    permission_classes = [IsAuthenticated, IsHotelAdmin]

    def get_queryset(self):
        # Only return templates for the user's hotel
        if hasattr(self.request.user, 'hotel'):
            return CustomMessageTemplate.objects.filter(
                hotel=self.request.user.hotel
            )
        return CustomMessageTemplate.objects.none()

    def get_object(self):
        obj = super().get_object()
        # Additional check to ensure the template belongs to the user's hotel
        if hasattr(self.request.user, 'hotel') and obj.hotel != self.request.user.hotel:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to access this template.")
        return obj


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def template_types_view(request):
    """
    Get available template types and categories.
    """
    template_types = MessageTemplate.TEMPLATE_TYPE_CHOICES
    categories = MessageTemplate.TEMPLATE_TYPE_CHOICES  # Using same choices for categories
    
    return Response({
        'template_types': template_types,
        'categories': categories,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def render_template_preview(request, template_id):
    """
    Render a template preview with sample data.
    """
    try:
        template = MessageTemplate.objects.get(id=template_id)
        
        # Sample data for preview
        sample_data = {
            'guest_name': 'John Doe',
            'room_number': '101',
            'hotel_name': 'Sample Hotel',
            'check_in_date': '2024-12-01',
            'check_out_date': '2024-12-03',
            'booking_reference': 'BK123456',
        }
        
        rendered_content = template.render_content(sample_data)
        
        return Response({
            'template_id': template.id,
            'template_name': template.name,
            'rendered_content': rendered_content,
            'sample_data': sample_data,
        })
    except MessageTemplate.DoesNotExist:
        return Response(
            {'error': 'Template not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def template_variables_view(request):
    """
    Get all available template variables with their model and field information.
    """
    try:
        variables = get_template_variables()
        
        # Group variables by model for better organization
        grouped_variables = {}
        for var in variables:
            model_name = var['model']
            if model_name not in grouped_variables:
                grouped_variables[model_name] = []
            grouped_variables[model_name].append(var)
        
        return Response({
            'variables': variables,
            'grouped_by_model': grouped_variables,
            'total_count': len(variables),
        })
    except Exception as e:
        logger.error(f"Error in template_variables_view: {e}")
        return Response(
            {'error': 'Error retrieving template variables'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )