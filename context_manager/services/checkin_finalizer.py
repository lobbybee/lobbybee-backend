from guest.models import Guest
from django.db import transaction

@transaction.atomic
def finalize_checkin(context):
    """
    Creates or updates a Guest object at the end of a successful check-in process.
    This function should be called when the check-in flow is completed.
    It uses data collected in context.context_data['collected_checkin_data'].
    """
    is_temp = context.context_data.get('is_temp_guest', True) 
    collected_data = context.context_data.get('collected_checkin_data', {})
    whatsapp_number = context.context_data.get('temp_whatsapp_number', context.user_id) # Fallback to user_id

    guest = None
    if is_temp:
        # Create new Guest
        # Use defaults for fields not collected, or require them in the flow
        guest = Guest.objects.create(
            whatsapp_number=whatsapp_number,
            full_name=collected_data.get('full_name', 'Guest'),
            # Add other fields from collected_data as needed (email, etc.)
            # ID type/document would likely need separate handling
        )
        print(f"Created new guest: {guest}")
    else:
        # Update existing Guest
        # The guest object might have been retrieved in handle_initial_message
        # or we can get it again. Let's get it to be safe.
        try:
            guest = Guest.objects.get(whatsapp_number=whatsapp_number)
            # Update fields if new data was collected
            # (e.g., if guest updated their name during this checkin)
            # Be cautious about overwriting existing data
            if 'full_name' in collected_data and collected_data['full_name'] != 'Guest':
                 guest.full_name = collected_data['full_name']
            # ... update other fields if necessary
            guest.save()
            print(f"Updated existing guest: {guest}")
        except Guest.DoesNotExist:
            # This shouldn't happen if is_temp_guest flag is correct, but handle gracefully
            logger.warning(f"Expected existing guest for {whatsapp_number} during checkin finalization, but not found. Creating new.")
            guest = Guest.objects.create(
                whatsapp_number=whatsapp_number,
                full_name=collected_data.get('full_name', 'Guest'),
                # ... other fields
            )

    if guest:
        # Link the actual Guest object to the context's context_data
        # Note: ConversationContext doesn't have a direct guest FK, it's managed via context_data
        context.context_data['guest_id'] = guest.id
        # Clear temporary data
        context.context_data.pop('is_temp_guest', None)
        context.context_data.pop('temp_whatsapp_number', None)
        context.context_data.pop('collected_checkin_data', None)
        context.save(update_fields=['context_data']) # Save only context_data
        
    return guest