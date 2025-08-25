from django.http import Http404
from django.utils import timezone
from rest_framework import viewsets, permissions, status, generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from .models import Hotel, HotelDocument, Room, RoomCategory, Department
from .serializers import (
    HotelSerializer,
    UserHotelSerializer,
    HotelDocumentSerializer,
    RoomCategorySerializer,
    RoomSerializer,
    DepartmentSerializer,
    BulkCreateRoomSerializer,
)
from .permissions import IsHotelAdmin, IsSameHotelUser, CanManagePlatform
from .filters import RoomFilter


class IsVerifiedUser(permissions.BasePermission):
    """
    Allows access only to verified users.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_verified


class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.all()
    permission_classes = [IsVerifiedUser]
    filterset_fields = ['status', 'city', 'country']
    ordering_fields = ['name', 'registration_date']

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


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class AdminHotelViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Platform Admins to manage hotels.
    """
    queryset = Hotel.objects.filter(is_demo=False).order_by('-registration_date')
    serializer_class = HotelSerializer
    permission_classes = [permissions.IsAuthenticated, CanManagePlatform]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['status', 'city', 'country', 'is_verified', 'is_active']
    search_fields = ['name']

    @action(detail=True, methods=['post'], url_path='verify')
    def verify(self, request, pk=None):
        hotel = self.get_object()
        notes = request.data.get('notes', '')
        
        hotel.is_verified = True
        hotel.status = 'verified'
        if notes:
            hotel.verification_notes = notes
        hotel.verified_at = timezone.now()
        hotel.save(update_fields=['is_verified', 'status', 'verification_notes', 'verified_at'])
        
        return Response({'status': 'hotel verified'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        hotel = self.get_object()
        hotel.is_active = not hotel.is_active
        hotel.save(update_fields=['is_active'])
        status_text = 'activated' if hotel.is_active else 'deactivated'
        return Response({'status': f'hotel {status_text}'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        hotel = self.get_object()
        notes = request.data.get('notes')
        if not notes:
            raise ValidationError({"notes": "Rejection notes are required."})
        
        hotel.status = 'rejected'
        hotel.is_verified = False
        hotel.verification_notes = notes
        hotel.save(update_fields=['status', 'is_verified', 'verification_notes'])
        
        return Response({'status': 'hotel rejected'}, status=status.HTTP_200_OK)


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


class RoomCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = RoomCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin, IsSameHotelUser]
    filterset_fields = ['name']
    ordering_fields = ['name', 'base_price']
    search_fields = ['name']

    def get_queryset(self):
        return RoomCategory.objects.filter(hotel=self.request.user.hotel)

    def perform_create(self, serializer):
        serializer.save(hotel=self.request.user.hotel)


class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin, IsSameHotelUser]
    filterset_class = RoomFilter
    ordering_fields = ['room_number', 'floor']

    def get_queryset(self):
        return Room.objects.filter(hotel=self.request.user.hotel)

    def perform_create(self, serializer):
        serializer.save(hotel=self.request.user.hotel)

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Bulk create rooms for a hotel.
        """
        serializer = BulkCreateRoomSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            created_rooms = Room.objects.bulk_create_rooms(
                hotel=request.user.hotel,
                category=data['category'],
                floor=data['floor'],
                start_number_str=data['start_number'],
                end_number_str=data['end_number']
            )
            return Response(
                {"detail": f"{len(created_rooms)} rooms created successfully."},
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin, IsSameHotelUser]
    filterset_fields = ['department_type', 'is_active']
    ordering_fields = ['name']

    def get_queryset(self):
        return Department.objects.filter(hotel=self.request.user.hotel)

    def perform_create(self, serializer):
        serializer.save(hotel=self.request.user.hotel)