from rest_framework import permissions


class CanFlagGuests(permissions.BasePermission):
    """
    Allows hotel staff and platform staff to flag guests.
    - Hotel staff (admin, manager, receptionist) can flag for their hotel
    - Platform staff can add global notes and police flags
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Hotel staff can flag guests
        if request.user.user_type in ['hotel_admin', 'manager', 'receptionist']:
            return request.user.hotel is not None
        
        # Platform staff can flag guests
        return request.user.user_type in ['platform_admin', 'platform_staff']


class CanViewGuestFlags(permissions.BasePermission):
    """
    Allows viewing guest flags.
    - All hotel staff can view flags
    - Platform staff can view all flags
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Hotel staff can view flags
        if request.user.user_type in ['hotel_admin', 'manager', 'receptionist']:
            return request.user.hotel is not None
        
        # Platform staff can view all flags
        return request.user.user_type in ['platform_admin', 'platform_staff']


class CanManageGuestFlags(permissions.BasePermission):
    """
    Allows managing (reset) guest flags.
    - Only platform staff can reset flags
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only platform staff can manage (reset) flags
        return request.user.user_type in ['platform_admin', 'platform_staff']
    
    def has_object_permission(self, request, view, obj):
        # Platform staff can manage all flags
        return request.user.user_type in ['platform_admin', 'platform_staff']


class CanResetGuestFlags(permissions.BasePermission):
    """
    Specifically for reset action - only platform staff
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only platform staff can reset flags
        return request.user.user_type in ['platform_admin', 'platform_staff']