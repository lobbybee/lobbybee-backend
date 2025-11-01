from django.http import Http404
from django.utils import timezone
from rest_framework import viewsets, permissions, status, generics, filters
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
import logging
from django.conf import settings

from .models import Hotel, HotelDocument, Room, RoomCategory, PaymentQRCode, WiFiCredential
from .serializers import (
    HotelSerializer,
    UserHotelSerializer,
    HotelDocumentSerializer,
    RoomCategorySerializer,
    RoomSerializer,
    RoomStatusUpdateSerializer,
    BulkCreateRoomSerializer,
    PaymentQRCodeSerializer,
    WiFiCredentialSerializer,
    RoomWiFiCredentialSerializer,
)
from .permissions import IsHotelAdmin, IsSameHotelUser, CanManagePlatform, IsHotelStaffReadOnlyOrAdmin, RoomPermissions, CanManagePaymentQRCode
from django_filters.rest_framework import DjangoFilterBackend
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
        if self.request.user.is_staff or self.request.user.is_superuser or self.request.user.user_type == 'hotel_admin':
            return HotelSerializer
        return UserHotelSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Hotel.objects.all().prefetch_related('documents')
        if hasattr(user, "hotel") and user.hotel:
            return Hotel.objects.filter(pk=user.hotel.pk).prefetch_related('documents')
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
    queryset = Hotel.objects.filter(is_demo=False).prefetch_related('documents').order_by('-registration_date')
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
        logger = logging.getLogger(__name__)
        # Get the default storage backend from STORAGES setting
        storages_config = getattr(settings, 'STORAGES', {})
        default_storage_config = storages_config.get('default', {})
        backend = default_storage_config.get('BACKEND', 'Not configured')
        logger.info(f"DEFAULT_FILE_STORAGE: {backend}")
        logger.info(f"AWS_STORAGE_BUCKET_NAME: {settings.AWS_STORAGE_BUCKET_NAME}")
        logger.info(f"AWS_S3_REGION_NAME: {settings.AWS_S3_REGION_NAME}")
        # Associate the document with the user's hotel
        hotel = getattr(self.request.user, "hotel", None)
        if hotel is None:
            raise ValidationError("User has no hotel associated.")
        serializer.save(hotel=hotel)


class HotelDocumentUpdateView(generics.UpdateAPIView):
    """
    Update verification documents for a hotel.
    """

    serializer_class = HotelDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin]
    
    def get_queryset(self):
        # Only allow users to update documents for their own hotel
        user = self.request.user
        if hasattr(user, "hotel") and user.hotel:
            return HotelDocument.objects.filter(hotel=user.hotel)
        return HotelDocument.objects.none()


class RoomCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = RoomCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin]
    filterset_fields = ['name']
    ordering_fields = ['name', 'base_price']
    search_fields = ['name']

    def get_queryset(self):
        return RoomCategory.objects.filter(hotel=self.request.user.hotel)

    def perform_create(self, serializer):
        serializer.save(hotel=self.request.user.hotel)


class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated, IsSameHotelUser, RoomPermissions]
    pagination_class = StandardResultsSetPagination
    filterset_class = RoomFilter
    ordering_fields = ['room_number', 'floor']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['room_number']

    def get_serializer_class(self):
        if self.action in ['partial_update', 'update'] and self.request.user.user_type in ['receptionist', 'manager']:
            return RoomStatusUpdateSerializer
        return self.serializer_class

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

    @action(detail=False, methods=['get'], url_path='floors')
    def floors(self, request):
        """
        Get all floors for the hotel.
        """
        floors = Room.objects.get_floors_for_hotel(request.user.hotel)
        return Response({"floors": list(floors)}, status=status.HTTP_200_OK)


class PaymentQRCodeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Payment QR Codes.
    
    - Hotel Admin and Manager: Full CRUD access
    - Receptionist: Read-only access (can only view active QR codes)
    """
    serializer_class = PaymentQRCodeSerializer
    permission_classes = [permissions.IsAuthenticated, CanManagePaymentQRCode]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['active']
    ordering_fields = ['name', 'created_at']
    search_fields = ['name', 'upi_id']

    def get_queryset(self):
        """
        Filter QR codes based on user role and hotel.
        Receptionists can only see active QR codes.
        Admins and Managers can see all QR codes (active and inactive).
        """
        queryset = PaymentQRCode.objects.filter(hotel=self.request.user.hotel)
        
        # Receptionists can only see active QR codes
        if self.request.user.user_type == 'receptionist':
            queryset = queryset.filter(active=True)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """
        Automatically assign the hotel from the authenticated user.
        Only accessible by hotel admin and manager.
        """
        serializer.save(hotel=self.request.user.hotel)

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """
        Toggle the active status of a QR code.
        Only accessible by hotel admin and manager.
        """
        # Check if user has permission (admin or manager)
        if request.user.user_type == 'receptionist':
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        qr_code = self.get_object()
        qr_code.active = not qr_code.active
        qr_code.save(update_fields=['active'])
        status_text = 'activated' if qr_code.active else 'deactivated'
        return Response(
            {"status": f"QR code {status_text}"},
            status=status.HTTP_200_OK
        )


class WiFiCredentialViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing WiFi credentials.
    
    - Hotel Admin and Manager: Full CRUD access
    - Receptionist: Read-only access
    """
    serializer_class = WiFiCredentialSerializer
    permission_classes = [permissions.IsAuthenticated, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['floor', 'room_category', 'is_active']
    ordering_fields = ['floor', 'room_category', 'created_at']
    search_fields = ['network_name']

    def get_queryset(self):
        """
        Filter WiFi credentials based on user hotel.
        """
        return WiFiCredential.objects.filter(hotel=self.request.user.hotel).select_related('room_category').order_by('floor', 'room_category__name')

    def perform_create(self, serializer):
        """
        Automatically assign the hotel from the authenticated user.
        """
        serializer.save(hotel=self.request.user.hotel)

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """
        Toggle the active status of WiFi credentials.
        Only accessible by hotel admin and manager.
        """
        # Check if user has permission (admin or manager)
        if request.user.user_type == 'receptionist':
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        wifi_credential = self.get_object()
        wifi_credential.is_active = not wifi_credential.is_active
        wifi_credential.save(update_fields=['is_active'])
        status_text = 'activated' if wifi_credential.is_active else 'deactivated'
        return Response(
            {"status": f"WiFi credentials {status_text}"},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='by-room/(?P<room_id>[^/.]+)')
    def get_by_room(self, request, room_id=None):
        """
        Get WiFi credentials for a specific room.
        Returns the most specific credentials available for the room.
        """
        try:
            room = Room.objects.get(id=room_id, hotel=request.user.hotel)
        except Room.DoesNotExist:
            return Response(
                {"detail": "Room not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RoomWiFiCredentialSerializer(room)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='by-floor/(?P<floor>[^/.]+)')
    def get_by_floor(self, request, floor=None):
        """
        Get all WiFi credentials for a specific floor.
        """
        try:
            floor = int(floor)
        except ValueError:
            return Response(
                {"detail": "Invalid floor number."},
                status=status.HTTP_400_BAD_REQUEST
            )

        credentials = self.get_queryset().filter(floor=floor)
        serializer = self.get_serializer(credentials, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='available-floors')
    def get_available_floors(self, request):
        """
        Get all floors that have WiFi credentials configured.
        """
        floors = self.get_queryset().values_list('floor', flat=True).distinct().order_by('floor')
        return Response({"floors": list(floors)}, status=status.HTTP_200_OK)


