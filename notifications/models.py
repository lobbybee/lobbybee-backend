from django.db import models
from user.models import User


class Notification(models.Model):
    """
    Notification model for sending notifications to users or groups
    """
    # Individual user notification (null if group notification)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    
    # Group notification fields
    GROUP_CHOICES = [
        ('hotel_staff', 'Hotel Staff'),
        ('platform_user', 'Platform User'),
    ]
    group_type = models.CharField(max_length=20, choices=GROUP_CHOICES, null=True, blank=True)
    hotel = models.ForeignKey('hotel.Hotel', on_delete=models.CASCADE, null=True, blank=True, help_text="Required for hotel_staff group notifications")
    
    # Common fields
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.URLField(null=True, blank=True, help_text="URL to navigate to when notification is clicked")
    link_label = models.CharField(max_length=100, null=True, blank=True, help_text="Label text for the link button")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['group_type', 'hotel']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        if self.user:
            return f"{self.user.get_full_name() or self.user.username}: {self.title}"
        elif self.group_type == 'hotel_staff':
            return f"Hotel Staff ({self.hotel}): {self.title}"
        elif self.group_type == 'platform_user':
            return f"Platform Users: {self.title}"
        return f"Notification: {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
    
    def get_target_users(self):
        """Get the list of users this notification targets"""
        if self.user:
            return [self.user]
        elif self.group_type == 'hotel_staff' and self.hotel:
            # Get hotel staff: hotel_admin, manager, receptionist
            return User.objects.filter(
                hotel=self.hotel,
                user_type__in=['hotel_admin', 'manager', 'receptionist'],
                is_active=True
            )
        elif self.group_type == 'platform_user':
            # Get platform users: platform_admin, platform_staff
            return User.objects.filter(
                user_type__in=['platform_admin', 'platform_staff'],
                is_active=True
            )
        return User.objects.none()
