"""
Template utility functions for processing message templates.
Handles template processing, variable resolution, and fallback templates.
"""

from typing import Dict, List, Optional, Any
from django.db.models import Model
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


def _format_human_datetime_label(value):
    """
    Format datetime/time values for guest-facing templates.
    Expected style: '26 Monday 12 PM'
    """
    if isinstance(value, datetime):
        hour_label = value.strftime('%I %p').lstrip('0')
        return f"{value.day} {value.strftime('%A')} {hour_label}"
    if isinstance(value, time):
        return value.strftime('%I %p').lstrip('0')
    return value

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
    'wifi_name': {
        'model': 'System',
        'field': 'wifi_name',
        'description': 'WiFi network name for the guest room/floor',
        'example': 'LobbyBee-Guest',
    },
    'wifi_password': {
        'model': 'System',
        'field': 'wifi_password',
        'description': 'WiFi password for the guest room/floor',
        'example': 'welcome123',
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
    'checkin_time': {
        'model': 'System',
        'field': 'checkin_time',
        'description': 'Guest check-in time for the active stay',
        'example': '14:00',
    },
    'checkout_time': {
        'model': 'System',
        'field': 'checkout_time',
        'description': 'Guest check-out time for the active stay',
        'example': '11:00',
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
    logger.info(f"Processing template '{template_name}' for hotel {hotel_id}, guest {guest_id}")
    
    try:
        # Step 1: Try to get custom template first
        template = None
        template_type = None
        
        try:
            logger.debug(f"Searching for custom template '{template_name}' for hotel {hotel_id}")
            
            # First try to find custom template by name
            template = CustomMessageTemplate.objects.get(
                hotel_id=hotel_id,
                name=template_name,
                is_active=True
            )
            template_type = 'custom'
            logger.info(f"Found custom template '{template_name}' for hotel {hotel_id}")
            
        except CustomMessageTemplate.DoesNotExist:
            logger.info(f"No direct custom template '{template_name}' found for hotel {hotel_id}")
            
            # Check if there's a custom template that uses this as base template
            try:
                global_template = MessageTemplate.objects.get(name=template_name, is_active=True)
                logger.debug(f"Found global template '{template_name}', checking for custom overrides")
                
                custom_templates = CustomMessageTemplate.objects.filter(
                    hotel_id=hotel_id,
                    base_template=global_template,
                    is_active=True
                )
                
                if custom_templates.exists():
                    template = custom_templates.first()
                    template_type = 'custom_override'
                    logger.info(f"Found custom template override for '{template_name}' with name '{template.name}'")
                
            except MessageTemplate.DoesNotExist:
                logger.debug(f"No global template '{template_name}' found to check for overrides")
                pass
        
        # Step 2: Fallback to global template
        if template is None:
            try:
                logger.debug(f"Searching for global template '{template_name}'")
                template = MessageTemplate.objects.get(
                    name=template_name,
                    is_active=True
                )
                template_type = 'global'
                logger.info(f"Found global template '{template_name}'")
            except MessageTemplate.DoesNotExist:
                logger.info(f"No global template '{template_name}' found")
                pass
        
        # Step 3: Fallback to essential template if available
        if template is None and template_name in ESSENTIAL_TEMPLATES:
            logger.debug(f"Using essential template '{template_name}'")
            essential_template = ESSENTIAL_TEMPLATES[template_name]
            template = {
                'content': essential_template['content'],
                'variables': essential_template['variables'],
                'name': essential_template['name'],
                'template_type': essential_template['template_type'],
                'category': essential_template['category'],
            }
            template_type = 'essential'
            logger.info(f"Using essential template '{template_name}'")
        
        # Step 4: If no template found, raise error
        if template is None:
            logger.error(f"Template '{template_name}' not found in any source")
            return {
                'success': False,
                'error': f'Template "{template_name}" not found',
                'template_name': template_name,
                'hotel_id': hotel_id,
            }
        
        logger.info(f"Template '{template_name}' found, type: {template_type}")
        logger.debug(f"Template object type: {type(template)}")
        logger.debug(f"Template object attributes: {dir(template) if hasattr(template, '__dict__') else 'N/A'}")
        
        # Step 5: Resolve variables
        logger.info(f"Resolving variables for guest {guest_id}")
        context = _resolve_variables(hotel_id, guest_id, additional_context or {})
        logger.info(f"Resolved context variables: {list(context.keys())}")
        logger.debug(f"Context sample: {dict(list(context.items())[:5])}")
        
        # Step 6: Process template content
        logger.info(f"Processing template content for '{template_name}'")
        
        if hasattr(template, 'text_content'):
            logger.debug(f"Template has text_content attribute")
            # Check if text_content is callable
            if callable(template.text_content):
                logger.debug(f"template.text_content is callable, calling it...")
                content = template.text_content()
            else:
                logger.debug(f"template.text_content is not callable, using as property")
                content = template.text_content
            logger.info(f"Using template.text_content: {content[:50] if content else 'None'}...")
        elif isinstance(template, dict) and 'content' in template:
            logger.debug(f"Template is dict with 'content' key")
            content = template['content']
            logger.info(f"Using template['content']: {content[:50] if content else 'None'}...")
        else:
            logger.error(f"Template object has no content! Template type: {type(template)}, Template: {template}")
            return {
                'success': False,
                'error': f'Template "{template_name}" has no content field',
                'template_name': template_name,
                'hotel_id': hotel_id,
            }
        
        logger.info(f"Original content: {content}")
        processed_content = _render_template(content, context)
        logger.info(f"Template processed successfully: {processed_content[:50] if processed_content else 'None'}...")
        
        # Step 7: Get media URL if template has media
        logger.info(f"Checking for media in template '{template_name}'")
        media_url = None
        
        # Check for get_media_url method or property
        if hasattr(template, 'get_media_url'):
            logger.debug(f"Template has get_media_url attribute")
            if callable(template.get_media_url):
                logger.debug(f"template.get_media_url is callable, calling it...")
                try:
                    media_url = template.get_media_url()
                    logger.debug(f"template.get_media_url() returned: {media_url}")
                except Exception as e:
                    logger.error(f"Error calling template.get_media_url(): {str(e)}")
                    media_url = None
            else:
                logger.debug(f"template.get_media_url is not callable, using as property")
                media_url = template.get_media_url
            logger.debug(f"Template media URL from get_media_url: {media_url}")
        
        # Check for media_file attribute
        if hasattr(template, 'media_file'):
            logger.debug(f"Template has media_file attribute")
            if template.media_file:
                if hasattr(template.media_file, 'url'):
                    media_url = template.media_file.url
                    logger.debug(f"Template media_file.url: {media_url}")
                else:
                    logger.debug(f"Template media_file has no url attribute")
            else:
                logger.debug(f"Template media_file is None/empty")
        
        logger.info(f"Final media URL: {media_url}")
        
        result = {
            'success': True,
            'template_name': template_name,
            'template_type': template_type,
            'original_content': content,
            'processed_content': processed_content,
            'media_url': media_url,
            'context': context,
            'hotel_id': hotel_id,
            'guest_id': guest_id,
        }
        
        logger.info(f"Template processing completed successfully for '{template_name}'")
        return result
        
    except Exception as e:
        logger.error(f"Error processing template '{template_name}' for hotel {hotel_id}, guest {guest_id}: {str(e)}", exc_info=True)
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
            from guest.models import Stay  # Import here to avoid circular imports
            
            guest = Guest.objects.get(id=guest_id)
            context.update(_extract_model_fields(guest, 'Guest'))
            
            # Get current room information from the guest's active stay
            try:
                active_stay = Stay.objects.filter(guest=guest, status='active').first()
                if active_stay and active_stay.room:
                    room = active_stay.room
                    context.update(_extract_model_fields(room, 'Room'))
                    logger.debug(f"Found room {room.room_number} from active stay {active_stay.id}")
                else:
                    # Fallback: check if guest has a room attribute directly
                    if hasattr(guest, 'room') and guest.room:
                        room = guest.room
                        context.update(_extract_model_fields(room, 'Room'))
                        logger.debug(f"Found room {room.room_number} from guest.room attribute")
                    else:
                        logger.debug(f"No room found for guest {guest.id}")
            except Exception as e:
                logger.error(f"Error getting room from stay for guest {guest.id}: {str(e)}")
            
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
    logger.debug(f"Extracting fields from {model_name} model instance: {type(model_instance)}")
    fields = {}
    
    for var_name, var_info in TEMPLATE_VARIABLES.items():
        if var_info['model'] == model_name:
            field_name = var_info['field']
            logger.debug(f"Processing field {field_name} for variable {var_name}")
            
            if hasattr(model_instance, field_name):
                value = getattr(model_instance, field_name)
                logger.debug(f"Field {field_name} found, value type: {type(value)}")
                
                if callable(value):
                    logger.debug(f"Field {field_name} is callable, executing...")
                    try:
                        # For methods like get_full_name()
                        result = value()
                        logger.debug(f"Callable field {field_name} returned: {type(result)} = {result}")
                        fields[var_name] = result
                    except Exception as e:
                        logger.error(f"Error calling callable field {field_name}: {str(e)}")
                        fields[var_name] = None
                else:
                    logger.debug(f"Field {field_name} is not callable, value: {value}")
                    # Render booking check-in/out fields as human-readable labels
                    # for template usage (e.g. '26 Monday 12 PM').
                    if (
                        model_name == 'Booking'
                        and field_name in ['check_in_date', 'check_out_date']
                    ):
                        fields[var_name] = _format_human_datetime_label(value)
                        continue
                    fields[var_name] = value
            else:
                logger.debug(f"Field {field_name} not found in {model_name} model instance")
    
    logger.debug(f"Extracted fields for {model_name}: {list(fields.keys())}")
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
    logger.debug(f"Rendering template: {template_content}")
    logger.debug(f"Available context variables: {list(context.keys())}")
    
    try:
        # Simple template rendering - replace {{variable}} with actual values
        rendered_content = template_content
        replacements_made = 0
        
        for var_name, value in context.items():
            # Support both {{var}} and {var} placeholders.
            double_brace_placeholder = f'{{{{{var_name}}}}}'
            single_brace_placeholder = f'{{{var_name}}}'
            if double_brace_placeholder in rendered_content:
                rendered_content = rendered_content.replace(double_brace_placeholder, str(value))
                replacements_made += 1
                logger.debug(f"Replaced {double_brace_placeholder} with: {str(value)[:50]}")
            if single_brace_placeholder in rendered_content:
                rendered_content = rendered_content.replace(single_brace_placeholder, str(value))
                replacements_made += 1
                logger.debug(f"Replaced {single_brace_placeholder} with: {str(value)[:50]}")
        
        logger.debug(f"Template rendering completed. Made {replacements_made} replacements.")
        logger.debug(f"Final rendered content: {rendered_content}")
        return rendered_content
    except Exception as e:
        logger.error(f"Error rendering template: {str(e)}", exc_info=True)
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
