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

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                request.user.user_type == 'superadmin')
