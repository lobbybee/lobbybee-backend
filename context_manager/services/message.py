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

    if options:
        if user_input in options:
            return True, ""
        else:
            options_list = ", ".join([f"'{k}'" for k in options.keys()])
            return False, f"Invalid option. Please select from: {options_list}"
    
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
    if options:
        options_text = "\n".join([f"{key}. {value}" for key, value in options.items()])
        response_message += f"\n{options_text}"
        
    return response_message

def replace_placeholders(template, context):
    """Replaces placeholders like {guest_name} with actual data."""
    guest_id = context.context_data.get('guest_id')
    guest = Guest.objects.get(id=guest_id) if guest_id else None
    hotel = context.hotel
    stay = Stay.objects.filter(guest=guest, hotel=hotel, status='active').first() if guest else None

    # Get all placeholders from the database
    placeholders = Placeholder.objects.all()
    
    replacements = {}
    for p in placeholders:
        # Resolve the placeholder logic
        try:
            # Split the logic into parts (e.g., 'guest.full_name' -> ['guest', 'full_name'])
            parts = p.resolving_logic.split('.')
            # Get the initial object (e.g., guest, hotel, stay)
            obj = locals().get(parts[0])
            if obj:
                # Traverse the attributes to get the final value
                value = obj
                for part in parts[1:]:
                    value = getattr(value, part)
                
                # Format the value if it's a datetime object
                if hasattr(value, 'strftime'):
                    value = value.strftime('%d-%m-%Y %H:%M')

                replacements[f'{{{p.name}}}'] = str(value)
            else:
                replacements[f'{{{p.name}}}'] = ''
        except (AttributeError, IndexError):
            replacements[f'{{{p.name}}}'] = ''

    # Add accumulated data to replacements
    if 'accumulated_data' in context.context_data:
        for key, value in context.context_data['accumulated_data'].items():
            replacements[f'{{{key}}}'] = str(value)

    # Replace all placeholders in the template
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
        
    return template

def update_accumulated_data(context, user_input):
    """
    Updates the context's accumulated_data based on the current step.
    This logic can be expanded with more sophisticated rules.
    """
    step_name = context.current_step.template.step_name
    # A simple convention: if a step name contains "Collect", store the input
    # using a key derived from the step name.
    if 'collect' in step_name.lower():
        data_key = step_name.lower().replace('collect', '').strip().replace(' ', '_')
        if data_key:
            # Ensure accumulated_data exists
            if 'accumulated_data' not in context.context_data:
                context.context_data['accumulated_data'] = {}
            context.context_data['accumulated_data'][data_key] = user_input
            context.save()
