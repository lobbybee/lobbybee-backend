from django.http import Http404
from rest_framework import viewsets, permissions, status, generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import Hotel, HotelDocument
from .serializers import (
    HotelSerializer,
    UserHotelSerializer,
    HotelDocumentSerializer,
)
from .permissions import IsHotelAdmin


class IsVerifiedUser(permissions.BasePermission):
    """
    Allows access only to verified users.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_verified


class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.all()
    permission_classes = [IsVerifiedUser]

    def get_serializer_class(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return HotelSerializer
        return UserHotelSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Hotel.objects.all()
        if hasattr(user, "hotel") and user.hotel:
            return Hotel.objects.filter(pk=user.hotel.pk)
        return Hotel.objects.none()

    def perform_create(self, serializer):
        # Only staff/superusers can create hotels through this viewset
        if not self.request.user.is_staff and not self.request.user.is_superuser:
            raise PermissionDenied("You do not have permission to create a hotel.")
        serializer.save()


class UpdateProfileView(generics.UpdateAPIView):
    """
    Update hotel profile.
    Only hotel admins can access this view.
    """

    serializer_class = HotelSerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin]

    def get_object(self):
        # Hotel admins can only update their own hotel
        hotel = getattr(self.request.user, "hotel", None)
        if hotel is None:
            raise Http404("No hotel associated with this user.")
        return hotel


class HotelDocumentUploadView(generics.CreateAPIView):
    """
    Upload verification documents for a hotel.
    """

    serializer_class = HotelDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin]

    def perform_create(self, serializer):
        # Associate the document with the user's hotel
        hotel = getattr(self.request.user, "hotel", None)
        if hotel is None:
            raise ValidationError("User has no hotel associated.")
        serializer.save(hotel=hotel)