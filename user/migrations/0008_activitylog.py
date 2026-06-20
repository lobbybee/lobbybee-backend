import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotel', '0032_hotel_logo'),
        ('user', '0007_user_department_alter_user_user_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=40)),
                ('message', models.CharField(max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='user.user')),
                ('hotel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_logs', to='hotel.hotel')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['hotel', '-created_at'], name='user_activi_hotel_i_idx')],
            },
        ),
    ]
