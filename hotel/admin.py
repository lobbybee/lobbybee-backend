from django.contrib import admin
from .models import Hotel, Room, RoomCategory, Department

admin.site.register(Hotel)
admin.site.register(Room)
admin.site.register(RoomCategory)
admin.site.register(Department)