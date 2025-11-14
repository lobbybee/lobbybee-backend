"""
Template utility functions for processing message templates.
Handles template processing, variable resolution, and fallback templates.
"""

from typing import Dict, List, Optional, Any
from django.db.models import Model
from datetime import datetime

from ..models import MessageTemplate, CustomMessageTemplate
from guest.models import Guest, Booking
from hotel.models import Hotel, Room
from user.models import User


# Template variable definitions with model and field references
TEMPLATE_VARIABLES = {
    # Guest related variables
    'guest_name': {
        'model': 'Guest',
        'field': 'full_name',
        'description': 'Guest full name',
        'example': 'John Doe',
    },
    'guest_email': {
        'model': 'Guest',
        'field': 'email',
        'description': 'Guest email address',
        'example': 'john.doe@example.com',
    },
    'guest_whatsapp': {
        'model': 'Guest',
        'field': 'whatsapp_number',
        'description': 'Guest WhatsApp number',
        'example': '+1234567890',
    },
    'guest_register_number': {
        'model': 'Guest',
        'field': 'register_number',
        'description': 'Guest register number',
        'example': 'REG123456',
    },
    'guest_nationality': {
        'model': 'Guest',
        'field': 'nationality',
        'description': 'Guest nationality',
        'example': 'US',
    },
    
    # Hotel related variables
    'hotel_name': {
        'model': 'Hotel',
        'field': 'name',
        'description': 'Hotel name',
        'example': 'Grand Hotel',
    },
    'hotel_address': {
        'model': 'Hotel',
        'field': 'address',
        'description': 'Hotel address',
        'example': '123 Main St, City, Country',
    },
    'hotel_phone': {
        'model': 'Hotel',
        'field': 'phone',
        'description': 'Hotel main phone number',
        'example': '+1234567890',
    },
    'hotel_email': {
        'model': 'Hotel',
        'field': 'email',
        'description': 'Hotel email address',
        'example': 'info@grandhotel.com',
    },
    'hotel_city': {
        'model': 'Hotel',
        'field': 'city',
        'description': 'Hotel city',
        'example': 'New York',
    },
    
    # Room related variables
    'room_number': {
        'model': 'Room',
        'field': 'room_number',
        'description': 'Room number',
        'example': '101',
    },
    'room_floor': {
        'model': 'Room',
        'field': 'floor',
        'description': 'Room floor number',
        'example': '1',
    },
    'room_status': {
        'model': 'Room',
        'field': 'status',
        'description': 'Room status',
        'example': 'available',
    },
    
    # Booking related variables
    'check_in_date': {
        'model': 'Booking',
        'field': 'check_in_date',
        'description': 'Check-in date',
        'example': '2024-12-01',
    },
    'check_out_date': {
        'model': 'Booking',
        'field': 'check_out_date',
        'description': 'Check-out date',
        'example': '2024-12-03',
    },
    'booking_status': {
        'model': 'Booking',
        'field': 'status',
        'description': 'Booking status',
        'example': 'confirmed',
    },
    'booking_amount': {
        'model': 'Booking',
        'field': 'total_amount',
        'description': 'Total booking amount',
        'example': '299.99',
    },
    
    # Dynamic variables
    'current_date': {
        'model': 'System',
        'field': 'current_date',
        'description': 'Current date',
        'example': '2024-11-08',
    },
    'current_time': {
        'model': 'System',
        'field': 'current_time',
        'description': 'Current time',
        'example': '14:30',
    },
}


# Essential templates with hardcoded fallbacks
ESSENTIAL_TEMPLATES = {
    'welcome': {
        'name': 'Welcome Message',
        'content': 'Hello {{guest_name}}, welcome to {{hotel_name}}! Your room {{room_number}} is ready. We hope you enjoy your stay.',
        'template_type': 'welcome',
        'category': 'guest_services',
        'variables': ['guest_name', 'hotel_name', 'room_number'],
    },
    'checkout': {
        'name': 'Check-out Reminder',
        'content': 'Dear {{guest_name}}, your check-out is today at 11:00 AM. We hope you enjoyed your stay at {{hotel_name}}!',
        'template_type': 'checkout',
        'category': 'guest_services',
        'variables': ['guest_name', 'hotel_name'],
    },
    'housekeeping': {
        'name': 'Housekeeping Request',
        'content': 'Hello {{guest_name}}, our housekeeping team will be at your room {{room_number}} shortly.',
        'template_type': 'housekeeping',
        'category': 'operational',
        'variables': ['guest_name', 'room_number'],
    },
    'maintenance': {
        'name': 'Maintenance Update',
        'content': 'Dear {{guest_name}}, we are working on the maintenance issue in room {{room_number}}. We apologize for any inconvenience.',
        'template_type': 'maintenance',
        'category': 'operational',
        'variables': ['guest_name', 'room_number'],
    },
    'emergency': {
        'name': 'Emergency Alert',
        'content': 'Emergency situation detected. Please remain calm and follow staff instructions. Contact {{hotel_phone}} if needed.',
        'template_type': 'emergency',
        'category': 'emergency',
        'variables': ['hotel_phone'],
    },
}


def get_template_variables() -> List[Dict[str, Any]]:
    """
    Get all available template variables with their details.
    
    Returns:
        List of template variables with model, field, description, and example.
    """
    variables = []
    for var_name, var_info in TEMPLATE_VARIABLES.items():
        variables.append({
            'name': var_name,
            'model': var_info['model'],
            'field': var_info['field'],
            'description': var_info['description'],
            'example': var_info['example'],
        })
    return variables


def process_template(
    hotel_id: int,
    template_name: str,
    guest_id: Optional[int] = None,
    additional_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a template with the given context.
    
    Args:
        hotel_id: Hotel ID for custom template lookup
        template_name: Name of the template to process
        guest_id: Optional guest ID for variable resolution
        additional_context: Additional context variables
    
    Returns:
        Dictionary with processed template content and metadata
    """
    try:
        # Step 1: Try to get custom template first
        template = None
        template_type = None
        
        try:
            template = CustomMessageTemplate.objects.get(
                hotel_id=hotel_id,
                name=template_name,
                is_active=True
            )
            template_type = 'custom'
        except CustomMessageTemplate.DoesNotExist:
            pass
        
        # Step 2: Fallback to global template
        if template is None:
            try:
                template = MessageTemplate.objects.get(
                    name=template_name,
                    is_active=True
                )
                template_type = 'global'
            except MessageTemplate.DoesNotExist:
                pass
        
        # Step 3: Fallback to essential template if available
        if template is None and template_name in ESSENTIAL_TEMPLATES:
            essential_template = ESSENTIAL_TEMPLATES[template_name]
            template = {
                'content': essential_template['content'],
                'variables': essential_template['variables'],
                'name': essential_template['name'],
                'template_type': essential_template['template_type'],
                'category': essential_template['category'],
            }
            template_type = 'essential'
        
        # Step 4: If no template found, raise error
        if template is None:
            return {
                'success': False,
                'error': f'Template "{template_name}" not found',
                'template_name': template_name,
                'hotel_id': hotel_id,
            }
        
        # Step 5: Resolve variables
        context = _resolve_variables(hotel_id, guest_id, additional_context or {})
        
        # Step 6: Process template content
        if hasattr(template, 'text_content'):
            content = template.text_content
        else:
            content = template['content']
        
        processed_content = _render_template(content, context)
        
        return {
            'success': True,
            'template_name': template_name,
            'template_type': template_type,
            'original_content': content,
            'processed_content': processed_content,
            'context': context,
            'hotel_id': hotel_id,
            'guest_id': guest_id,
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error processing template: {str(e)}',
            'template_name': template_name,
            'hotel_id': hotel_id,
        }


def _resolve_variables(
    hotel_id: int,
    guest_id: Optional[int],
    additional_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Resolve template variables from database models.
    
    Args:
        hotel_id: Hotel ID
        guest_id: Optional guest ID
        additional_context: Additional context variables
    
    Returns:
        Dictionary with resolved variables
    """
    context = additional_context.copy()
    
    try:
        # Get hotel information
        if hotel_id:
            hotel = Hotel.objects.get(id=hotel_id)
            context.update(_extract_model_fields(hotel, 'Hotel'))
    except Hotel.DoesNotExist:
        pass
    
    try:
        # Get guest information
        if guest_id:
            guest = Guest.objects.get(id=guest_id)
            context.update(_extract_model_fields(guest, 'Guest'))
            
            # Get current room information if available
            if hasattr(guest, 'room') and guest.room:
                room = guest.room
                context.update(_extract_model_fields(room, 'Room'))
            
            # Get latest booking information if available
            latest_booking = guest.bookings.last()
            if latest_booking:
                context.update(_extract_model_fields(latest_booking, 'Booking'))
                
                # Get room from booking if different from guest room
                if hasattr(latest_booking, 'room') and latest_booking.room:
                    booking_room = latest_booking.room
                    context.update({
                        'booking_room_number': booking_room.room_number,
                        'booking_room_floor': booking_room.floor,
                        'booking_room_status': booking_room.status,
                    })
    except Guest.DoesNotExist:
        pass
    
    # Add system variables
    now = datetime.now()
    context.update({
        'current_date': now.strftime('%Y-%m-%d'),
        'current_time': now.strftime('%H:%M'),
    })
    
    return context


def _extract_model_fields(model_instance: Model, model_name: str) -> Dict[str, Any]:
    """
    Extract fields from a model instance based on template variable definitions.
    
    Args:
        model_instance: The model instance
        model_name: Name of the model for filtering variables
    
    Returns:
        Dictionary with extracted field values
    """
    fields = {}
    
    for var_name, var_info in TEMPLATE_VARIABLES.items():
        if var_info['model'] == model_name:
            field_name = var_info['field']
            
            if hasattr(model_instance, field_name):
                value = getattr(model_instance, field_name)
                if callable(value):
                    # For methods like get_full_name()
                    fields[var_name] = value()
                else:
                    fields[var_name] = value
    
    return fields


def _render_template(template_content: str, context: Dict[str, Any]) -> str:
    """
    Render template content with context variables.
    
    Args:
        template_content: Template string with {{variables}}
        context: Dictionary with variable values
    
    Returns:
        Rendered content string
    """
    try:
        # Simple template rendering - replace {{variable}} with actual values
        rendered_content = template_content
        for var_name, value in context.items():
            placeholder = f'{{{{{var_name}}}}}'
            rendered_content = rendered_content.replace(placeholder, str(value))
        
        return rendered_content
    except Exception:
        # If rendering fails, return original content
        return template_content


def get_essential_templates() -> List[Dict[str, Any]]:
    """
    Get all essential templates with their information.
    
    Returns:
        List of essential templates
    """
    templates = []
    for template_name, template_info in ESSENTIAL_TEMPLATES.items():
        templates.append({
            'name': template_name,
            'display_name': template_info['name'],
            'content': template_info['content'],
            'template_type': template_info['template_type'],
            'category': template_info['category'],
            'variables': template_info['variables'],
            'is_essential': True,
        })
    return templates