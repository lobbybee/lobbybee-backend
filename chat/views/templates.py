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
    Hotel users can only see templates that are customizable.
    """
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Superusers and platform staff can see all templates
        if self.request.user.is_superuser or self.request.user.user_type == 'platform_staff':
            return MessageTemplate.objects.all().order_by('name')
        
        # Hotel users can only see customizable and active templates
        return MessageTemplate.objects.filter(
            is_customizable=True,
            is_active=True
        ).order_by('name')

    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            self.permission_classes = [IsAuthenticated, IsSuperUserOrPlatformStaff]
        return super().get_permissions()


class MessageTemplateDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a message template.
    Only superusers and platform staff can update/delete global templates.
    Hotel users can only view templates that are customizable and active.
    """
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Superusers and platform staff can see all templates
        if self.request.user.is_superuser or self.request.user.user_type == 'platform_staff':
            return MessageTemplate.objects.all()
        
        # Hotel users can only see customizable and active templates
        return MessageTemplate.objects.filter(
            is_customizable=True,
            is_active=True
        )

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
    Supports both MessageTemplate and CustomMessageTemplate.
    """
    try:
        # Try to find template in both models
        template = None
        template_type = None
        
        # First try MessageTemplate
        try:
            template = MessageTemplate.objects.get(id=template_id)
            template_type = 'global'
        except MessageTemplate.DoesNotExist:
            # If not found, try CustomMessageTemplate
            template = CustomMessageTemplate.objects.get(id=template_id)
            template_type = 'custom'
            
            # Check permissions - only allow hotel users to preview their own templates
            if hasattr(request.user, 'hotel') and template.hotel != request.user.hotel:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You don't have permission to preview this template.")
        
        # Import the render utility and template variables
        from ..utils.template_util import _render_template, TEMPLATE_VARIABLES
        
        # Build sample data from template variable examples
        sample_data = {}
        for var_name, var_info in TEMPLATE_VARIABLES.items():
            sample_data[var_name] = var_info['example']
        
        # Override hotel_name if it's a custom template
        if template_type == 'custom' and template.hotel:
            sample_data['hotel_name'] = template.hotel.name
        
        # Update dynamic variables with current values
        from datetime import datetime
        now = datetime.now()
        sample_data['current_date'] = now.strftime('%Y-%m-%d')
        sample_data['current_time'] = now.strftime('%H:%M')
        
        # Render the template using the utility function
        rendered_content = _render_template(template.text_content, sample_data)
        
        # Prepare response data
        response_data = {
            'template_id': template.id,
            'template_name': template.name,
            'template_type': template.template_type,
            'template_model': template_type,  # 'global' or 'custom'
            'rendered_content': rendered_content,
            'sample_data': sample_data,
        }
        
        # Add hotel info for custom templates
        if template_type == 'custom' and template.hotel:
            response_data['hotel_id'] = template.hotel.id
            response_data['hotel_name'] = template.hotel.name
        
        # Add media information if exists
        if hasattr(template, 'get_media_url'):
            media_url = template.get_media_url
            if media_url:
                response_data['media_url'] = media_url
                response_data['media_filename'] = getattr(template, 'media_filename', None)
        
        return Response(response_data)
    except (MessageTemplate.DoesNotExist, CustomMessageTemplate.DoesNotExist):
        return Response(
            {'error': 'Template not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error rendering template preview: {e}")
        return Response(
            {'error': 'Error rendering template preview'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
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