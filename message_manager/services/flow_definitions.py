DEMO_FLOW = {
    'start': {
        'message': 'Welcome to our hotel demo! Type "services" to explore.',
        'next_triggers': {'services': 'show_services'},
        'default_next': 'start'
    },
    'show_services': {
        'message': """Available services: 1. Room Service 2. Housekeeping 3. Reception""",
        'next_triggers': {
            '1': 'demo_room_service',
            '2': 'demo_housekeeping',
            '3': 'demo_reception'
        }
    },
    'demo_room_service': {
        'message': 'Room Service: What would you like to order?',
        'action': 'start_relay_to_department'
    },
    'demo_housekeeping': {
        'message': 'Housekeeping: How can we help with your room?',
        'action': 'start_relay_to_department'
    },
    'demo_reception': {
        'message': 'Reception: How can we assist you at the front desk?',
        'action': 'start_relay_to_department'
    }
}

CHECKIN_FLOW = {
    'start': {
        'message': """Welcome to {hotel_name}! I'll help with your check-in. What is your full name?""",
        'next_step': 'collect_name',
        'action': 'validate_guest_name'
    },
    'collect_documents': {
        'message': """Please upload a photo of your ID document.""",
        'next_step': 'finalize_checkin',
        'action': 'save_document'
    }
}

SERVICES_FLOW = {
    'start': {
        'message': """How can we assist you today? 1. Room Service 2. Housekeeping 3. Reception 4. Other""",
        'next_triggers': {
            '1': 'start_relay_room_service',
            '2': 'start_relay_housekeeping',
            '3': 'start_relay_reception',
            '4': 'start_relay_other'
        }
    },
    'start_relay_room_service': {
        'message': 'Connecting you to Room Service...',
        'action': 'start_relay_to_department'
    },
    'start_relay_housekeeping': {
        'message': 'Connecting you to Housekeeping...',
        'action': 'start_relay_to_department'
    },
    'start_relay_reception': {
        'message': 'Connecting you to Reception...',
        'action': 'start_relay_to_department'
    },
    'start_relay_other': {
        'message': 'Connecting you to our team...',
        'action': 'start_relay_to_department'
    }
}