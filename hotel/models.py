from django.db import models
from django.utils import timezone
import uuid

from user.models import User
from lobbybee.utils.file_url import upload_to_hotel_documents

# Hotel Management
class Hotel(models.Model):
    HOTEL_STATUS = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    phone = models.CharField(max_length=15)
    email = models.EmailField()

    # Documents (CDN URLs)
    license_document_url = models.URLField(blank=True)
    registration_document_url = models.URLField(blank=True)
    additional_documents = models.JSONField(default=list)

    # Location & QR
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    qr_code_url = models.URLField(blank=True)
    unique_qr_code = models.CharField(max_length=50, unique=True, blank=True)

    # Settings
    wifi_password = models.CharField(max_length=100, blank=True)
    check_in_time = models.TimeField(default='14:00')
    time_zone = models.CharField(max_length=50, default='UTC')

    status = models.CharField(max_length=20, choices=HOTEL_STATUS, default='pending')
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


    def save(self, *args, **kwargs):
        if not self.unique_qr_code:
            base_code = self.name.lower().replace(' ', '_')
            self.unique_qr_code = f"{base_code}_{uuid.uuid4().hex[:6]}"
        super().save(*args, **kwargs)

    def get_admin(self):
        return self.user_set.filter(user_type='hotel_admin').first()

class HotelDocument(models.Model):
    """
    Stores verification documents for hotels.
    """
    DOCUMENT_TYPE = [
        ('license', 'Business License'),
        ('registration', 'Company Registration'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE)
    document_file = models.FileField(upload_to=upload_to_hotel_documents)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.hotel.name}"