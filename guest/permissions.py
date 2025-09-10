from rest_framework.permissions import BasePermission
from rest_framework import permissions


class CanManageGuests(BasePermission):
    """
    Allows hotel staff to manage guests.
    - All staff can view guests
    - Receptionists and admins can create guests
    - Only admins can perform other write operations
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
        if request.method in permissions.SAFE_METHODS:
            return True

        # Create access for receptionists and admins
        if request.method == 'POST':
            return request.user.user_type in ['hotel_admin', 'receptionist']

        # Other write operations only for admins
        return request.user.user_type == 'hotel_admin'


class CanViewAndManageStays(BasePermission):
    """
    Allows hotel staff to view and manage stays.
    - All staff can view stays
    - Receptionists and admins can perform check-in/check-out operations
    - Only admins can perform other write operations
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
        if request.method in permissions.SAFE_METHODS:
            return True

        # Create/update access for receptionists and admins
        if request.method in ['POST', 'PUT', 'PATCH']:
            return request.user.user_type in ['hotel_admin', 'receptionist']

        # Delete operations only for admins
        return request.user.user_type == 'hotel_admin'