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
