# Generated manually

from django.db import migrations


MEAL_TEMPLATE_UPDATES = [
    {
        'name': 'lobbybee_breakfast_reminder',
        'variables': ['guest_name', 'meal_start', 'meal_end'],
        'text_content': (
            'Good {{day_greeting}} {{guest_name}}!\n'
            '\n'
            'Your requested {{meal_name}} is available from {{meal_start}} to {{meal_end}}.\n'
            'Enjoy your Meal.\n'
            'Have a wonderful day ahead!'
        ),
    },
    {
        'name': 'lobbybee_lunch_reminder',
        'variables': ['guest_name', 'meal_start', 'meal_end'],
        'text_content': (
            'Good {{day_greeting}} {{guest_name}}!\n'
            '\n'
            'Your requested {{meal_name}} is available from {{meal_start}} to {{meal_end}}.\n'
            'Enjoy your Meal.\n'
            'Have a wonderful day ahead!'
        ),
    },
    {
        'name': 'lobbybee_dinner_reminder',
        'variables': ['guest_name', 'meal_start', 'meal_end'],
        'text_content': (
            'Good {{day_greeting}} {{guest_name}}!\n'
            '\n'
            'Your requested {{meal_name}} is available from {{meal_start}} to {{meal_end}}.\n'
            'Enjoy your Meal.\n'
            'Have a wonderful day ahead!'
        ),
    },
]


def update_meal_templates(apps, schema_editor):
    MessageTemplate = apps.get_model('chat', 'MessageTemplate')
    for data in MEAL_TEMPLATE_UPDATES:
        MessageTemplate.objects.filter(name=data['name']).update(
            variables=data['variables'],
            text_content=data['text_content'],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0019_update_meal_and_checkout_templates'),
    ]

    operations = [
        migrations.RunPython(update_meal_templates, migrations.RunPython.noop),
    ]
