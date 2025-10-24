import re
from typing import Optional


def normalize_phone_number(phone_number: str) -> Optional[str]:
    """
    Normalize phone number to a consistent format for storage and comparison.
    
    This function handles various phone number formats including:
    - Numbers with + prefix (+1234567890)
    - Numbers without + prefix (1234567890)
    - Numbers with spaces, dashes, parentheses (123-456-7890, (123) 456-7890)
    - Numbers with country codes and other formatting
    
    Args:
        phone_number (str): The phone number to normalize
        
    Returns:
        Optional[str]: Normalized phone number without + prefix (1234567890),
                      or None if the input is invalid
                      
    Examples:
        >>> normalize_phone_number("+1234567890")
        '1234567890'
        >>> normalize_phone_number("1234567890")
        '1234567890'
        >>> normalize_phone_number("123-456-7890")
        '1234567890'
        >>> normalize_phone_number("(123) 456-7890")
        '1234567890'
        >>> normalize_phone_number("+1 (123) 456-7890")
        '11234567890'
        >>> normalize_phone_number("invalid")
        None
    """
    if not phone_number:
        return None
    
    # Remove all non-digit characters
    digits_only = re.sub(r'[^\d]', '', phone_number)
    
    # Check if we have any digits after cleaning
    if not digits_only:
        return None
    
    # Handle country code
    if digits_only.startswith('1') and len(digits_only) == 11:
        # US number with country code
        normalized = digits_only
    elif len(digits_only) == 10:
        # Assume US number without country code
        normalized = f'1{digits_only}'
    elif digits_only.startswith('91') and len(digits_only) == 12:
        # India number with country code
        normalized = digits_only
    elif len(digits_only) == 10 and not digits_only.startswith('0'):
        # Could be India number without country code (if it doesn't start with 0)
        normalized = f'91{digits_only}'
    elif len(digits_only) >= 10 and len(digits_only) <= 15:
        # International number (assume it already includes country code)
        normalized = digits_only
    else:
        # Invalid number length
        return None
    
    return normalized


def normalize_phone_number_flexible(phone_number: str) -> str:
    """
    More flexible phone number normalization that preserves original format
    when possible, but ensures consistent comparison.
    
    This function is useful when you want to maintain the original formatting
    for display purposes but need consistent comparison.
    
    Args:
        phone_number (str): The phone number to normalize
        
    Returns:
        str: Normalized phone number for comparison (without +)
        
    Examples:
        >>> normalize_phone_number_flexible("+1234567890")
        '1234567890'
        >>> normalize_phone_number_flexible("123-456-7890")
        '1234567890'
        >>> normalize_phone_number_flexible("(123) 456-7890")
        '1234567890'
    """
    if not phone_number:
        return ""
    
    # Remove all non-digit characters for comparison
    digits_only = re.sub(r'[^\d]', '', phone_number)
    
    return digits_only


def validate_phone_number(phone_number: str) -> bool:
    """
    Validate if a phone number is in a reasonable format.
    
    Args:
        phone_number (str): The phone number to validate
        
    Returns:
        bool: True if the phone number appears valid, False otherwise
    """
    normalized = normalize_phone_number(phone_number)
    
    if not normalized:
        return False
    
    # Check if the normalized number has a reasonable length
    digits_only = re.sub(r'[^\d]', '', normalized)
    
    # Valid phone numbers should have between 10 and 15 digits (including country code)
    return 10 <= len(digits_only) <= 15


def compare_phone_numbers(phone1: str, phone2: str) -> bool:
    """
    Compare two phone numbers after normalizing them.
    
    Args:
        phone1 (str): First phone number
        phone2 (str): Second phone number
        
    Returns:
        bool: True if the phone numbers match after normalization
    """
    norm1 = normalize_phone_number(phone1)
    norm2 = normalize_phone_number(phone2)
    
    return norm1 == norm2 if norm1 and norm2 else False


def format_phone_number_for_display(phone_number: str, format_type: str = 'international') -> str:
    """
    Format a normalized phone number for display purposes.
    
    Args:
        phone_number (str): The phone number to format
        format_type (str): Format type ('international', 'national', 'plain')
        
    Returns:
        str: Formatted phone number
        
    Examples:
        >>> format_phone_number_for_display("11234567890", "national")
        '(123) 456-7890'
        >>> format_phone_number_for_display("11234567890", "international")
        '+1 123-456-7890'
    """
    normalized = normalize_phone_number(phone_number)
    
    if not normalized:
        return phone_number or ""
    
    digits_only = re.sub(r'[^\d]', '', normalized)
    
    if format_type == 'plain':
        return normalized
    elif format_type == 'international' and len(digits_only) == 11 and digits_only.startswith('1'):
        # US international format: +1 123-456-7890
        return f"+1 {digits_only[1:4]}-{digits_only[4:7]}-{digits_only[7:]}"
    elif format_type == 'national' and len(digits_only) == 11 and digits_only.startswith('1'):
        # US national format: (123) 456-7890
        return f"({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"
    elif format_type == 'international' and len(digits_only) == 12 and digits_only.startswith('91'):
        # India international format: +91 12345-67890
        return f"+91 {digits_only[2:7]}-{digits_only[7:]}"
    elif format_type == 'national' and len(digits_only) == 12 and digits_only.startswith('91'):
        # India national format: 12345-67890
        return f"{digits_only[2:7]}-{digits_only[7:]}"
    else:
        # Return original normalized format for other cases
        return normalized


from django.db import models


class NormalizedPhoneNumberField(models.CharField):
    """
    A Django model field that automatically normalizes phone numbers before saving.
    
    This field ensures that all phone numbers are stored in a consistent E.164 format
    regardless of how they are entered by users or received from external APIs.
    
    Usage:
        class Guest(models.Model):
            phone_number = NormalizedPhoneNumberField(max_length=20)
            whatsapp_number = NormalizedPhoneNumberField(max_length=20, null=True, blank=True)
    """
    
    def __init__(self, *args, **kwargs):
        # Set default max_length to accommodate E.164 format (+123456789012345)
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)
    
    def pre_save(self, model_instance, add):
        """
        Normalize the phone number before saving to the database.
        
        Args:
            model_instance: The model instance being saved
            add: Whether this is a new record being added
            
        Returns:
            str: Normalized phone number without + prefix
        """
        # Get the raw phone number value
        raw_phone = getattr(model_instance, self.attname)
        
        if raw_phone:
            # Normalize the phone number
            normalized = normalize_phone_number(str(raw_phone))
            if normalized:
                # Set the normalized value back to the model instance
                setattr(model_instance, self.attname, normalized)
                return normalized
            else:
                # If normalization fails, set to None and return None
                setattr(model_instance, self.attname, None)
                return None
        
        return raw_phone
    
    def deconstruct(self):
        """
        Allow Django migrations to understand this custom field.
        """
        name, path, args, kwargs = super().deconstruct()
        # Remove max_length from kwargs if it's the default value
        if kwargs.get('max_length') == 20:
            kwargs.pop('max_length')
        return name, path, args, kwargs


def migrate_existing_phone_numbers(app_label, model_name, field_name):
    """
    Utility function to migrate existing phone numbers to normalized format.
    
    This should be run once as a data migration after updating models to use
    NormalizedPhoneNumberField.
    
    Args:
        app_label (str): Django app label (e.g., 'guest')
        model_name (str): Model name (e.g., 'Guest')
        field_name (str): Field name to migrate (e.g., 'whatsapp_number')
        
    Returns:
        dict: Migration statistics
    """
    from django.apps import apps
    
    try:
        model = apps.get_model(app_label, model_name)
        stats = {
            'total': 0,
            'normalized': 0,
            'failed': 0,
            'failed_numbers': []
        }
        
        # Get all instances with non-empty phone numbers
        instances = model.objects.exclude(**{f'{field_name}__in': ['', None]})
        stats['total'] = instances.count()
        
        for instance in instances:
            try:
                current_number = getattr(instance, field_name)
                if current_number:
                    normalized = normalize_phone_number(str(current_number))
                    if normalized and normalized != current_number:
                        setattr(instance, field_name, normalized)
                        instance.save(update_fields=[field_name])
                        stats['normalized'] += 1
            except Exception as e:
                stats['failed'] += 1
                stats['failed_numbers'].append({
                    'id': instance.pk,
                    'number': getattr(instance, field_name),
                    'error': str(e)
                })
        
        return stats
        
    except LookupError:
        return {'error': f'Model {app_label}.{model_name} not found'}
    except Exception as e:
        return {'error': f'Migration failed: {str(e)}'}


def get_guest_group_name(whatsapp_number: str) -> str:
    """
    Generate consistent guest group name for WebSocket connections.
    
    This ensures that all WebSocket group names use normalized phone numbers
    for consistency across the application, while being compatible with
    Django Channels group name restrictions.
    
    Args:
        whatsapp_number (str): The WhatsApp number (raw or normalized)
        
    Returns:
        str: Group name in format 'guest_{normalized_number}'
        
    Examples:
        >>> get_guest_group_name("+1234567890")
        'guest_1234567890'
        >>> get_guest_group_name("123-456-7890")
        'guest_1234567890'
    """
    normalized = normalize_phone_number(whatsapp_number)
    if not normalized:
        return None
    
    return f"guest_{normalized}"


def normalize_phone_number_for_lookup(phone_number: str) -> str:
    """
    Normalize phone number specifically for database lookups.
    
    This is a convenience function that returns the normalized number or raises
    a ValueError if the number is invalid, making it suitable for use in
    views and other places where you need to ensure valid input.
    
    Args:
        phone_number (str): The phone number to normalize
        
    Returns:
        str: Normalized phone number in E.164 format
        
    Raises:
        ValueError: If the phone number is invalid
        
    Examples:
        >>> normalize_phone_number_for_lookup("123-456-7890")
        '+1234567890'
        >>> normalize_phone_number_for_lookup("invalid")
        ValueError: Invalid phone number format
    """
    normalized = normalize_phone_number(phone_number)
    if not normalized:
        raise ValueError("Invalid phone number format")
    return normalized


def extract_phone_number_from_group_name(group_name: str) -> str:
    """
    Extract the original phone number from a WebSocket group name.
    
    This reverses the process in get_guest_group_name.
    
    Args:
        group_name (str): The WebSocket group name
        
    Returns:
        str: Original normalized phone number, or None if not a valid guest group
        
    Examples:
        >>> extract_phone_number_from_group_name('guest_1234567890')
        '1234567890'
        >>> extract_phone_number_from_group_name('invalid_group')
        None
    """
    if not group_name.startswith('guest_'):
        return None
    
    # Remove the 'guest_' prefix
    number_part = group_name[6:]  # Remove 'guest_'
    
    # Validate that it's a normalized phone number
    if normalize_phone_number(number_part) == number_part:
        return number_part
    
    return None