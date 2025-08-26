from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from context_manager.models import ConversationContext
from .models import Guest, GuestIdentityDocument, Stay
from .serializers import (
    GuestSerializer,
    GuestIdentityDocumentSerializer,
    StaySerializer,
    CheckInSerializer,
    CheckOutSerializer,
)
from hotel.permissions import IsHotelAdmin, IsSameHotelUser, CanCheckInCheckOut
from django.utils import timezone
import logging
from django.conf import settings
import logging
from django.conf import settings


class GuestViewSet(viewsets.ModelViewSet):
    queryset = Guest.objects.all()
    serializer_class = GuestSerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin]
    filterset_fields = ['status', 'nationality']
    ordering_fields = ['full_name', 'first_contact_date']

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        Search for guests by name, email, or phone number within the user's hotel.
        """
        query = request.query_params.get('q', None)
        if not query:
            return Response(
                {"detail": "Query parameter 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get guests that have a stay record in the current user's hotel
        hotel_guests = Guest.objects.filter(
            stays__hotel=request.user.hotel
        ).distinct()

        # Apply the search query on the filtered guests
        search_results = hotel_guests.filter(
            Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(whatsapp_number__icontains=query)
        )

        serializer = self.get_serializer(search_results, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stays-by-phone')
    def stays_by_phone(self, request):
        """
        Get a guest's stay history by their phone number.
        """
        phone_number = request.query_params.get("phone_number", None)
        if not phone_number:
            return Response(
                {"detail": "Query parameter 'phone_number' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            guest = Guest.objects.get(whatsapp_number=phone_number)
        except Guest.DoesNotExist:
            return Response(
                {"detail": "Guest with this phone number not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Filter stays for the current user's hotel
        stays = Stay.objects.filter(guest=guest, hotel=request.user.hotel).order_by(
            "-check_in_date"
        )
        serializer = StaySerializer(stays, many=True)
        return Response(serializer.data)


class GuestIdentityDocumentViewSet(viewsets.ModelViewSet):
    queryset = GuestIdentityDocument.objects.all()
    serializer_class = GuestIdentityDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin]
    filterset_fields = ['document_type', 'is_verified']
    ordering_fields = ['uploaded_at']

    def get_queryset(self):
        return GuestIdentityDocument.objects.filter(
            guest__stay__hotel=self.request.user.hotel
        )

    def perform_create(self, serializer):
        # Ensure the document is associated with a guest from the same hotel
        guest = serializer.validated_data["guest"]
        if guest.stays.filter(hotel=self.request.user.hotel).exists():
            serializer.save(verified_by=self.request.user)
        else:
            raise permissions.PermissionDenied(
                "You can only add documents for guests in your hotel."
            )


class GuestIdentityDocumentUploadView(generics.CreateAPIView):
    """
    Upload identity documents for a guest.
    """

    serializer_class = GuestIdentityDocumentSerializer
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
        
        # Ensure the document is associated with a guest from the same hotel
        guest = serializer.validated_data["guest"]
        if guest.stays.filter(hotel=self.request.user.hotel).exists():
            serializer.save(verified_by=self.request.user)
        else:
            raise permissions.PermissionDenied(
                "You can only add documents for guests in your hotel."
            )


class StayViewSet(viewsets.ModelViewSet):
    queryset = Stay.objects.all()
    serializer_class = StaySerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin, IsSameHotelUser]
    filterset_fields = ['status', 'check_in_date']
    ordering_fields = ['check_in_date', 'check_out_date']

    def get_queryset(self):
        return Stay.objects.filter(hotel=self.request.user.hotel)

    def perform_create(self, serializer):
        serializer.save(hotel=self.request.user.hotel)

    @action(
        detail=True,  # Acts on a specific stay instance
        methods=["post"],
        url_path="initiate-checkin",
        permission_classes=[IsHotelAdmin], # Or a more specific permission
    )
    def initiate_checkin(self, request, pk=None):
        """
        Initiates the WhatsApp check-in flow for a guest.
        """
        try:
            stay = self.get_object()
        except Stay.DoesNotExist:
            return Response(
                {"detail": "Stay not found in this hotel."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if stay.status != "pending":
            return Response(
                {"detail": f"Check-in cannot be initiated. Stay status is ''{stay.status}'' instead of ''pending''."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        guest = stay.guest
        if not guest.whatsapp_number:
            return Response(
                {"detail": "Guest does not have a WhatsApp number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create or update the conversation context for the guest
        context, created = ConversationContext.objects.update_or_create(
            user_id=guest.whatsapp_number,
            hotel=request.user.hotel,
            defaults={
                'context_data': {
                    'current_flow': 'guest_checkin',
                    'current_step': 'start',
                    'stay_id': stay.id,
                    'guest_id': guest.id,
                    'accumulated_data': {},
                    'navigation_stack': ['start'],
                    'error_count': 0,
                },
                'is_active': True,
            }
        )

        # TODO: Trigger a message to the user via a Celery task
        # For now, we just confirm the context is created.
        
        return Response(
            {"detail": "WhatsApp check-in flow initiated successfully."},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="check-in",
        permission_classes=[CanCheckInCheckOut],
    )
    def check_in(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stay_id = serializer.validated_data["stay_id"]

        try:
            stay = Stay.objects.get(pk=stay_id, hotel=request.user.hotel)
        except Stay.DoesNotExist:
            return Response(
                {"detail": "Stay not found in this hotel."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if stay.status != "pending":
            return Response(
                {"detail": f"Stay is already {stay.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not stay.identity_verified:
            return Response(
                {"detail": "Identity not verified for this stay."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room = stay.room
        if room.status != "available":
            return Response(
                {"detail": f"Room is not available. Current status: {room.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update statuses
        stay.status = "active"
        stay.actual_check_in = timezone.now()
        stay.save()

        room.status = "occupied"
        room.current_guest = stay.guest
        room.save()

        guest = stay.guest
        guest.status = "checked_in"
        guest.save()

        return Response(StaySerializer(stay).data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="check-out",
        permission_classes=[CanCheckInCheckOut],
    )
    def check_out(self, request):
        serializer = CheckOutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stay_id = serializer.validated_data["stay_id"]

        try:
            stay = Stay.objects.get(pk=stay_id, hotel=request.user.hotel)
        except Stay.DoesNotExist:
            return Response(
                {"detail": "Stay not found in this hotel."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if stay.status != "active":
            return Response(
                {"detail": f"Stay is not active. Current status: {stay.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update statuses
        stay.status = "completed"
        stay.actual_check_out = timezone.now()
        stay.save()

        room = stay.room
        room.status = "cleaning"  # Or 'available' based on hotel policy
        room.current_guest = None
        room.save()

        guest = stay.guest
        guest.status = "checked_out"
        guest.save()

        return Response(StaySerializer(stay).data, status=status.HTTP_200_OK)
