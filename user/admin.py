from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'hotel', 'is_staff')
    list_filter = UserAdmin.list_filter + ('user_type', 'hotel',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Info', {'fields': ('user_type', 'hotel', 'phone_number', 'is_verified', 'is_active_hotel_user', 'created_by')}),
    )
