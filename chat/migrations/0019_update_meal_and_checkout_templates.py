# Generated manually on 2026-02-26

from django.db import migrations


TEMPLATE_UPDATES = [
    {
        'name': 'lobbybee_breakfast_reminder',
        'variables': ['guest_name', 'breakfast_time', 'breakfast_end_time'],
        'text_content': (
            'Good morning {{guest_name}}!\n'
            '\n'
            'Breakfast is from {{breakfast_time}} to {{breakfast_end_time}}.\n'
            'Enjoy your Meal.\n'
            'Have a wonderful day ahead!'
        ),
    },
    {
        'name': 'lobbybee_lunch_reminder',
        'variables': ['guest_name', 'lunch_time', 'lunch_end_time'],
        'text_content': (
            'Good afternoon {{guest_name}}!\n'
            '\n'
            'Lunch is served from {{lunch_time}} to {{lunch_end_time}}.\n'
            'Will you be eating out, or want to serve Lunch in-house?\n'
            'Please Contact the Room Service now so we can be prepared with what you love.\n'
            '\n'
            'Thank you'
        ),
    },
    {
        'name': 'lobbybee_dinner_reminder',
        'variables': ['guest_name', 'dinner_time', 'dinner_end_time'],
        'text_content': (
            'Good evening {{guest_name}}!\n'
            '\n'
            'Dinner is served from {{dinner_time}} to {{dinner_end_time}}.\n'
            'Will you be eating out, or want to serve dinner in-house?\n'
            'Please Contact the Room Service now so we can be prepared with what you love.\n'
            '\n'
            'Thank you'
        ),
    },
    {
        'name': 'lobbybee_checkout_thank_you',
        'variables': [
            'guest_name', 'hotel_name', 'check_in_date', 'checkin_time',
            'check_out_date', 'checkout_time', 'room_number', 'no_of_days',
        ],
        'text_content': (
            'Dear {{guest_name}},\n'
            '\n'
            'Thank you for choosing {{hotel_name}} for your stay!\n'
            'Your Stay Details:\n'
            'Check in Day: {{check_in_date}} Time: {{checkin_time}}\n'
            'Check out Day: {{check_out_date}} Time: {{checkout_time}}\n'
            'Room No: {{room_number}}\n'
            'No of Days: {{no_of_days}}\n'
            '\n'
            'We hope you had a wonderful experience.\n'
            'For Next Visit Booking, Please send a message here for Welcome back gifts.\n'
            'Thank you, Team LobbyBee for {{hotel_name}}'
        ),
    },
]


def update_templates(apps, schema_editor):
    MessageTemplate = apps.get_model('chat', 'MessageTemplate')
    for data in TEMPLATE_UPDATES:
        MessageTemplate.objects.filter(name=data['name']).update(
            variables=data['variables'],
            text_content=data['text_content'],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0018_update_starter_message_templates'),
    ]

    operations = [
        migrations.RunPython(update_templates, migrations.RunPython.noop),
    ]
