from rest_framework.permissions import BasePermission
from rest_framework import permissions

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

class IsHotelStaffReadOnlyOrAdmin(BasePermission):
    """
    Allows read-only access to hotel staff (manager, receptionist), 
    and full access to hotel admins.
    """
    def has_permission(self, request, view):
        is_hotel_staff = (
            request.user.is_authenticated and
            request.user.user_type in ['hotel_admin', 'manager', 'receptionist'] and
            request.user.hotel is not None
        )
        if not is_hotel_staff:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.user_type == 'hotel_admin'

class RoomPermissions(BasePermission):
    """
    Custom permissions for the Room viewset.
    - All staff can list/retrieve rooms.
    - All staff can partially update (for status changes).
    - Receptionists and managers can update room status.
    - Only admins can create, fully update details, or delete.
    """
    def has_permission(self, request, view):
        is_hotel_staff = (
            request.user.is_authenticated and
            request.user.user_type in ['hotel_admin', 'manager', 'receptionist'] and
            request.user.hotel is not None
        )
        if not is_hotel_staff:
            return False

        # Read access for all hotel staff
        if view.action in ['list', 'retrieve', 'floors']:
            return True
        
        # Allow partial_update and update for status changes by staff
        if view.action in ['partial_update', 'update']:
            return True

        # Only admin can do other actions
        if view.action in ['create', 'destroy', 'bulk_create']:
            return request.user.user_type == 'hotel_admin'
            
        return False

class IsHotelStaff(BasePermission):
    """
    Allows access to users who are staff members of a hotel.
    (hotel_admin, manager, receptionist)
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.user_type in ['hotel_admin', 'manager', 'receptionist'] and
            request.user.hotel is not None
        )

class CanManagePaymentQRCode(BasePermission):
    """
    Allows hotel admin and manager to manage payment QR codes.
    Receptionists can only view active QR codes (list and retrieve).
    """
    def has_permission(self, request, view):
        """
        All hotel staff (admin, manager, receptionist) can access list and retrieve views.
        Only admin and manager can create, update, delete.
        """
        if not (request.user.is_authenticated and request.user.hotel is not None):
            return False
            
        # Allow all hotel staff to view lists and retrieve details
        if request.method in permissions.SAFE_METHODS:
            return request.user.user_type in ['hotel_admin', 'manager', 'receptionist']
        
        # Only admin and manager can modify
        return request.user.user_type in ['hotel_admin', 'manager']
    
    def has_object_permission(self, request, view, obj):
        # Ensure user belongs to the same hotel
        if obj.hotel != request.user.hotel:
            return False
        
        # Receptionists can only view, not modify
        if request.user.user_type == 'receptionist':
            return request.method in permissions.SAFE_METHODS
        
        # Admin and Manager can do everything
        return True
