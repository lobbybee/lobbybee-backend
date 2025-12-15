from django.db import models
from django.db import transaction
from user.models import User
from hotel.models import Hotel, Room
from lobbybee.utils.file_url import upload_to_guest_documents

class Booking(models.Model):
    BOOKING_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='bookings')
    primary_guest = models.ForeignKey('Guest', on_delete=models.CASCADE, related_name='bookings')

    booking_date = models.DateTimeField(auto_now_add=True)
    check_in_date = models.DateTimeField()
    check_out_date = models.DateTimeField()

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='pending')
    is_via_whatsapp = models.BooleanField(default=False)

    # This field will store the list of guests for the entire booking
    guest_names = models.JSONField(default=list)

    def __str__(self):
        return f"Booking for {self.primary_guest.full_name} at {self.hotel.name}"


class Guest(models.Model):
    GUEST_STATUS = [
        ('pending_checkin', 'Pending Check-in'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
    ]

    whatsapp_number = models.CharField(max_length=20, unique=True)
    register_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True)

    # Primary guest details for booking
    is_primary_guest = models.BooleanField(default=True)

    status = models.CharField(max_length=20, choices=GUEST_STATUS, default='pending_checkin')
    first_contact_date = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    # WhatsApp interaction preferences
    preferred_language = models.CharField(max_length=10, default='en')
    is_whatsapp_active = models.BooleanField(default=True)
    loyalty_points = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.whatsapp_number})"

class GuestIdentityDocument(models.Model):
    DOCUMENT_TYPES = [
        ('aadhar_id', 'AADHAR ID'),
        ('driving_license', 'Driving License'),
        ('national_id', 'National ID'),
        ('voter_id', 'Voter ID'),
        ('other', 'Other Government ID'),
    ]
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='identity_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document_number = models.CharField(max_length=50, blank=True)
    document_file = models.FileField(upload_to=upload_to_guest_documents)
    document_file_back = models.FileField(upload_to=upload_to_guest_documents, blank=True, null=True)
    is_primary = models.BooleanField(default=False)  # Primary document for verification
    is_accompanying_guest = models.BooleanField(default=False)  # Document for non-primary guest
    is_verified = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        # Only one primary document per guest, but multiple non-primary documents allowed
        constraints = [
            models.UniqueConstraint(
                fields=['guest'],
                condition=models.Q(is_primary=True),
                name='unique_primary_document_per_guest'
            )
        ]

    def __str__(self):
        guest_type = "accompanying guest" if self.is_accompanying_guest else "primary guest"
        return f"{self.get_document_type_display()} for {self.guest.full_name} ({guest_type})"

class Stay(models.Model):
    STAY_STATUS = [
        ('pending', 'Pending Check-in'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='stays', null=True, blank=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='stays')
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='stays')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='stays', null=True, blank=True)
    register_number = models.CharField(max_length=50, blank=True, null=True)

    check_in_date = models.DateTimeField()
    check_out_date = models.DateTimeField()
    actual_check_in = models.DateTimeField(null=True, blank=True)
    actual_check_out = models.DateTimeField(null=True, blank=True)

    number_of_guests = models.IntegerField(default=1)
    guest_names = models.JSONField(default=list)  # Store accompanying guest names

    status = models.CharField(max_length=20, choices=STAY_STATUS, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Check-in process tracking
    identity_verified = models.BooleanField(default=False)
    documents_uploaded = models.BooleanField(default=False)

    # Internal rating and notes for hotel staff use
    internal_rating = models.IntegerField(null=True, blank=True, help_text="Internal rating from 1 to 5")
    internal_note = models.TextField(blank=True, help_text="Internal notes about the guest stay")
    
    # 24 hours stay indicator
    hours_24 = models.BooleanField(default=False, help_text="Indicates if this is a 24-hour stay")

    # Reminder settings
    breakfast_reminder = models.BooleanField(default=False, help_text="Enable breakfast reminder for this stay")
    dinner_reminder = models.BooleanField(default=False, help_text="Enable dinner reminder for this stay")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Stay for {self.guest.full_name} at {self.hotel.name}"


class Feedback(models.Model):
    stay = models.OneToOneField(Stay, on_delete=models.CASCADE, related_name='feedback')
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='feedback')
    rating = models.IntegerField(help_text="Rating from 1 to 5")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback for {self.guest.full_name} - Rating: {self.rating}"
