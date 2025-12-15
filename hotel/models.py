from django.db import models, IntegrityError
from django.utils import timezone
import uuid
import re
from django.core.exceptions import ValidationError

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
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    google_review_link = models.URLField(blank=True, help_text="Google Review link for the hotel")

    # Documents (CDN URLs)

    # Location & QR
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    qr_code_url = models.URLField(blank=True)
    unique_qr_code = models.CharField(max_length=50, unique=True, blank=True)

    # Settings
    check_in_time = models.TimeField(default='14:00')
    time_zone = models.CharField(max_length=50, default='UTC')
    breakfast_reminder = models.BooleanField(default=False, help_text="Enable breakfast reminders for guests")
    dinner_reminder = models.BooleanField(default=False, help_text="Enable dinner reminders for guests")

    status = models.CharField(max_length=20, choices=HOTEL_STATUS, default='pending')
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_demo = models.BooleanField(default=False)
    verification_notes = models.TextField(blank=True, help_text="Notes for verification process by platform admin.")
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

    def is_subscribed(self):
        """
        Check if the hotel has an active subscription
        """
        try:
            from payments.utils import is_hotel_subscribed
            return is_hotel_subscribed(self)
        except ImportError:
            # If payments app is not available, return False
            return False

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


# Room Management
class RoomCategory(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='room_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    max_occupancy = models.IntegerField()
    amenities = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.hotel.name})"

    def room_count(self):
        return self.rooms.count()


class RoomManager(models.Manager):
    def bulk_create_rooms(self, hotel, category, floor, start_number_str, end_number_str):
        # Extract prefix and numeric part from start_number
        # This regex supports formats like 'F-100', 'H101', '101', etc.
        match_start = re.match(r'([a-zA-Z]+-?)*(\d+)', start_number_str)
        if not match_start:
            raise ValidationError("Invalid start room number format. Expected format like 'F-100', 'H101' or '101'.")

        prefix = match_start.group(1) or ''
        start_num = int(match_start.group(2))

        # Extract prefix and numeric part from end_number
        match_end = re.match(r'([a-zA-Z]+-?)*(\d+)', end_number_str)
        if not match_end:
            raise ValidationError("Invalid end room number format. Expected format like 'F-110', 'H104' or '104'.")

        end_prefix = match_end.group(1) or ''
        end_num = int(match_end.group(2))

        if prefix != end_prefix:
            raise ValidationError("Start and end room number prefixes do not match.")

        if start_num > end_num:
            raise ValidationError("Start room number cannot be greater than the end room number.")

        rooms_to_create = []
        existing_room_numbers = set(self.filter(hotel=hotel).values_list('room_number', flat=True))

        for i in range(start_num, end_num + 1):
            room_number = f"{prefix}{i}"
            if room_number in existing_room_numbers:
                continue  # Skip if room already exists

            rooms_to_create.append(self.model(
                hotel=hotel,
                room_number=room_number,
                category=category,
                floor=floor,
                status='available'
            ))

        if not rooms_to_create:
            raise ValidationError("No new rooms to create. They may already exist.")

        try:
            return self.bulk_create(rooms_to_create)
        except IntegrityError:
            raise ValidationError("Some rooms already exist in the database. Please check the room numbers.")

    def get_floors_for_hotel(self, hotel):
        return self.filter(hotel=hotel).values_list('floor', flat=True).distinct().order_by('floor')


class Room(models.Model):
    ROOM_STATUS = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('cleaning', 'Under Cleaning'),
        ('maintenance', 'Under Maintenance'),
        ('out_of_order', 'Out of Order'),
    ]

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=10)
    category = models.ForeignKey(RoomCategory, on_delete=models.CASCADE, related_name='rooms')
    floor = models.IntegerField()
    status = models.CharField(max_length=20, choices=ROOM_STATUS, default='available')
    current_guest = models.ForeignKey('guest.Guest', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RoomManager()

    class Meta:
        unique_together = ['hotel', 'room_number']
        indexes = [
            models.Index(fields=['hotel', 'floor']),
            models.Index(fields=['hotel', 'status']),
            models.Index(fields=['hotel', 'category']),
        ]

    def __str__(self):
        return f"Room {self.room_number} ({self.hotel.name})"

    def get_status_display_name(self):
        return dict(self.ROOM_STATUS).get(self.status, self.status)


# Payment QR Code Management
class PaymentQRCode(models.Model):
    """
    Stores payment QR codes for hotels, which can be managed by hotel admin or manager.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='payment_qr_codes')
    name = models.CharField(max_length=100, help_text="Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')")
    image = models.FileField(upload_to=upload_to_hotel_documents, help_text="QR code image file")
    upi_id = models.CharField(max_length=100, help_text="UPI ID associated with this QR code")
    active = models.BooleanField(default=True, help_text="Whether this QR code is currently active for use")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['hotel', 'active']),
        ]

    def __str__(self):
        return f"{self.name} - {self.hotel.name}"

    def get_image_url(self):
        if self.image:
            return self.image.url
        return None


# WiFi Credentials Management
class WiFiCredential(models.Model):
    """
    Stores WiFi credentials for different floors and room categories within a hotel.
    Allows each floor and room category combination to have different WiFi passwords.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='wifi_credentials')
    floor = models.IntegerField(help_text="Floor number for these WiFi credentials")
    room_category = models.ForeignKey(RoomCategory, on_delete=models.CASCADE, related_name='wifi_credentials', 
                                    null=True, blank=True, help_text="Room category for these credentials. If null, applies to all categories on this floor.")
    network_name = models.CharField(max_length=100, help_text="WiFi network name (SSID)")
    password = models.CharField(max_length=100, help_text="WiFi password for this floor/category")
    is_active = models.BooleanField(default=True, help_text="Whether these WiFi credentials are currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['hotel', 'floor', 'room_category']
        indexes = [
            models.Index(fields=['hotel', 'floor']),
            models.Index(fields=['hotel', 'room_category']),
            models.Index(fields=['hotel', 'is_active']),
        ]

    def __str__(self):
        if self.room_category:
            return f"WiFi for {self.hotel.name} - Floor {self.floor} - {self.room_category.name}"
        return f"WiFi for {self.hotel.name} - Floor {self.floor} (All categories)"

    def get_credentials_for_room(self, room):
        """
        Get the most specific WiFi credentials for a given room.
        Prefers room-specific credentials over floor-wide credentials.
        """
        # Try to find credentials for this specific room category and floor
        specific_creds = WiFiCredential.objects.filter(
            hotel=self.hotel,
            floor=room.floor,
            room_category=room.category,
            is_active=True
        ).first()
        
        if specific_creds:
            return specific_creds
        
        # Fall back to floor-wide credentials (room_category is null)
        floor_creds = WiFiCredential.objects.filter(
            hotel=self.hotel,
            floor=room.floor,
            room_category__isnull=True,
            is_active=True
        ).first()
        
        return floor_creds
