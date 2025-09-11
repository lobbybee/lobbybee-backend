from rest_framework.permissions import BasePermission


class CanManagePayments(BasePermission):
    """
    Allows access to platform-level payment management features.
    This includes superusers, platform admins, and platform staff.
    """
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                (request.user.is_superuser or 
                 request.user.user_type in ['platform_admin', 'platform_staff']))


class IsHotelAdminOrPlatformStaff(BasePermission):
    """
    Allows access to hotel admins for viewing their own payment info,
    and platform staff for managing all payments.
    """
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                (request.user.user_type in ['hotel_admin'] or
                 request.user.user_type in ['platform_admin', 'platform_staff']))