from django.contrib import admin
from .models import Guest, GuestIdentityDocument, Stay, Booking, Feedback, ReminderLog

admin.site.register(Guest)
admin.site.register(GuestIdentityDocument)
admin.site.register(Stay)
admin.site.register(Booking)
admin.site.register(Feedback)


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
