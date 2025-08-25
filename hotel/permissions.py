from rest_framework.permissions import BasePermission

class IsHotelAdmin(BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                request.user.user_type == 'hotel_admin')

class IsSameHotelUser(BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                request.user.hotel is not None)
    
    def has_object_permission(self, request, view, obj):
        return obj.hotel == request.user.hotel

class CanManagePlatform(BasePermission):
    """
    Allows access to platform-level management features.
    This includes superusers, platform admins, and platform staff.
    """
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                (request.user.is_superuser or 
                 request.user.user_type in ['platform_admin', 'platform_staff']))

class CanCreateReceptionist(BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            if request.user.is_authenticated and request.data.get('user_type') == 'receptionist':
                return request.user.user_type in ['hotel_admin', 'manager']
        return True # Allow other methods or if not creating a receptionist

class CanCheckInCheckOut(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type in ["hotel_admin", "receptionist"]
        )
