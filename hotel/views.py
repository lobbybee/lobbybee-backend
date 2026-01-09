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
from guest.models import Guest
from chat.utils.whatsapp_utils import send_whatsapp_image_with_link
from django.db.models import ObjectDoesNotExist
import threading
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

# Set up logger
logger = logging.getLogger(__name__)
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

class AdminHotelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Platform Admins to manage hotels.
    """
    queryset = Hotel.objects.filter(is_demo=False).prefetch_related('documents').order_by('-registration_date')
    permission_classes = [permissions.IsAuthenticated, CanManagePlatform]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['status', 'city', 'country', 'is_verified', 'is_active']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action in ['partial_update', 'update']:
            from .serializers import AdminHotelUpdateSerializer
            return AdminHotelUpdateSerializer
        return HotelSerializer

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


class AdminHotelDocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Platform Admins to manage hotel documents.
    Handles both create and update operations based on document type.
    """
    permission_classes = [permissions.IsAuthenticated, CanManagePlatform]
    
    def get_queryset(self):
        hotel_id = self.kwargs.get('hotel_pk')
        return HotelDocument.objects.filter(hotel_id=hotel_id)
    
    def get_serializer_class(self):
        if self.action in ['partial_update', 'update']:
            from .serializers import AdminHotelDocumentUpdateSerializer
            return AdminHotelDocumentUpdateSerializer
        return HotelDocumentSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['hotel_pk'] = self.kwargs.get('hotel_pk')
        return context
    
    def get_object(self):
        """
        Override to find document by type if no specific ID provided,
        or use the standard lookup by ID.
        """
        hotel_id = self.kwargs.get('hotel_pk')
        document_id = self.kwargs.get('pk')
        
        if document_id == 'type':
            # This is a special case for finding document by type
            document_type = self.request.data.get('document_type')
            if document_type:
                try:
                    return HotelDocument.objects.get(
                        hotel_id=hotel_id, 
                        document_type=document_type
                    )
                except HotelDocument.DoesNotExist:
                    # Will be handled in update method to create new document
                    return None
        
        # Standard lookup by document ID
        return super().get_object()
    
    def partial_update(self, request, *args, **kwargs):
        """
        Handle partial update with create logic:
        - If document with type exists → Update it
        - If document doesn't exist AND file provided → Create new
        """
        hotel_id = self.kwargs.get('hotel_pk')
        document_type = request.data.get('document_type')
        
        # Validate hotel exists
        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            return Response(
                {'error': 'Hotel not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Try to find existing document by type
        existing_document = None
        if document_type:
            try:
                existing_document = HotelDocument.objects.get(
                    hotel_id=hotel_id, 
                    document_type=document_type
                )
            except HotelDocument.DoesNotExist:
                existing_document = None
        
        # If no existing document and no file provided, return error
        if not existing_document and not request.FILES.get('document_file'):
            return Response(
                {'error': 'Document file is required to create a new document'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new document if it doesn't exist
        if not existing_document:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            document = serializer.save(hotel=hotel)
            return Response(
                HotelDocumentSerializer(document).data, 
                status=status.HTTP_201_CREATED
            )
        
        # Update existing document
        # Set the document ID for standard update flow
        self.kwargs['pk'] = existing_document.id
        return super().partial_update(request, *args, **kwargs)
    
    def update_by_type(self, request, hotel_pk=None):
        """
        Update or create document by type.
        This is the main endpoint for type-based document operations.
        """
        return self.partial_update(request, hotel_pk=hotel_pk, pk='type')


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

    def create(self, request, *args, **kwargs):
        data = request.data
        
        # Check if incoming data is a list for bulk creation
        if isinstance(data, list):
            serializer = self.get_serializer(data=data, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_bulk_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        
        # Default behavior for single category creation
        return super().create(request, *args, **kwargs)

    def perform_bulk_create(self, serializer):
        # Save multiple categories, assigning the hotel to each
        for item in serializer.validated_data:
            item['hotel'] = self.request.user.hotel
        serializer.save()


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

    def create(self, request, *args, **kwargs):
        data = request.data
        
        # Check if incoming data is a list for bulk creation
        if isinstance(data, list):
            serializer = self.get_serializer(data=data, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_bulk_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        
        # Default behavior for single room creation
        return super().create(request, *args, **kwargs)

    def perform_bulk_create(self, serializer):
        # Save multiple rooms, assigning the hotel to each
        for item in serializer.validated_data:
            item['hotel'] = self.request.user.hotel
        serializer.save()

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Bulk create rooms for a hotel.
        Supports both single range and multiple ranges (as array).
        """
        try:
            data = request.data
            all_created_rooms = []
            
            # Check if incoming data is a list for multiple ranges
            if isinstance(data, list):
                # Process each range
                for range_data in data:
                    serializer = BulkCreateRoomSerializer(
                        data=range_data,
                        context={'request': request}
                    )
                    serializer.is_valid(raise_exception=True)
                    validated_data = serializer.validated_data
                    
                    created_rooms = Room.objects.bulk_create_rooms(
                        hotel=request.user.hotel,
                        category=validated_data['category'],
                        floor=validated_data['floor'],
                        start_number_str=validated_data['start_number'],
                        end_number_str=validated_data['end_number']
                    )
                    all_created_rooms.extend(created_rooms)
            else:
                # Single range (old format)
                serializer = BulkCreateRoomSerializer(
                    data=data,
                    context={'request': request}
                )
                serializer.is_valid(raise_exception=True)
                validated_data = serializer.validated_data
                
                created_rooms = Room.objects.bulk_create_rooms(
                    hotel=request.user.hotel,
                    category=validated_data['category'],
                    floor=validated_data['floor'],
                    start_number_str=validated_data['start_number'],
                    end_number_str=validated_data['end_number']
                )
                all_created_rooms.extend(created_rooms)
            
            return Response(
                {"detail": f"{len(all_created_rooms)} rooms created successfully."},
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

    @action(detail=False, methods=['post'], url_path='send-to-whatsapp')
    def send_to_whatsapp(self, request):
        """
        Send QR code to guest's WhatsApp number.
        Takes qr_code_id and guest_id as parameters and sends the QR code image asynchronously.
        """
        qr_code_id = request.data.get('qr_code_id')
        guest_id = request.data.get('guest_id')
        
        if not qr_code_id or not guest_id:
            return Response(
                {"detail": "Both qr_code_id and guest_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get QR code
            qr_code = PaymentQRCode.objects.get(id=qr_code_id, hotel=request.user.hotel)
            
            # Get guest
            guest = Guest.objects.get(id=guest_id)
            
            # Validate QR code has image
            if not qr_code.image:
                return Response(
                    {"detail": "QR code does not have an image."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            def send_whatsapp_async():
                try:
                    # Send QR code image to WhatsApp with UPI ID as caption
                    send_whatsapp_image_with_link(
                        recipient_number=guest.whatsapp_number,
                        image_url=qr_code.image.url,
                        caption=f"UPI ID: {qr_code.upi_id}"
                    )
                    logger.info(f"QR code {qr_code_id} sent to guest {guest.full_name} ({guest.whatsapp_number})")
                except Exception as e:
                    logger.error(f"Failed to send QR code {qr_code_id} to guest {guest.whatsapp_number}: {str(e)}")
            
            # Send asynchronously without waiting for the request
            thread = threading.Thread(target=send_whatsapp_async)
            thread.daemon = True
            thread.start()
            
            return Response(
                {"detail": f"QR code is being sent to {guest.full_name} at {guest.whatsapp_number}"},
                status=status.HTTP_200_OK
            )
            
        except PaymentQRCode.DoesNotExist:
            return Response(
                {"detail": "QR code not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Guest.DoesNotExist:
            return Response(
                {"detail": "Guest not found."},
                status=status.HTTP_404_NOT_FOUND
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


