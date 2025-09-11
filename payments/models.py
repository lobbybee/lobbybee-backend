from django.db import models
from django.utils import timezone
import uuid
from decimal import Decimal
from django.conf import settings

from hotel.models import Hotel


class SubscriptionPlan(models.Model):
    PLAN_TYPES = [
        ('trial', 'Trial'),
        ('standard', 'Standard'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, default='standard')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    duration_days = models.IntegerField(help_text="Duration of the plan in days")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"


class Transaction(models.Model):
    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    TRANSACTION_TYPES = [
        ('subscription', 'Subscription'),
        ('manual', 'Manual Adjustment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='transactions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='subscription')
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, help_text="External payment gateway transaction ID")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Transaction {self.transaction_id} for {self.hotel.name}"


class HotelSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.OneToOneField(Hotel, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='hotel_subscriptions')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Subscription for {self.hotel.name} ({self.plan.name})"
    
    def is_expired(self):
        return timezone.now() > self.end_date
    
    def days_until_expiry(self):
        if self.is_expired():
            return 0
        return (self.end_date - timezone.now()).days