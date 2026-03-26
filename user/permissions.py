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


class CanManageHotelUsers(BasePermission):
    """
    Allows hotel admins and managers to manage hotel users.
    Managers cannot manage hotel_admin/manager accounts.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ['hotel_admin', 'manager'] and
            request.user.hotel is not None
        )

    def has_object_permission(self, request, view, obj):
        # Restrict to same hotel only
        if getattr(obj, 'hotel', None) != request.user.hotel:
            return False

        # Managers cannot manage manager/admin users
        if request.user.user_type == 'manager' and obj.user_type in ['hotel_admin', 'manager']:
            return False

        return True
