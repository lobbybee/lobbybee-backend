from django.db import models
from django.utils import timezone


class GuestFlag(models.Model):
    """
    Stores flags for guests created by hotel staff or platform staff.
    Each flag represents a separate incident and preserves complete history.
    """
    guest = models.ForeignKey('guest.Guest', on_delete=models.CASCADE, related_name='flags')
    stay = models.ForeignKey('guest.Stay', on_delete=models.CASCADE, null=True, blank=True, 
                            help_text="Stay associated with the flag (null for platform flags)")
    last_modified_by = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True)
    
    # Flag details
    internal_reason = models.TextField(help_text="Internal reason for flagging (visible to platform staff only)")
    global_note = models.TextField(blank=True, help_text="Public note visible to all hotels during check-in")
    reset_reason = models.TextField(blank=True, help_text="Reason for resetting the flag")
    flagged_by_police = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    reset_at = models.DateTimeField(null=True, blank=True)
    reset_by = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, 
                                blank=True, related_name='reset_flags')
    
    class Meta:
        indexes = [
            models.Index(fields=['guest', 'is_active']),
            models.Index(fields=['stay']),
            models.Index(fields=['flagged_by_police']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = "Guest Flag"
        verbose_name_plural = "Guest Flags"
        
    def __str__(self):
        flag_type = "Police" if self.flagged_by_police else "Hotel" if self.stay else "Platform"
        status = "Active" if self.is_active else "Reset"
        return f"{flag_type} flag for {self.guest.full_name} ({status})"
    
    def reset(self, reset_reason, reset_by_user):
        """Reset the flag with reason and user who reset it."""
        self.is_active = False
        self.reset_reason = reset_reason
        self.reset_by = reset_by_user
        self.reset_at = timezone.now()
        self.save()