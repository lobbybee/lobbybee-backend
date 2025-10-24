from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.utils import timezone
import datetime

class User(AbstractUser):
    USER_TYPES = [
        ('platform_admin', 'Platform Admin'),
        ('platform_staff', 'Platform Staff'),
        ('hotel_admin', 'Hotel Admin'),
        ('manager', 'Manager'),
        ('receptionist', 'Receptionist'),
        ('department_staff', 'Department Staff'),
        ('other_staff', 'Other Staff'),
    ]

    DEPARTMENT_CHOICES = [
        ('Reception', 'Reception'),
        ('Housekeeping', 'Housekeeping'),
        ('Room Service', 'Room Service'),
        ('Restaurant', 'Restaurant'),
        ('Management', 'Management'),
    ]

    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    is_verified = models.BooleanField(default=False)
    hotel = models.ForeignKey('hotel.Hotel', on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    is_active_hotel_user = models.BooleanField(default=True)  # For hotel-level user management
    created_at = models.DateTimeField(auto_now_add=True)
    department = models.JSONField(null=True, blank=True)

class OTP(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    resend_attempts = models.IntegerField(default=0)

    def is_expired(self):
        expiry_time = self.created_at + datetime.timedelta(minutes=5)
        return timezone.now() > expiry_time
