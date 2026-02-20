from django.contrib import admin
from .models import Guest, GuestIdentityDocument, Stay,Booking,Feedback

admin.site.register(Guest)
admin.site.register(GuestIdentityDocument)
admin.site.register(Stay)
admin.site.register(Booking)
admin.site.register(Feedback)
