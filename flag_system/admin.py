from django.contrib import admin

from .models import GuestFlag


@admin.register(GuestFlag)
class GuestFlagAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'guest',
        'stay',
        'flagged_by_police',
        'is_active',
        'last_modified_by',
        'created_at',
        'reset_at',
    )
    list_filter = ('is_active', 'flagged_by_police', 'created_at', 'reset_at')
    search_fields = (
        'guest__full_name',
        'guest__whatsapp_number',
        'guest__register_number',
        'stay__register_number',
        'global_note',
        'internal_reason',
        'reset_reason',
    )
    autocomplete_fields = ('guest', 'stay', 'last_modified_by', 'reset_by')
    readonly_fields = ('created_at', 'reset_at')
