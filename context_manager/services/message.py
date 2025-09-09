import json
import re
from copy import deepcopy

from guest.models import Guest, Stay
from ..models import Placeholder
from ..utils.whatsapp import upload_whatsapp_media, get_whatsapp_media_info
import logging

logger = logging.getLogger(__name__)


def format_message(message_content):
    """
    Ensures the message is in the correct format for WhatsApp API.
    - If it's already a properly formatted message dictionary (with 'type' for interactive messages or 'text' for text messages), return as-is
    - If it's a simple string, wrap it in the standard WhatsApp text message format {'text': 'message'}
    - If it's any other type of content, convert to string and wrap as text message
    """
    if isinstance(message_content, dict):
        # If it's already a properly formatted message (interactive or text), return as-is
        if 'type' in message_content or 'text' in message_content:
            return message_content
        # For other dictionaries, convert to string and wrap as text message
        return {"text": str(message_content)}
    # For simple string messages, wrap them in the standard WhatsApp text message format
    return {"text": str(message_content)}


def _recursive_replace(item, replacements):
    """
    Recursively traverses a dictionary or list to replace placeholder strings.
    """
    if isinstance(item, dict):
        # For dictionaries, recurse into each value.
        return {key: _recursive_replace(value, replacements) for key, value in item.items()}
    elif isinstance(item, list):
        # For lists, recurse into each element.
        return [_recursive_replace(elem, replacements) for elem in item]
    elif isinstance(item, str):
        # For strings, perform the placeholder substitution.
        # Placeholders are in the format {placeholder_name}.
        def get_replacement(match):
            placeholder_name = match.group(1)
            # Return the replacement if found, otherwise return the original placeholder string.
            return replacements.get(placeholder_name, match.group(0))
        
        return re.sub(r'\{([^}]+)\}', get_replacement, item)
    else:
        # For all other data types, return the item as is.
        return item


def replace_placeholders(template: dict, context) -> dict:
    """
    Replaces all placeholder variables in a message template dictionary with dynamic data.
    
    Args:
        template (dict): The message template, as a Python dictionary.
        context: The conversation context containing guest, hotel, and other data.

    Returns:
        dict: The message template with all placeholders resolved.
    """
    # 1. Gather all possible data sources for placeholders.
    guest_id = context.context_data.get('guest_id')
    guest = Guest.objects.get(id=guest_id) if guest_id else None
    hotel = context.hotel
    stay = None
    if guest and hotel:
        stay = Stay.objects.filter(guest=guest, hotel=hotel, status='active').first()

    # Use a temporary object for guest data if the guest is not yet created (e.g., during check-in).
    if not guest:
        collected_data = context.context_data.get('collected_checkin_data', {})
        if collected_data:
            # Create a simple object that can be accessed with dot notation.
            guest = type('TempGuest', (), collected_data)()

    # Consolidate all data into a single dictionary for easier access.
    replacement_sources = {
        'guest': guest,
        'hotel': hotel,
        'stay': stay,
        **context.context_data.get('accumulated_data', {})
    }

    # 2. Find all unique placeholders in the template to avoid redundant database queries.
    # We serialize the dict to a string to easily find all placeholders.
    template_str = json.dumps(template)
    placeholders_in_template = set(re.findall(r'\{([^}]+)\}', template_str))

    # 3. Query the database for the resolving logic of these placeholders.
    db_placeholders = Placeholder.objects.filter(name__in=placeholders_in_template)

    # 4. Build the final dictionary of placeholder names to their resolved values.
    replacements = {}
    for p in db_placeholders:
        try:
            # The resolving logic is in the format 'source.attribute', e.g., 'guest.full_name'.
            obj_name, attr_name = p.resolving_logic.split('.')
            source_obj = replacement_sources.get(obj_name)
            if source_obj:
                # Retrieve the attribute value from the source object.
                value = getattr(source_obj, attr_name, '')
                # Format datetimes for display.
                if hasattr(value, 'strftime'):
                    value = value.strftime('%d-%m-%Y %H:%M')
                replacements[p.name] = str(value)
            else:
                replacements[p.name] = ''  # Placeholder source not available.
        except (AttributeError, IndexError, ValueError):
            # Handle cases where logic is malformed or attribute doesn't exist.
            replacements[p.name] = ''

    # Add any simple accumulated data directly to replacements if not already there.
    for key, value in replacement_sources.items():
        if isinstance(value, (str, int, float)):
            replacements.setdefault(key, str(value))

    # 5. Perform the replacement on a deep copy of the template to avoid side effects.
    template_copy = deepcopy(template)
    return _recursive_replace(template_copy, replacements)


def generate_response(context) -> dict:
    """
    Generates a response for the current step, handling media (with expiration checks)
    and text/interactive messages. It prioritizes hotel-specific customizations.
    """
    flow_step = context.current_step

    effective_media = flow_step.media or flow_step.template.media
    effective_message_template = flow_step.message_template or flow_step.template.message_template

    # --- Media Message Handling ---
    if effective_media:
        try:
            wa_media_id = effective_media.whatsapp_media_id
            
            # 1. Check if the existing media ID is still valid
            if wa_media_id:
                media_info = get_whatsapp_media_info(wa_media_id)
                if not media_info: # The ID has expired
                    wa_media_id = None # Unset to trigger re-upload

            # 2. If there is no valid ID, upload the file from S3
            if not wa_media_id:
                logger.info(f"No valid WhatsApp Media ID for media {effective_media.id}. Uploading from S3.")
                wa_media_id = upload_whatsapp_media(effective_media.file)
                # Cache the new, valid ID to the database
                effective_media.whatsapp_media_id = wa_media_id
                effective_media.save()

            # 3. Construct the media message payload
            media_type = effective_media.mime_type.split('/')[0]
            if media_type not in ['image', 'video', 'audio', 'document']:
                logger.warning(f"Unsupported media MIME type: {effective_media.mime_type}. Falling back to text.")
                return replace_placeholders(effective_message_template, context)

            message_payload = {
                "type": media_type,
                media_type: {"id": wa_media_id}
            }

            caption = effective_message_template.get('caption')
            if caption:
                message_payload[media_type]['caption'] = caption
            
            return replace_placeholders(message_payload, context)

        except Exception as e:
            logger.error(f"Failed to process media for FlowStep {flow_step.id}: {e}", exc_info=True)
            return replace_placeholders(effective_message_template, context)

    # --- Text/Interactive Message Handling ---
    return replace_placeholders(effective_message_template, context)


def validate_input(context, user_input, message_type='text'):
    """
    Validates user input against the current step's requirements (e.g., button choices).
    It prioritizes the hotel's custom options from the FlowStep, falling back to the template.
    """
    flow_step = context.current_step
    step_template = flow_step.template

    # --- Step-specific validation ---
    # For ID Photo Upload, we only want an image.
    if step_template.step_name == 'ID Photo Upload':
        if message_type == 'image':
            return True, ""
        else:
            return False, "Please upload an image of your ID. Other file types are not accepted."

    # If the step expects generic media and the user sent a supported media type, input is valid.
    # Use the effective message_type (custom or from template)
    effective_message_type = flow_step.message_type or step_template.message_type
    if effective_message_type == 'media' and message_type in ['image', 'voice', 'video', 'document', 'audio']:
        return True, ""
    
    # Use the hotel-specific options if they exist, otherwise use the template's default.
    options = flow_step.options or step_template.options

    # If the input is a valid flow category transition, it's valid.
    if step_template.allowed_flow_categories and user_input in step_template.allowed_flow_categories:
        return True, ""

    # If there are defined options, the input must be one of them.
    if options:
        if user_input in options:
            return True, ""
        else:
            # Provide a helpful error message.
            return False, f"Invalid option. Please choose from the available buttons."

    # If no options are defined, any input is considered valid.
    return True, ""


def update_accumulated_data(context, user_input, message_type='text'):
    """
    Updates the context's `accumulated_data` or `collected_checkin_data` based on the current step.
    This is typically used for steps that collect information from the user.
    """
    step_name = context.current_step.template.step_name
    flow_category = context.current_step.template.flow_template.category

    # Convention: steps named 'Collect ...' or steps expecting media are for data gathering.
    if 'collect' in step_name.lower() or context.current_step.template.message_type == 'media':
        # Derive a key for the data from the step name.
        data_key = step_name.lower().replace('collect', '').strip().replace(' ', '_')
        if context.current_step.template.message_type == 'media':
            data_key = f"{data_key}_media_id"

        if data_key:
            # Ensure the data structures exist in context_data.
            context.context_data.setdefault('accumulated_data', {})
            context.context_data['accumulated_data'][data_key] = user_input

            # If this is part of the check-in flow, also store data specifically for check-in finalization.
            if flow_category == 'hotel_checkin':
                 checkin_data = context.context_data.setdefault('collected_checkin_data', {})
                 checkin_data[data_key] = user_input

            context.save(update_fields=['context_data'])