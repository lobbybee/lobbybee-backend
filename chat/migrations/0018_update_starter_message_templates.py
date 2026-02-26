# Generated manually on 2026-02-26

from django.db import migrations


TEMPLATE_UPDATES = [
    {
        'name': 'lobbybee_hotel_welcome',
        'template_type': 'greeting',
        'variables': [
            'guest_name', 'hotel_name', 'hotel_city', 'room_number',
            'checkin_time', 'check_in_date', 'check_out_date', 'checkout_time',
            'hotel_phone', 'wifi_name', 'wifi_password', 'google_map_link', 'hours_24',
        ],
        'text_content': (
            'Hello {{guest_name}}!\n'
            '\n'
            'Welcome to {{hotel_name}}, {{hotel_city}}\n'
            'Your room {{room_number}} is ready.\n'
            'Check in time is: {{checkin_time}}, {{check_in_date}}\n'
            'Your Planned Check out Date & time is {{check_out_date}} {{checkout_time}} ({{hours_24}})\n'
            '\n'
            'Reception Phone No is: {{hotel_phone}}\n'
            'Google Location: {{google_map_link}}\n'
            '\n'
            'At any time, just reply here to talk to us.\n'
            '\n'
            'We are delighted to have you stay with us.\n'
            'Have a lovely Stay!!\n'
            '\n'
            'You can use hotel wifi using\n'
            '\n'
            'WIFI Name: {{wifi_name}}\n'
            'WIFI Password: {{wifi_password}}\n'
            '\n'
            'Btw, Wifi is a public service so please use caution.'
        ),
    },
    {
        'name': 'lobbybee_breakfast_reminder',
        'template_type': 'service',
        'variables': ['guest_name', 'breakfast_time'],
        'text_content': (
            'Good morning {{guest_name}}!\n'
            '\n'
            'Breakfast is from {{breakfast_time}}.\n'
            'Enjoy your Meal.\n'
            'Have a wonderful day ahead!'
        ),
    },
    {
        'name': 'lobbybee_checkout_reminder',
        'template_type': 'farewell',
        'variables': ['guest_name', 'room_number', 'checkout_time', 'hotel_name'],
        'text_content': (
            'Dear {{guest_name}},\n'
            '\n'
            'Your check-out time for Room No {{room_number}} is today at {{checkout_time}}.\n'
            'Please settle the bills and return your room keys on time to avoid any additional charges.\n'
            '\n'
            'If you like to continue your stay, Please contact Reception immediately to check availability.\n'
            '\n'
            'Have a great day!!'
        ),
    },
    {
        'name': 'lobbybee_checkout_thank_you',
        'template_type': 'farewell',
        'variables': [
            'guest_name', 'hotel_name', 'check_in_date', 'checkin_time',
            'check_out_date', 'checkout_time', 'room_number',
        ],
        'text_content': (
            'Dear {{guest_name}},\n'
            '\n'
            'Thank you for choosing {{hotel_name}} for your stay!\n'
            'Your Stay Details:\n'
            'Check in Day: {{check_in_date}} Time: {{checkin_time}}\n'
            'Check out Day: {{check_out_date}} Time: {{checkout_time}}\n'
            'Room No: {{room_number}}\n'
            '\n'
            'We hope you had a wonderful experience.\n'
            'For Next Visit Booking, Please send a message here for Welcome back gifts.\n'
            'Thank you, Team LobbyBee for {{hotel_name}}'
        ),
    },
    {
        'name': 'lobbybee_dinner_reminder',
        'template_type': 'service',
        'variables': ['guest_name', 'dinner_time'],
        'text_content': (
            'Good evening {{guest_name}}!\n'
            '\n'
            'Dinner is served from {{dinner_time}}.\n'
            'Will you be eating out, or want to serve dinner in-house?\n'
            'Please Contact the Room Service now so we can be prepared with what you love.\n'
            '\n'
            'Thank you'
        ),
    },
    {
        'name': 'lobbybee_lunch_reminder',
        'template_type': 'service',
        'variables': ['guest_name'],
        'text_content': (
            'Good afternoon {{guest_name}}!\n'
            '\n'
            'Will you be eating out, or want to serve Lunch in-house?\n'
            'Please Contact the Room Service now so we can be prepared with what you love.\n'
            '\n'
            'Thank you'
        ),
    },
]


def update_starter_templates(apps, schema_editor):
    MessageTemplate = apps.get_model('chat', 'MessageTemplate')
    for data in TEMPLATE_UPDATES:
        MessageTemplate.objects.filter(name=data['name']).update(
            template_type=data['template_type'],
            variables=data['variables'],
            text_content=data['text_content'],
        )


def revert_starter_templates(apps, schema_editor):
    """
    Reverting to the exact original content from 0015_add_starter_message_templates
    is impractical; this is a no-op reverse migration.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0017_alter_conversation_conversation_type'),
    ]

    operations = [
        migrations.RunPython(update_starter_templates, revert_starter_templates),
    ]
