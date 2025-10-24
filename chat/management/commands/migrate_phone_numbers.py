from django.core.management.base import BaseCommand
from django.db import transaction
from chat.utils.phone_utils import normalize_phone_number, migrate_existing_phone_numbers


class Command(BaseCommand):
    help = 'Migrate existing phone numbers to normalized format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app-label',
            type=str,
            default='guest',
            help='App label (default: guest)'
        )
        parser.add_argument(
            '--model-name',
            type=str,
            default='Guest',
            help='Model name (default: Guest)'
        )
        parser.add_argument(
            '--field-name',
            type=str,
            default='whatsapp_number',
            help='Field name (default: whatsapp_number)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes'
        )

    def handle(self, *args, **options):
        app_label = options['app_label']
        model_name = options['model_name']
        field_name = options['field_name']
        dry_run = options['dry_run']

        self.stdout.write(
            self.style.SUCCESS(
                f'Migrating phone numbers for {app_label}.{model_name}.{field_name}'
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            # Show what would be normalized without actually changing
            from django.apps import apps
            try:
                model = apps.get_model(app_label, model_name)
                instances = model.objects.exclude(**{f'{field_name}__in': ['', None]})
                
                would_change = 0
                for instance in instances:
                    current_number = getattr(instance, field_name)
                    if current_number:
                        normalized = normalize_phone_number(str(current_number))
                        if normalized and normalized != current_number:
                            would_change += 1
                            self.stdout.write(
                                f'  Would change: {current_number} -> {normalized} (ID: {instance.pk})'
                            )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Would normalize {would_change} phone numbers out of {instances.count()} total'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error in dry run: {str(e)}')
                )
        else:
            # Perform actual migration
            with transaction.atomic():
                stats = migrate_existing_phone_numbers(app_label, model_name, field_name)
                    
                if 'error' in stats:
                    self.stdout.write(
                        self.style.ERROR(f'Migration failed: {stats["error"]}')
                    )
                    return
                    
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Migration completed successfully! (Removed + symbols)'
                    )
                )
                self.stdout.write(f'  Total records: {stats["total"]}')
                self.stdout.write(
                    self.style.SUCCESS(f'  Normalized (no +): {stats["normalized"]}')
                )
                    
                if stats['failed'] > 0:
                    self.stdout.write(
                        self.style.WARNING(f'  Failed: {stats["failed"]}')
                    )
                    for failed in stats['failed_numbers']:
                        self.stdout.write(
                            self.style.ERROR(
                                f'    ID {failed["id"]}: {failed["number"]} - {failed["error"]}'
                            )
                        )