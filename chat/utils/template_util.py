"""
Template utility functions for processing message templates.
Handles template processing, variable resolution, and fallback templates.
"""

from typing import Dict, List, Optional, Any
from django.db.models import Model
from django.utils import timezone
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

STAY_TIME_TEMPLATE_KEYS = {
    'checkin_time',
    'checkout_time',
    'check_in_time',
    'check_out_time',
}


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


def _format_stay_datetime_label(value, target_tz: Optional[ZoneInfo] = None):
    """
    Format stay datetime variables for templates.
    Example: '12 Wed March 12 PM'
    """
    if not value:
        return ''

    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = value.astimezone(target_tz) if target_tz else timezone.localtime(value)
        hour_label = value.strftime('%I').lstrip('0') or '0'
        return f"{value.day} {value.strftime('%a')} {value.strftime('%B')} {hour_label} {value.strftime('%p')}"

    if isinstance(value, time):
        return value.strftime('%I %p').lstrip('0')

    return value


def _format_human_time_with_minutes(value):
    """
    Format time as a guest-friendly label with minutes when needed.
    Examples: '2 PM', '2:30 PM'
    """
    if not value:
        return ''
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        if value.minute == 0:
            return value.strftime('%I %p').lstrip('0')
        return value.strftime('%I:%M %p').lstrip('0')
    return value


def _meal_end_time(meal_time) -> str:
    """
    Return the formatted end time for a meal service window (start + 2 hours).
    e.g. time(7, 30) → '9 AM'
    """
    if not meal_time:
        return ''
    dt = datetime.combine(datetime.today(), meal_time)
    end_dt = dt + timedelta(hours=2)
    return _format_human_datetime_label(end_dt.time())


from ..models import MessageTemplate, CustomMessageTemplate
from guest.models import Guest, Booking
from hotel.models import Hotel, Room
from user.models import User


# Template variable definitions with model and field references
TEMPLATE_VARIABLES = {
    # Guest related variables
    'guest_name': {
        'model': 'Guest',
        'field': 'get_first_name',
        'description': 'Guest first name',
        'example': 'John',
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
    'hotel_state': {
        'model': 'Hotel',
        'field': 'state',
        'description': 'Hotel state',
        'example': 'California',
    },
    'hotel_country': {
        'model': 'Hotel',
        'field': 'country',
        'description': 'Hotel country',
        'example': 'India',
    },
    'hotel_pincode': {
        'model': 'Hotel',
        'field': 'pincode',
        'description': 'Hotel postal/pin code',
        'example': '110001',
    },
    'google_map_link': {
        'model': 'Hotel',
        'field': 'google_map_link',
        'description': 'Google Maps link for the hotel',
        'example': 'https://maps.google.com/?q=Grand+Hotel',
    },
    'breakfast_time': {
        'model': 'Hotel',
        'field': 'breakfast_time',
        'description': 'Time when breakfast service starts',
        'example': '8 AM',
    },
    'breakfast_end_time': {
        'model': 'Hotel',
        'field': 'breakfast_time',
        'description': 'Time when breakfast service ends (start + 2 hours)',
        'example': '10 AM',
    },
    'lunch_time': {
        'model': 'Hotel',
        'field': 'lunch_time',
        'description': 'Time when lunch service starts',
        'example': '12 PM',
    },
    'lunch_end_time': {
        'model': 'Hotel',
        'field': 'lunch_time',
        'description': 'Time when lunch service ends (start + 2 hours)',
        'example': '2 PM',
    },
    'dinner_time': {
        'model': 'Hotel',
        'field': 'dinner_time',
        'description': 'Time when dinner service starts',
        'example': '7 PM',
    },
    'dinner_end_time': {
        'model': 'Hotel',
        'field': 'dinner_time',
        'description': 'Time when dinner service ends (start + 2 hours)',
        'example': '9 PM',
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
        'model': 'WiFiCredential',
        'field': 'network_name',
        'description': 'WiFi network name for the guest room/floor',
        'example': 'LobbyBee-Guest',
    },
    'wifi_password': {
        'model': 'WiFiCredential',
        'field': 'password',
        'description': 'WiFi password for the guest room/floor',
        'example': 'welcome123',
    },
    
    # Booking related variables
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
    
    # Stay variables
    'no_of_days': {
        'model': 'Stay',
        'field': 'no_of_days',
        'description': 'Number of days of the stay (check_out_date - check_in_date)',
        'example': '3',
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
            # Compute meal service end times (start + 2 hours)
            context['breakfast_end_time'] = _meal_end_time(hotel.breakfast_time)
            context['lunch_end_time'] = _meal_end_time(hotel.lunch_time)
            context['dinner_end_time'] = _meal_end_time(hotel.dinner_time)
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
                from hotel.models import WiFiCredential
                active_stay = Stay.objects.filter(guest=guest, status='active').first()
                room = None
                if active_stay:
                    # Use actual timestamps once available; fall back to planned values.
                    effective_check_in = active_stay.actual_check_in or active_stay.check_in_date
                    effective_check_out = active_stay.actual_check_out or active_stay.check_out_date
                    # Calculate number of stay days from calendar dates
                    no_of_days = (
                        effective_check_out.date() - effective_check_in.date()
                    ).days
                    context['no_of_days'] = no_of_days
                    if active_stay.room:
                        room = active_stay.room
                        context.update(_extract_model_fields(room, 'Room'))
                        logger.debug(f"Found room {room.room_number} from active stay {active_stay.id}")

                if room is None:
                    # Fallback: check if guest has a room attribute directly
                    if hasattr(guest, 'room') and guest.room:
                        room = guest.room
                        context.update(_extract_model_fields(room, 'Room'))
                        logger.debug(f"Found room {room.room_number} from guest.room attribute")
                    else:
                        logger.debug(f"No room found for guest {guest.id}")

                # Resolve WiFi credentials for the guest's room.
                # Mirrors RoomWiFiCredentialSerializer: prefer category-specific
                # over floor-wide by ordering on room_category__id descending.
                if room:
                    from django.db.models import Q
                    wifi_cred = WiFiCredential.objects.filter(
                        hotel_id=hotel_id,
                        floor=room.floor,
                        is_active=True,
                    ).filter(
                        Q(room_category=room.category) | Q(room_category__isnull=True)
                    ).order_by('-room_category__id').first()
                    if wifi_cred:
                        context['wifi_name'] = wifi_cred.network_name
                        context['wifi_password'] = wifi_cred.password
                        logger.debug(f"Resolved WiFi credentials for room {room.room_number}")
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

    # Keep explicitly provided context authoritative. This allows callers to
    # pass multi-room values (e.g. comma-separated room numbers/WiFi mappings)
    # without being overwritten by single active-stay fallback resolution.
    context.update(additional_context)
    
    # Add system variables in hotel-local timezone for guest-facing templates.
    tz_name = context.get('time_zone') or additional_context.get('hotel_timezone') or 'UTC'
    try:
        hotel_tz = ZoneInfo(tz_name)
    except Exception:
        hotel_tz = ZoneInfo('UTC')
    now = timezone.now().astimezone(hotel_tz)
    context.update({
        'current_date': now.strftime('%Y-%m-%d'),
        'current_time': _format_human_time_with_minutes(now),
    })
    
    return _normalize_template_context(context)


def _normalize_template_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply centralized value normalization for known template variables.
    """
    normalized = context.copy()
    tz_name = (
        normalized.get('hotel_timezone')
        or normalized.get('time_zone')
        or 'UTC'
    )
    try:
        hotel_tz = ZoneInfo(tz_name)
    except Exception:
        hotel_tz = ZoneInfo('UTC')
    for key in STAY_TIME_TEMPLATE_KEYS:
        if key in normalized:
            normalized[key] = _format_stay_datetime_label(normalized[key], target_tz=hotel_tz)
    return normalized


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
                    # Render hotel time fields as human-readable labels (e.g. '8 AM').
                    if (
                        model_name == 'Hotel'
                        and field_name in ['breakfast_time', 'lunch_time', 'dinner_time']
                    ):
                        fields[var_name] = _format_human_datetime_label(value) if value else ''
                        continue
                    # Prefer human labels for choice-based status values.
                    if model_name == 'Room' and field_name == 'status':
                        fields[var_name] = model_instance.get_status_display()
                        continue
                    if model_name == 'Booking' and field_name == 'status':
                        fields[var_name] = model_instance.get_status_display()
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
            value_for_template = value
            if value_for_template is None:
                value_for_template = ''
            elif isinstance(value_for_template, bool):
                value_for_template = 'Yes' if value_for_template else 'No'
            if double_brace_placeholder in rendered_content:
                rendered_content = rendered_content.replace(double_brace_placeholder, str(value_for_template))
                replacements_made += 1
                logger.debug(f"Replaced {double_brace_placeholder} with: {str(value_for_template)[:50]}")
            if single_brace_placeholder in rendered_content:
                rendered_content = rendered_content.replace(single_brace_placeholder, str(value_for_template))
                replacements_made += 1
                logger.debug(f"Replaced {single_brace_placeholder} with: {str(value_for_template)[:50]}")
        
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
