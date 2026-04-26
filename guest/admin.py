from django.contrib import admin
from .models import Guest, GuestIdentityDocument, Stay, Booking, Feedback, ReminderLog


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'full_name',
        'whatsapp_number',
        'register_number',
        'email',
        'status',
    )
    list_filter = ('status',)
    search_fields = (
        'full_name',
        'whatsapp_number',
        'register_number',
        'email',
    )


@admin.register(GuestIdentityDocument)
class GuestIdentityDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest', 'document_type', 'document_number', 'is_verified', 'uploaded_at')
    list_filter = ('document_type', 'is_verified')
    search_fields = ('document_number', 'guest__full_name', 'guest__whatsapp_number')


@admin.register(Stay)
class StayAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'guest',
        'hotel',
        'room',
        'check_in_date',
        'check_out_date',
        'status',
    )
    list_filter = ('status', 'hotel')
    search_fields = (
        'register_number',
        'guest__full_name',
        'guest__whatsapp_number',
        'hotel__name',
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'primary_guest', 'hotel', 'check_in_date', 'check_out_date', 'status', 'booking_date')
    list_filter = ('status', 'hotel')
    search_fields = ('primary_guest__full_name', 'primary_guest__whatsapp_number', 'hotel__name')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest', 'stay', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('guest__full_name', 'guest__whatsapp_number', 'note')


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "stay",
        "reminder_type",
        "reminder_date",
        "scheduled_for",
        "status",
        "is_test",
        "sent_at",
        "created_at",
    )
    list_filter = ("status", "reminder_type", "is_test", "reminder_date", "created_at")
    search_fields = (
        "stay__guest__full_name",
        "stay__guest__whatsapp_number",
        "stay__hotel__name",
        "task_id",
        "reason",
    )
    readonly_fields = ("created_at", "updated_at")