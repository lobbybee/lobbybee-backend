from rest_framework.permissions import BasePermission

class IsSuperUser(BasePermission):
    """
    Allows access only to superusers.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser

class IsPlatformAdmin(BasePermission):
    """
    Allows access only to platform admins.
    """
    def has_permission(self, request, view):
        return request.user and request.user.user_type == 'platform_admin'

class IsPlatformStaff(BasePermission):
    """
    Allows access only to platform staff.
    """
    def has_permission(self, request, view):
        return request.user and request.user.user_type == 'platform_staff'

class IsHotelAdmin(BasePermission):
    """
    Allows access only to hotel admins.
    """
    def has_permission(self, request, view):
        return request.user and request.user.user_type == 'hotel_admin'

class IsSuperUserOrPlatformStaff(BasePermission):
    """
    Allows access only to superusers and platform staff.
    """
    def has_permission(self, request, view):
        return (request.user and 
                (request.user.is_superuser or request.user.user_type == 'platform_staff'))

class IsHotelManagerOrAdmin(BasePermission):
    """
    Allows access only to hotel managers and hotel admins.
    """
    def has_permission(self, request, view):
        return (request.user and 
                (request.user.is_superuser or 
                 request.user.user_type in ['hotel_admin', 'manager']))

class IsHotelStaffOrAdmin(BasePermission):
    """
    Allows access only to hotel receptionists, managers, and hotel admins.
    """
    def has_permission(self, request, view):
        return (request.user and 
                (request.user.is_superuser or 
                 request.user.user_type in ['hotel_admin', 'manager', 'receptionist']))