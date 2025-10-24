from django.contrib import admin
from .models import Hotel, Room, RoomCategory, HotelDocument

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'status', 'is_verified', 'registration_date')
    list_filter = ('status', 'is_verified', 'city', 'country')
    search_fields = ('name', 'city', 'pincode')
    readonly_fields = ('registration_date', 'verified_at', 'updated_at', 'unique_qr_code')

@admin.register(HotelDocument)
class HotelDocumentAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'document_type', 'uploaded_at')
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('hotel__name', 'document_type')
    readonly_fields = ('uploaded_at',)

admin.site.register(Room)
admin.site.register(RoomCategory)
