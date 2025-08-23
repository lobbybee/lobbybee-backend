from ..models import HotelFlowConfiguration, Placeholder
from guest.models import Guest, Stay

def validate_input(context, user_input):
    """Validates user input against the current step's requirements."""
    step_template = context.current_step.template
    # Get customized options if they exist
    config = HotelFlowConfiguration.objects.filter(hotel=context.hotel, flow_template=step_template.flow_template).first()
    options = step_template.options
    if config and config.customization_data:
        step_customs = config.customization_data.get('step_customizations', {})
        # IMPORTANT: Assumes customization is keyed by step_name
        custom_options = step_customs.get(str(step_template.id), {}).get('options')
        if custom_options:
            options = custom_options

    if step_template.allowed_flow_categories and user_input in step_template.allowed_flow_categories:
        return True, ""

    if options:
        if user_input in options:
            return True, ""
        else:
            # options_list = ", ".join([f"'{k}'" for k in options.keys()])
            # return False, f"Invalid option. Please select from: {options_list}"
            return False, "Invalid option."

    return True, "" # No options to validate against

def generate_response(context):
    """Generates a response message for the current flow step with placeholders."""
    step_template = context.current_step.template
    config = HotelFlowConfiguration.objects.filter(hotel=context.hotel, flow_template=step_template.flow_template).first()

    message_template = step_template.message_template
    options = step_template.options

    # Apply hotel-specific customizations
    if config and config.customization_data:
        step_customs = config.customization_data.get('step_customizations', {})
        # Use the step template's ID for robust matching
        customizations = step_customs.get(str(step_template.id), {})
        message_template = customizations.get('message_template', message_template)
        options = customizations.get('options', options)

    # Replace placeholders and add options
    response_message = replace_placeholders(message_template, context)
    # if options:
    #     options_text = "\n".join([f"{key}. {value}" for key, value in options.items()])
    #     response_message += f"\n{options_text}"

    return response_message

import re

def replace_placeholders(template, context):
    """Replaces placeholders like {guest_name} with actual data.
    Handles cases where Guest or Hotel object might not exist yet (e.g., during check-in collection or platform-level interactions).
    """
    guest_id = context.context_data.get('guest_id')
    guest = Guest.objects.get(id=guest_id) if guest_id else None
    # Handle case where context.hotel is None (platform level)
    hotel = context.hotel
    # Only try to find an active stay if there's a specific hotel context
    stay = None
    if guest and hotel:
        stay = Stay.objects.filter(guest=guest, hotel=hotel, status='active').first()

    # If guest object doesn't exist, try to get data from collected_checkin_data
    if not guest:
        collected_data = context.context_data.get('collected_checkin_data', {})
        # Create a temporary object for placeholder replacement
        if collected_data:
             # Use a simple object or dict to hold collected data for replacement
            guest = type('TempGuest', (), collected_data)() # Or just use collected_data dict directly

    # Build a dictionary of all possible replacement values
    # Handle hotel being None gracefully
    replacement_data = {
        'guest': guest,
        'hotel': hotel, # This will be None for platform contexts
        'stay': stay,
        **context.context_data.get('accumulated_data', {})
    }

    # Find all unique placeholders in the template
    placeholders_in_template = set(re.findall(r'\{([^}]+)\}', template))

    # Fetch only the required placeholders from the DB
    db_placeholders = Placeholder.objects.filter(name__in=placeholders_in_template)

    replacements = {}
    for p in db_placeholders:
        try:
            parts = p.resolving_logic.split('.')
            obj_name = parts[0]
            attr_name = parts[1] if len(parts) > 1 else None

            if obj_name in replacement_data:
                obj = replacement_data[obj_name]
                if obj and attr_name:
                    # Handle potential temporary guest object attributes
                    # Also handle hotel being None (e.g., obj is None)
                    value = getattr(obj, attr_name, '') # Default to empty string if attribute missing or obj is None
                    if hasattr(value, 'strftime'):
                        value = value.strftime('%d-%m-%Y %H:%M')
                    replacements[p.name] = str(value)
                elif obj:
                    replacements[p.name] = str(obj)
                # Handle case where obj is None (e.g., hotel is None)
                # The placeholder will resolve to an empty string
                else:
                    replacements[p.name] = ''
        except (AttributeError, IndexError):
            replacements[p.name] = ''

    # Add accumulated data that might not be in placeholders table
    for key, value in replacement_data.items():
        if key not in replacements:
            replacements[key] = str(value)

    # Replace all placeholders in one go
    def get_replacement(match):
        placeholder_name = match.group(1)
        return replacements.get(placeholder_name, match.group(0))

    return re.sub(r'\{([^}]+)\}', get_replacement, template)

def update_accumulated_data(context, user_input):
    """
    Updates the context's accumulated_data based on the current step.
    This logic can be expanded with more sophisticated rules.
    For check-in flows, data is also stored in 'collected_checkin_data'.
    """
    step_name = context.current_step.template.step_name
    flow_category = context.current_step.template.flow_template.category

    # A simple convention: if a step name contains "Collect", store the input
    # using a key derived from the step name.
    if 'collect' in step_name.lower():
        data_key = step_name.lower().replace('collect', '').strip().replace(' ', '_')
        if data_key:
            # Ensure accumulated_data exists
            if 'accumulated_data' not in context.context_data:
                context.context_data['accumulated_data'] = {}
            context.context_data['accumulated_data'][data_key] = user_input

            # If this is part of the check-in flow, also store in collected_checkin_data
            if flow_category == 'hotel_checkin':
                 checkin_data = context.context_data.setdefault('collected_checkin_data', {})
                 checkin_data[data_key] = user_input

            context.save()
