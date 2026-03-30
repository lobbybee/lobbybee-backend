from rest_framework import viewsets, permissions, status, generics, serializers
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.db.models import Q
from lobbybee.utils.responses import success_response, error_response, created_response, not_found_response
from lobbybee.utils.pagination import StandardizedPagination
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
import threading

from .models import Guest, GuestIdentityDocument, Stay, Booking
from .serializers import (
    CreateGuestSerializer, CheckinOfflineSerializer, VerifyCheckinSerializer,
    StayListSerializer, BookingListSerializer, GuestResponseSerializer, ExtendStaySerializer,
    CheckoutSerializer, CheckoutBulkSerializer, CheckedInGuestGroupSerializer
)
from .services_checkout import checkout_stays_for_guest
from hotel.models import Hotel, Room, WiFiCredential
from hotel.permissions import IsHotelStaff, IsSameHotelUser
from user.permissions import IsPlatformAdmin, IsPlatformStaff
from .permissions import CanManageGuests, CanViewAndManageStays
from flag_system.services import get_flag_summary_for_guest
from chat.utils.template_util import process_template
from chat.utils.whatsapp_utils import send_whatsapp_image_with_link, send_whatsapp_button_message, send_whatsapp_list_message, send_whatsapp_text_message, send_whatsapp_payload
from chat.utils.whatsapp_flow_utils import generate_department_menu_payload
from chat.models import Conversation
from guest.name_utils import get_first_name_from_full_name
import logging

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(StandardizedPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class GuestManagementViewSet(viewsets.GenericViewSet):
    """
    Simplified guest management endpoints
    """
    permission_classes = [permissions.IsAuthenticated, IsHotelStaff, IsSameHotelUser]

    def get_queryset(self):
        return Guest.objects.filter(
            Q(stays__hotel=self.request.user.hotel) | Q(bookings__hotel=self.request.user.hotel)
        ).distinct()

    @action(detail=False, methods=['post'], url_path='create-guest')
    def create_guest(self, request):
        """
        Create primary guest with accompanying guests and their documents.
        Returns guest IDs for use in booking/stay creation.

        Expected format:
        - Form data with primary_guest, accompanying_guests JSON
        - Files: primary_documents_0, primary_documents_1, guest_0_documents_0, guest_1_documents_0, etc.
        """
        serializer = CreateGuestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # Create primary guest
                primary_data = serializer.validated_data['primary_guest']
                primary_guest = Guest.objects.create(
                    whatsapp_number=primary_data['whatsapp_number'],
                    full_name=primary_data['full_name'],
                    email=primary_data.get('email', ''),
                    is_primary_guest=True,
                    status='pending_checkin'
                )

                # Create accompanying guests
                accompanying_guest_ids = []
                accompanying_guests_data = serializer.validated_data.get('accompanying_guests', [])

                for i, acc_guest_data in enumerate(accompanying_guests_data):
                    acc_guest = Guest.objects.create(
                        full_name=acc_guest_data['full_name'],
                        is_primary_guest=False,
                        status='pending_checkin',
                        whatsapp_number=f"ACC_{primary_guest.whatsapp_number}_{i+1}"
                    )
                    accompanying_guest_ids.append(acc_guest.id)

                # Handle primary guest documents
                primary_doc_count = 0
                while f'primary_documents_{primary_doc_count}' in request.FILES:
                    doc_file = request.FILES[f'primary_documents_{primary_doc_count}']
                    doc_back_file = request.FILES.get(f'primary_documents_back_{primary_doc_count}')

                    GuestIdentityDocument.objects.create(
                        guest=primary_guest,
                        document_type=primary_data.get('document_type', 'other'),
                        document_number=primary_data.get('document_number', ''),
                        document_file=doc_file,
                        document_file_back=doc_back_file,
                        is_accompanying_guest=False,
                        is_primary=(primary_doc_count == 0)  # First doc is primary
                    )
                    primary_doc_count += 1

                # Handle accompanying guest documents
                for i, acc_guest_id in enumerate(accompanying_guest_ids):
                    acc_guest_data = accompanying_guests_data[i]
                    acc_doc_count = 0

                    while f'guest_{i}_documents_{acc_doc_count}' in request.FILES:
                        doc_file = request.FILES[f'guest_{i}_documents_{acc_doc_count}']
                        doc_back_file = request.FILES.get(f'guest_{i}_documents_back_{acc_doc_count}')

                        GuestIdentityDocument.objects.create(
                            guest_id=acc_guest_id,
                            document_type=acc_guest_data.get('document_type', 'other'),
                            document_number=acc_guest_data.get('document_number', ''),
                            document_file=doc_file,
                            document_file_back=doc_back_file,
                            is_accompanying_guest=True,
                            is_primary=(acc_doc_count == 0)  # First doc is primary for this guest
                        )
                        acc_doc_count += 1

                return created_response(data={
                    'primary_guest_id': primary_guest.id,
                    'accompanying_guest_ids': accompanying_guest_ids,
                    'message': 'Guests created successfully'
                })

        except Exception as e:
            logger.error(f"Error creating guests: {str(e)}")
            return error_response(
                f'Failed to create guests: {str(e)}',
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='guests')
    def list_guests(self, request):
        """
        List all guests for the hotel with optional search functionality
        Query parameters:
        - search: Search term to filter guests by name, phone number, or ID number
        """
        try:
            queryset = self.get_queryset()
            search_term = request.query_params.get('search', None)

            if search_term:
                queryset = queryset.filter(
                    Q(full_name__icontains=search_term) |
                    Q(whatsapp_number__icontains=search_term) |
                    Q(identity_documents__document_number__icontains=search_term)
                ).distinct()

            serializer = GuestResponseSerializer(queryset, many=True)
            return success_response(data=serializer.data)
        except Exception as e:
            return error_response(f"Failed to list guests: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='bookings')
    def list_bookings(self, request):
        """
        List all bookings for the hotel
        """
        try:
            bookings = Booking.objects.filter(hotel=request.user.hotel)
            serializer = BookingListSerializer(bookings, many=True)
            return success_response(data=serializer.data)
        except Exception as e:
            return error_response(f"Failed to list bookings: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StayManagementViewSet(viewsets.GenericViewSet):
    """
    Simplified stay management endpoints
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAndManageStays, IsSameHotelUser]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Stay.objects.filter(hotel=self.request.user.hotel)

    @action(detail=False, methods=['post'], url_path='checkin-offline')
    def checkin_offline(self, request):
        """
        Create pending stays with room assignment.
        Creates booking record to group stays.
        """
        serializer = CheckinOfflineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                hotel = request.user.hotel
                primary_guest_id = serializer.validated_data['primary_guest_id']
                room_ids = serializer.validated_data['room_ids']
                check_in_date = serializer.validated_data['check_in_date']
                check_out_date = serializer.validated_data['check_out_date']
                guest_names = serializer.validated_data.get('guest_names', [])

                # Validate primary guest exists
                primary_guest = get_object_or_404(Guest, id=primary_guest_id)

                # Validate rooms exist and are available
                rooms = []
                for room_id in room_ids:
                    room = get_object_or_404(Room, id=room_id, hotel=hotel)
                    if room.status != 'available':
                        raise serializers.ValidationError(f"Room {room.room_number} is not available")
                    rooms.append(room)

                # Create dummy booking to group stays
                booking = Booking.objects.create(
                    hotel=hotel,
                    primary_guest=primary_guest,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    guest_names=guest_names,
                    status='confirmed',
                    total_amount=0  # Calculate based on room rates if needed
                )

                # Create stay records
                stays = []
                for i, room in enumerate(rooms):
                    guest_name = guest_names[i] if i < len(guest_names) else primary_guest.full_name

                    stay = Stay.objects.create(
                        booking=booking,
                        hotel=hotel,
                        guest=primary_guest,
                        room=room,
                        register_number=None,  # Will be set during verification
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        number_of_guests=1,
                        guest_names=[guest_name],
                        status='pending',
                        identity_verified=False,
                        documents_uploaded=True,
                    )
                    stays.append(stay)

                    # Update room status to occupied
                    room.status = 'occupied'
                    room.current_guest = primary_guest
                    room.save()

                return created_response(data={
                    'booking_id': booking.id,
                    'stay_ids': [stay.id for stay in stays],
                    'message': 'Check-in created successfully. Pending verification.'
                })

        except Exception as e:
            logger.error(f"Error creating check-in: {str(e)}")
            return error_response(
                f'Failed to create check-in: {str(e)}',
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['patch'], url_path='verify-checkin')
    def verify_checkin(self, request, pk=None):
        """
        Verify and activate a stay. Updates register number and marks as checked in.
        Can optionally update room assignment(s) and checkout date.
        """
        try:
            stay = self.get_object()
        except Exception:
            return not_found_response("Stay not found")

        if stay.status != 'pending':
            return error_response(
                f'Stay is not pending. Current status: {stay.status}',
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = VerifyCheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                stays_to_activate = [stay]
                if stay.booking_id:
                    related_pending_stays = list(
                        stay.booking.stays.select_for_update().filter(
                            guest=stay.guest,
                            status='pending'
                        ).exclude(id=stay.id).order_by('id')
                    )
                    stays_to_activate.extend(related_pending_stays)

                if 'room_id' in serializer.validated_data and 'room_ids' in serializer.validated_data:
                    return error_response(
                        'Provide either room_id or room_ids, not both',
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Update register number if provided
                if 'register_number' in serializer.validated_data:
                    stay.register_number = serializer.validated_data['register_number']

                # Update room if provided
                if 'room_id' in serializer.validated_data:
                    new_room = get_object_or_404(Room, id=serializer.validated_data['room_id'], hotel=stay.hotel)

                    # Validate availability for room switch (unless it's already the same room)
                    is_same_room = stay.room and stay.room.id == new_room.id
                    if not is_same_room and new_room.status != 'available':
                        return error_response(
                            f'Room {new_room.room_number} is not available for reassignment',
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    if not is_same_room:
                        # Free up old room
                        if stay.room:
                            stay.room.status = 'available'
                            stay.room.current_guest = None
                            stay.room.save()

                        # Assign new room
                        new_room.status = 'occupied'
                        new_room.current_guest = stay.guest
                        new_room.save()
                        stay.room = new_room
                elif 'room_ids' in serializer.validated_data:
                    requested_room_ids = serializer.validated_data['room_ids']
                    if not requested_room_ids:
                        return error_response(
                            'room_ids cannot be empty',
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    initial_pending_stays_count = len(stays_to_activate)
                    if len(requested_room_ids) < initial_pending_stays_count:
                        return error_response(
                            f'room_ids count cannot be less than pending stays count ({initial_pending_stays_count})',
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Mirror offline check-in behavior: if more rooms are provided than
                    # pending stays, create additional pending stays under the same booking.
                    if len(requested_room_ids) > initial_pending_stays_count:
                        if not stay.booking:
                            return error_response(
                                'Cannot add multiple rooms without a booking',
                                status=status.HTTP_400_BAD_REQUEST
                            )

                        extra_stays_count = len(requested_room_ids) - initial_pending_stays_count
                        booking_guest_names = stay.booking.guest_names or []

                        for i in range(extra_stays_count):
                            guest_index = initial_pending_stays_count + i
                            guest_name = (
                                booking_guest_names[guest_index]
                                if guest_index < len(booking_guest_names)
                                else stay.guest.full_name
                            )
                            new_pending_stay = Stay.objects.create(
                                booking=stay.booking,
                                hotel=stay.hotel,
                                guest=stay.guest,
                                room=None,
                                register_number=None,
                                check_in_date=stay.check_in_date,
                                check_out_date=stay.check_out_date,
                                number_of_guests=1,
                                guest_names=[guest_name],
                                status='pending',
                                identity_verified=False,
                                documents_uploaded=stay.documents_uploaded,
                                breakfast_reminder=stay.breakfast_reminder,
                                lunch_reminder=stay.lunch_reminder,
                                dinner_reminder=stay.dinner_reminder,
                            )
                            stays_to_activate.append(new_pending_stay)

                    if len(set(requested_room_ids)) != len(requested_room_ids):
                        return error_response(
                            'room_ids must be unique',
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    rooms_by_id = {
                        room.id: room for room in Room.objects.select_for_update().filter(
                            id__in=requested_room_ids,
                            hotel=stay.hotel
                        )
                    }
                    missing_room_ids = [room_id for room_id in requested_room_ids if room_id not in rooms_by_id]
                    if missing_room_ids:
                        return error_response(
                            f'Invalid room_ids for this hotel: {missing_room_ids}',
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    current_room_ids = {pending_stay.room_id for pending_stay in stays_to_activate if pending_stay.room_id}
                    for room_id in requested_room_ids:
                        room = rooms_by_id[room_id]
                        if room.status == 'available':
                            continue
                        if room.id in current_room_ids and room.current_guest_id == stay.guest_id:
                            continue
                        return error_response(
                            f'Room {room.room_number} is not available for reassignment',
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    room_assignments = list(zip(stays_to_activate, requested_room_ids))
                    requested_room_id_set = set(requested_room_ids)
                    rooms_to_release = []

                    for pending_stay, target_room_id in room_assignments:
                        old_room = pending_stay.room
                        if old_room and old_room.id != target_room_id and old_room.id not in requested_room_id_set:
                            rooms_to_release.append(old_room)

                    for pending_stay, target_room_id in room_assignments:
                        pending_stay.room = rooms_by_id[target_room_id]

                    for room in {rooms_by_id[room_id] for room_id in requested_room_ids}:
                        room.status = 'occupied'
                        room.current_guest = stay.guest
                        room.save()

                    for old_room in rooms_to_release:
                        old_room.status = 'available'
                        old_room.current_guest = None
                        old_room.save()

                # Update checkout date if provided
                if 'check_out_date' in serializer.validated_data:
                    new_checkout_date = serializer.validated_data['check_out_date']
                    for pending_stay in stays_to_activate:
                        pending_stay.check_out_date = new_checkout_date

                    # Also update booking checkout date if booking exists
                    if stay.booking:
                        stay.booking.check_out_date = new_checkout_date
                        stay.booking.save()

                # Update guest info if provided
                guest_updates = serializer.validated_data.get('guest_updates', {})
                if guest_updates:
                    for field, value in guest_updates.items():
                        if hasattr(stay.guest, field):
                            setattr(stay.guest, field, value)
                    stay.guest.save()

                # Handle document verification
                verified_document_ids = serializer.validated_data.get('verified_document_ids', [])
                verify_all_documents = serializer.validated_data.get('verify_all_documents', False)
                
                if verify_all_documents or verified_document_ids:
                    # Get documents to verify
                    if verify_all_documents:
                        documents_to_verify = GuestIdentityDocument.objects.filter(guest=stay.guest)
                    else:
                        documents_to_verify = GuestIdentityDocument.objects.filter(
                            guest=stay.guest,
                            id__in=verified_document_ids
                        )
                    
                    # Mark documents as verified
                    verified_count = documents_to_verify.update(
                        is_verified=True,
                        verified_at=timezone.now(),
                        verified_by=request.user
                    )
                    
                    logger.info(f"Verified {verified_count} documents for guest {stay.guest.full_name}")
                else:
                    # If no specific documents are marked for verification, 
                    # verify all primary documents by default
                    primary_documents = GuestIdentityDocument.objects.filter(
                        guest=stay.guest,
                        is_primary=True
                    )
                    verified_count = primary_documents.update(
                        is_verified=True,
                        verified_at=timezone.now(),
                        verified_by=request.user
                    )
                    
                    if verified_count > 0:
                        logger.info(f"Verified {verified_count} primary documents for guest {stay.guest.full_name}")

                # Update reminder settings from request
                if 'breakfast_reminder' in serializer.validated_data:
                    for pending_stay in stays_to_activate:
                        pending_stay.breakfast_reminder = serializer.validated_data['breakfast_reminder']
                if 'lunch_reminder' in serializer.validated_data:
                    for pending_stay in stays_to_activate:
                        pending_stay.lunch_reminder = serializer.validated_data['lunch_reminder']
                if 'dinner_reminder' in serializer.validated_data:
                    for pending_stay in stays_to_activate:
                        pending_stay.dinner_reminder = serializer.validated_data['dinner_reminder']

                # Mark all related pending stays as active in one verification action.
                activated_at = timezone.now()
                for pending_stay in stays_to_activate:
                    pending_stay.identity_verified = True
                    pending_stay.status = 'active'
                    pending_stay.actual_check_in = activated_at
                    pending_stay.save()

                # Update guest status
                stay.guest.status = 'checked_in'
                stay.guest.save()

                # Update booking status if all stays are active
                if stay.booking:
                    all_active = all(s.status == 'active' for s in stay.booking.stays.all())
                    if all_active:
                        stay.booking.status = 'confirmed'
                        stay.booking.save()

                # Send welcome message to guest's WhatsApp if number exists
                # This happens at the very end when all guest data is updated in the database
                if stay.guest.whatsapp_number:
                    def send_welcome_message_async():
                        try:
                            template_context = self._build_checkin_template_context(
                                stay,
                                stays_for_context=stays_to_activate,
                            )

                            # Process the welcome template with complete guest context
                            template_result = process_template(
                                hotel_id=stay.hotel.id,
                                template_name='lobbybee_hotel_welcome',
                                guest_id=stay.guest.id,
                                additional_context=template_context
                            )

                            if template_result['success']:
                                # Get the processed content and media URL
                                welcome_message = template_result['processed_content']
                                media_url = template_result.get('media_url')

                                # Use default mascot image if no template media
                                if not media_url:
                                    media_url = 'https://www.lobbybee.com/mascot.png'

                                # Send welcome message with image via WhatsApp
                                send_whatsapp_image_with_link(
                                    recipient_number=stay.guest.whatsapp_number,
                                    image_url=media_url,
                                    caption=welcome_message
                                )

                                available_departments = self._get_available_departments_for_hotel(stay.hotel)
                                guest_name = get_first_name_from_full_name(stay.guest.full_name)
                                menu_payload = generate_department_menu_payload(
                                    stay.guest.whatsapp_number,
                                    guest_name,
                                    available_departments
                                )
                                send_whatsapp_payload(menu_payload)

                                logger.info(f"Welcome message sent to guest {stay.guest.full_name} ({stay.guest.whatsapp_number})")
                            else:
                                logger.error(f"Failed to process welcome template for guest {stay.guest.full_name}: {template_result.get('error', 'Unknown error')}")

                        except Exception as e:
                            logger.error(f"Failed to send welcome message to guest {stay.guest.whatsapp_number}: {str(e)}")

                    # Send welcome message asynchronously without waiting for the request
                    thread = threading.Thread(target=send_welcome_message_async)
                    thread.daemon = True
                    thread.start()

                # Schedule check-in reminder message using Celery
                if stay.guest.whatsapp_number:
                    from .tasks import schedule_checkout_extension_reminder, schedule_meal_reminders
                    is_test_reminder = serializer.validated_data.get('is_test', False)
                    stay_id = stay.id

                    # Evaluate effective reminder flags from the freshly-updated stay.
                    breakfast_enabled = stay.hotel.breakfast_reminder and stay.breakfast_reminder
                    lunch_enabled = stay.lunch_reminder
                    dinner_enabled = stay.hotel.dinner_reminder and stay.dinner_reminder

                    def schedule_reminders_after_commit():
                        # Schedule checkout reminder after transaction commits to avoid stale reads.
                        schedule_checkout_extension_reminder.delay(stay_id, is_test_reminder)

                        # Schedule meal reminders only when at least one meal reminder is enabled.
                        if breakfast_enabled or lunch_enabled or dinner_enabled:
                            schedule_meal_reminders.delay(stay_id)

                    transaction.on_commit(schedule_reminders_after_commit)

                # Check for guest flags before completing check-in
                from flag_system.serializers import GuestFlagSummarySerializer, GuestFlagResponseSerializer
                
                flag_summary = get_flag_summary_for_guest(stay.guest.id)
                
                response_data = {
                    'stay_id': stay.id,
                    'activated_stay_ids': [pending_stay.id for pending_stay in stays_to_activate],
                    'register_number': stay.register_number,
                    'room_ids': [pending_stay.room_id for pending_stay in stays_to_activate],
                    'check_out_date': stay.check_out_date,
                    'message': f'Check-in verified and activated successfully for {len(stays_to_activate)} stay(s)'
                }
                
                # Include flag summary if guest is flagged
                if flag_summary['is_flagged']:
                    # Serialize flags first
                    serialized_flags = GuestFlagResponseSerializer(
                        flag_summary['flags'], 
                        many=True
                    ).data
                    
                    # For hotel staff, remove internal_reason from flags
                    if request.user.user_type in ['hotel_admin', 'manager', 'receptionist']:
                        for flag_data in serialized_flags:
                            flag_data.pop('internal_reason', None)
                    
                    # Create flag summary with serialized flags
                    flag_summary_data = {
                        'is_flagged': flag_summary['is_flagged'],
                        'police_flagged': flag_summary['police_flagged'],
                        'flags': serialized_flags
                    }
                    response_data['flag_summary'] = flag_summary_data
                
                return success_response(data=response_data)

        except Exception as e:
            logger.error(f"Error verifying check-in: {str(e)}")
            return error_response(
                f'Failed to verify check-in: {str(e)}',
                status=status.HTTP_400_BAD_REQUEST
            )

    def _get_available_departments_for_hotel(self, hotel):
        """
        Resolve departments dynamically from active hotel staff assignments.
        """
        default_departments = [choice[0] for choice in Conversation.DEPARTMENT_CHOICES]
        if not hotel:
            return default_departments

        User = get_user_model()
        staff_departments = User.objects.filter(
            hotel=hotel,
            is_active_hotel_user=True
        ).exclude(
            department__isnull=True
        ).values_list("department", flat=True)

        resolved_departments = []
        seen = set()

        for department_value in staff_departments:
            if isinstance(department_value, str):
                values_to_check = [department_value]
            elif isinstance(department_value, list):
                values_to_check = department_value
            else:
                continue

            for raw_department in values_to_check:
                if not isinstance(raw_department, str):
                    continue

                raw_department = raw_department.strip()
                if not raw_department:
                    continue

                canonical_department = next(
                    (
                        dept
                        for dept in default_departments
                        if dept.lower() == raw_department.lower()
                    ),
                    None,
                )

                if canonical_department and canonical_department not in seen:
                    seen.add(canonical_department)
                    resolved_departments.append(canonical_department)

        return resolved_departments or default_departments

    def _get_wifi_credentials_for_stay(self, stay):
        """
        Get WiFi credentials for a stay using room floor + category preference.
        """
        if not stay.room:
            return None

        # Prefer category-specific credentials for the room's floor.
        credential = WiFiCredential.objects.filter(
            hotel=stay.hotel,
            floor=stay.room.floor,
            room_category=stay.room.category,
            is_active=True
        ).first()

        if credential:
            return credential

        # Fall back to floor-wide credentials.
        return WiFiCredential.objects.filter(
            hotel=stay.hotel,
            floor=stay.room.floor,
            room_category__isnull=True,
            is_active=True
        ).first()

    def _build_room_context(self, stays):
        """
        Build consolidated room/WiFi context for one or multiple stays.
        """
        room_entries = []
        seen_room_ids = set()
        for current_stay in stays:
            room = getattr(current_stay, 'room', None)
            if not room or room.id in seen_room_ids:
                continue
            seen_room_ids.add(room.id)
            wifi_credential = self._get_wifi_credentials_for_stay(current_stay)
            room_entries.append({
                'room_number': room.room_number,
                'room_floor': room.floor,
                'wifi_name': wifi_credential.network_name if wifi_credential else '',
                'wifi_password': wifi_credential.password if wifi_credential else '',
            })

        room_entries.sort(key=lambda item: str(item['room_number']))
        room_numbers = [str(item['room_number']) for item in room_entries]
        room_floors = [str(item['room_floor']) for item in room_entries if item['room_floor'] is not None]

        unique_wifi_names = {item['wifi_name'] for item in room_entries if item['wifi_name']}
        unique_wifi_passwords = {item['wifi_password'] for item in room_entries if item['wifi_password']}

        wifi_name = ''
        if len(unique_wifi_names) == 1:
            wifi_name = next(iter(unique_wifi_names))
        elif len(unique_wifi_names) > 1:
            wifi_name = ', '.join(
                f"{item['room_number']}:{item['wifi_name']}"
                for item in room_entries
                if item['wifi_name']
            )

        wifi_password = ''
        if len(unique_wifi_passwords) == 1:
            wifi_password = next(iter(unique_wifi_passwords))
        elif len(unique_wifi_passwords) > 1:
            wifi_password = ', '.join(
                f"{item['room_number']}:{item['wifi_password']}"
                for item in room_entries
                if item['wifi_password']
            )

        return {
            'room_number': ', '.join(room_numbers),
            'room_floor': ', '.join(room_floors),
            'wifi_name': wifi_name,
            'wifi_password': wifi_password,
        }

    def _build_checkin_template_context(self, stay, stays_for_context=None):
        """
        Build additional template context for check-in confirmation templates.
        """
        if stays_for_context is None:
            stays_for_context = list(
                Stay.objects.filter(
                    guest=stay.guest,
                    hotel=stay.hotel,
                    status='active'
                ).select_related('room', 'room__category')
            )
        if not stays_for_context:
            stays_for_context = [stay]

        checkin_candidates = [
            s.actual_check_in or s.check_in_date
            for s in stays_for_context
            if (s.actual_check_in or s.check_in_date)
        ]
        checkout_candidates = [s.check_out_date for s in stays_for_context if s.check_out_date]
        checkin_dt = min(checkin_candidates) if checkin_candidates else (stay.actual_check_in or stay.check_in_date)
        checkout_dt = max(checkout_candidates) if checkout_candidates else stay.check_out_date
        room_context = self._build_room_context(stays_for_context)

        return {
            # WiFi variables requested for templates.
            'wifi_name': room_context['wifi_name'],
            'wifi_password': room_context['wifi_password'],
            'hotel_timezone': stay.hotel.time_zone or 'UTC',
            # Time variables requested for templates.
            'checkin_time': checkin_dt,
            'checkout_time': checkout_dt,
            # Compatibility aliases that some templates may already use.
            'check_in_time': checkin_dt,
            'check_out_time': checkout_dt,
            # Explicit room fallbacks for template edge cases.
            'room_number': room_context['room_number'],
            'room_floor': room_context['room_floor'],
        }

    @action(detail=False, methods=['get'], url_path='pending-stays')
    def pending_stays(self, request):
        """
        List all stays that are pending verification with flag information
        """
        stays = self.get_queryset().filter(status='pending').order_by('-created_at')
        
        # Get all unique guest IDs from pending stays
        guest_ids = list(set(stay.guest_id for stay in stays))
        
        # Pre-fetch flag information for all these guests
        flag_summary_map = {}
        if guest_ids:
            from flag_system.serializers import GuestFlagSummarySerializer, GuestFlagResponseSerializer
            for guest_id in guest_ids:
                flag_summary = get_flag_summary_for_guest(guest_id)
                if flag_summary['is_flagged']:
                    # Serialize flags first
                    serialized_flags = GuestFlagResponseSerializer(
                        flag_summary['flags'], 
                        many=True
                    ).data
                    
                    # Remove internal_reason for hotel staff
                    if request.user.user_type in ['hotel_admin', 'manager', 'receptionist']:
                        for flag_data in serialized_flags:
                            flag_data.pop('internal_reason', None)
                    
                    # Update flag summary with serialized flags
                    flag_summary['flags'] = serialized_flags
                    flag_summary_map[guest_id] = flag_summary
        
        # Serialize stays and add flag information
        serializer = StayListSerializer(stays, many=True)
        response_data = serializer.data
        
        # Add flag information to each stay
        for stay_data in response_data:
            guest_id = stay_data['guest']['id']
            if guest_id in flag_summary_map:
                stay_data['flag_summary'] = flag_summary_map[guest_id]
        
        return success_response(data=response_data)

    @action(detail=False, methods=['get'], url_path='checked-in-users')
    def checked_in_users(self, request):
        """
        List all stays for the hotel with optional search and checked-in status flag.
        """
        stays = self.get_queryset()
        search_term = request.query_params.get('search', None)

        if search_term:
            stays = stays.filter(
                Q(guest__full_name__icontains=search_term) |
                Q(guest__whatsapp_number__icontains=search_term) |
                Q(guest__identity_documents__document_number__icontains=search_term)
            ).distinct()

        stays = stays.order_by('-created_at')

        page = self.paginate_queryset(stays)
        if page is not None:
            serializer = StayListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = StayListSerializer(stays, many=True)
        return success_response(data=serializer.data)

    @action(detail=False, methods=['get'], url_path='checked-in-users-grouped')
    def checked_in_users_grouped(self, request):
        """
        Group checked-in users by guest with room-level stay data and aggregated billing.
        """
        return self._group_stays_by_guest(request, active_only=True)

    @action(detail=False, methods=['get'], url_path='stays-history-grouped')
    def stays_history_grouped(self, request):
        """
        Group stay history by guest with search and pagination.
        Includes all statuses (active, pending, completed, cancelled).
        """
        return self._group_stays_by_guest(request, active_only=False)

    @action(detail=True, methods=['post'], url_path='checkout')
    def checkout_user(self, request, pk=None):
        """
        Legacy single-stay checkout endpoint.
        Backward compatible wrapper over bulk checkout service.
        """
        try:
            stay = self.get_object()
        except Exception:
            return not_found_response("Stay not found")

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = checkout_stays_for_guest(
                hotel=request.user.hotel,
                guest_id=stay.guest_id,
                stay_ids=[stay.id],
                actor=request.user,
                options=serializer.validated_data,
            )
        except serializers.ValidationError as exc:
            return error_response(str(exc.detail), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error checking out guest: {str(e)}")
            return error_response(
                f'Failed to check out guest: {str(e)}',
                status=status.HTTP_400_BAD_REQUEST
            )

        checkout_message_sent = False
        feedback_triggered = False
        if result['should_send_comms']:
            checkout_message_sent, feedback_triggered = self._send_checkout_message_and_feedback(
                representative_stay=result['representative_stay'],
                checked_out_stays=result['checked_out_stays'],
            )

        checked_out_stay = result['checked_out_stays'][0]
        response_data = {
            'stay_id': checked_out_stay.id,
            'message': 'Guest checked out successfully',
            'total_amount': str(checked_out_stay.total_amount),
            'guest_id': result['guest'].id,
            'checked_out_stay_ids': [checked_out_stay.id],
            'guest_has_active_stays': result['guest_has_active_stays'],
            'checkout_message_sent': checkout_message_sent,
            'feedback_triggered': feedback_triggered,
        }
        if checked_out_stay.internal_rating is not None:
            response_data['internal_rating'] = checked_out_stay.internal_rating
        if checked_out_stay.internal_note:
            response_data['internal_note'] = checked_out_stay.internal_note

        return success_response(data=response_data)

    @action(detail=False, methods=['post'], url_path='checkout-bulk')
    def checkout_bulk(self, request):
        """
        Checkout multiple stays for a single guest in one request.
        """
        serializer = CheckoutBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            result = checkout_stays_for_guest(
                hotel=request.user.hotel,
                guest_id=payload['guest_id'],
                stay_ids=payload['stay_ids'],
                actor=request.user,
                options=payload,
            )
        except serializers.ValidationError as exc:
            return error_response(str(exc.detail), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in bulk checkout: {str(e)}")
            return error_response(
                f'Failed to bulk check out guest: {str(e)}',
                status=status.HTTP_400_BAD_REQUEST
            )

        checkout_message_sent = False
        feedback_triggered = False
        if result['should_send_comms']:
            checkout_message_sent, feedback_triggered = self._send_checkout_message_and_feedback(
                representative_stay=result['representative_stay'],
                checked_out_stays=result['checked_out_stays'],
            )

        response_data = {
            'guest_id': result['guest'].id,
            'checked_out_stay_ids': [stay.id for stay in result['checked_out_stays']],
            'skipped_stay_ids': [],
            'guest_has_active_stays': result['guest_has_active_stays'],
            'checkout_message_sent': checkout_message_sent,
            'feedback_triggered': feedback_triggered,
            'total_amount': str(result['total_amount']),
            'message': 'Guest stays checked out successfully',
        }
        return success_response(data=response_data)

    def _build_checkout_template_context(self, stay, checked_out_stays=None):
        """
        Build additional template context for checkout thank-you templates.
        """
        # Prefer booking-wide room context so the final checkout message
        # includes all rooms booked together in the same transaction.
        if stay.booking_id:
            stays_for_context = list(
                stay.booking.stays.select_related('room', 'room__category').all()
            )
        else:
            stays_for_context = checked_out_stays or [stay]
        checkin_candidates = [
            s.actual_check_in or s.check_in_date
            for s in stays_for_context
            if (s.actual_check_in or s.check_in_date)
        ]
        checkout_candidates = [
            s.actual_check_out or s.check_out_date
            for s in stays_for_context
            if (s.actual_check_out or s.check_out_date)
        ]
        checkin_dt = min(checkin_candidates) if checkin_candidates else (stay.actual_check_in or stay.check_in_date)
        checkout_dt = max(checkout_candidates) if checkout_candidates else (stay.actual_check_out or timezone.now())
        room_context = self._build_room_context(stays_for_context)

        stay_duration = ''
        if checkin_dt and checkout_dt and checkout_dt >= checkin_dt:
            duration = checkout_dt - checkin_dt
            total_minutes = int(duration.total_seconds() // 60)
            days, rem_minutes = divmod(total_minutes, 1440)
            hours, minutes = divmod(rem_minutes, 60)
            duration_parts = []
            if days:
                duration_parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours:
                duration_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes and days == 0:
                duration_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            stay_duration = ', '.join(duration_parts) if duration_parts else '0 minutes'

        return {
            'hotel_timezone': stay.hotel.time_zone or 'UTC',
            'checkin_time': checkin_dt,
            'checkout_time': checkout_dt,
            'room_number': room_context['room_number'],
            'room_floor': room_context['room_floor'],
            'wifi_name': room_context['wifi_name'],
            'wifi_password': room_context['wifi_password'],
            'stay_duration': stay_duration,
            # Compatibility aliases if template uses underscore style keys.
            'check_in_time': checkin_dt,
            'check_out_time': checkout_dt,
        }

    def _get_flag_summary_map(self, request, guest_ids):
        flag_summary_map = {}
        if not guest_ids:
            return flag_summary_map

        from flag_system.serializers import GuestFlagResponseSerializer

        for guest_id in guest_ids:
            flag_summary = get_flag_summary_for_guest(guest_id)
            if not flag_summary['is_flagged']:
                continue

            serialized_flags = GuestFlagResponseSerializer(flag_summary['flags'], many=True).data
            if request.user.user_type in ['hotel_admin', 'manager', 'receptionist']:
                for flag_data in serialized_flags:
                    flag_data.pop('internal_reason', None)

            flag_summary['flags'] = serialized_flags
            flag_summary_map[guest_id] = flag_summary

        return flag_summary_map

    def _group_stays_by_guest(self, request, active_only=False):
        stays = self.get_queryset().select_related(
            'guest', 'room', 'room__category', 'booking'
        )
        search_term = request.query_params.get('search', None)

        if search_term:
            stays = stays.filter(
                Q(guest__full_name__icontains=search_term) |
                Q(guest__whatsapp_number__icontains=search_term) |
                Q(guest__identity_documents__document_number__icontains=search_term)
            ).distinct()

        if active_only:
            stays = stays.filter(status='active')

        stays = stays.order_by('-created_at')
        grouped_by_guest = {}
        guest_order = []

        for stay in stays:
            guest_id = stay.guest_id
            if guest_id not in grouped_by_guest:
                grouped_by_guest[guest_id] = {
                    'guest': stay.guest,
                    'stays': [],
                    'active_stay_ids': [],
                    'pending_stay_ids': [],
                    'completed_stay_ids': [],
                    'is_checked_in': False,
                }
                guest_order.append(guest_id)

            group = grouped_by_guest[guest_id]
            group['stays'].append(stay)
            if stay.status == 'active':
                group['active_stay_ids'].append(stay.id)
                group['is_checked_in'] = True
            elif stay.status == 'pending':
                group['pending_stay_ids'].append(stay.id)
            elif stay.status == 'completed':
                group['completed_stay_ids'].append(stay.id)

        flag_summary_map = self._get_flag_summary_map(request, guest_order)
        grouped_rows = []
        from .services import calculate_stay_billing
        for guest_id in guest_order:
            group = grouped_by_guest[guest_id]
            room_billing_rows = []
            current_bill_total = 0.0
            expected_bill_total = 0.0

            for stay in group['stays']:
                billing = calculate_stay_billing(stay)
                current_bill_total += float(billing.get('current_bill', 0))
                expected_bill_total += float(billing.get('expected_bill', 0))
                room_billing_rows.append({
                    'stay_id': stay.id,
                    'room_id': stay.room_id,
                    'current_bill': billing.get('current_bill', 0),
                    'expected_bill': billing.get('expected_bill', 0),
                })

            group_row = {
                'guest': group['guest'],
                'is_checked_in': group['is_checked_in'],
                'stays': group['stays'],
                'billing': {
                    'current_bill_total': round(current_bill_total, 2),
                    'expected_bill_total': round(expected_bill_total, 2),
                    'rooms': room_billing_rows,
                },
                'active_stay_ids': group['active_stay_ids'],
                'pending_stay_ids': group['pending_stay_ids'],
                'completed_stay_ids': group['completed_stay_ids'],
            }
            if guest_id in flag_summary_map:
                group_row['flag_summary'] = flag_summary_map[guest_id]
            grouped_rows.append(group_row)

        page = self.paginate_queryset(grouped_rows)
        if page is not None:
            serializer = CheckedInGuestGroupSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CheckedInGuestGroupSerializer(grouped_rows, many=True)
        return success_response(data=serializer.data)

    def _send_checkout_message_and_feedback(self, representative_stay, checked_out_stays=None):
        checkout_message_sent = False
        feedback_triggered = False
        guest = representative_stay.guest
        hotel = representative_stay.hotel

        closed_conversations_count = Conversation.objects.filter(
            guest=guest,
            hotel=hotel,
            status='active'
        ).update(status='closed')
        logger.info(
            f"Closed {closed_conversations_count} active conversations for guest "
            f"{guest.full_name} before checkout communications"
        )

        if guest.whatsapp_number:
            try:
                template_context = self._build_checkout_template_context(
                    representative_stay,
                    checked_out_stays=checked_out_stays,
                )
                template_result = process_template(
                    hotel_id=hotel.id,
                    template_name='lobbybee_checkout_thank_you',
                    guest_id=guest.id,
                    additional_context=template_context
                )

                if template_result.get('success'):
                    checkout_message = template_result.get('processed_content', '')
                    checkout_media_url = template_result.get('media_url')

                    if checkout_media_url:
                        send_whatsapp_image_with_link(
                            recipient_number=guest.whatsapp_number,
                            image_url=checkout_media_url,
                            caption=checkout_message
                        )
                    elif checkout_message:
                        send_whatsapp_text_message(
                            recipient_number=guest.whatsapp_number,
                            message_text=checkout_message
                        )
                    checkout_message_sent = True
                else:
                    logger.warning(
                        f"Checkout template processing failed for stay {representative_stay.id}: "
                        f"{template_result.get('error', 'Unknown error')}"
                    )
            except Exception as template_err:
                logger.error(
                    f"Failed to send checkout thank-you template for stay {representative_stay.id}: "
                    f"{template_err}",
                    exc_info=True
                )

        from .models import Feedback

        feedback_exists = Feedback.objects.filter(
            guest=guest,
            stay__hotel=hotel
        ).exists()
        if not feedback_exists:
            Conversation.objects.filter(
                guest=guest,
                hotel=hotel,
                conversation_type='feedback',
                status='active'
            ).update(status='archived')

            conversation = Conversation.objects.create(
                guest=guest,
                hotel=hotel,
                department='Reception',
                conversation_type='feedback',
                status='active'
            )

            header_text = f"How was your stay at {hotel.name}?"
            body_text = (
                f"Thank you for staying with us at {hotel.name}!\n\n"
                "We hope you had a wonderful experience and your stay was comfortable. "
                "Your feedback helps us improve our service and ensure we continue to "
                "provide exceptional hospitality.\n\n"
                "Please take a moment to rate your overall experience from 1 to 5 stars. "
                "We truly appreciate your time and feedback!"
            )
            rating_options = [
                {"id": "rating_1", "title": "⭐ Poor"},
                {"id": "rating_2", "title": "⭐⭐ Fair"},
                {"id": "rating_3", "title": "⭐⭐⭐ Good"},
                {"id": "rating_4", "title": "⭐⭐⭐⭐ Very Good"},
                {"id": "rating_5", "title": "⭐⭐⭐⭐⭐ Excellent"}
            ]

            try:
                from chat.flows.feedback_flow import save_system_message, FeedbackStep
                save_system_message(
                    conversation,
                    f"{header_text}\n\n{body_text}",
                    FeedbackStep.RATING
                )
                send_whatsapp_list_message(
                    recipient_number=guest.whatsapp_number,
                    header_text=header_text,
                    body_text=body_text,
                    options=rating_options
                )
                feedback_triggered = True
                logger.info(f"Feedback list message sent to guest {guest.full_name} ({guest.whatsapp_number})")
            except Exception as err:
                logger.error(f"Failed to send feedback list message: {err}")

        return checkout_message_sent, feedback_triggered

    @action(detail=True, methods=['post'], url_path='extend-stay')
    def extend_stay(self, request, pk=None):
        """
        Extend an active guest's stay by updating the checkout date.
        Only works for stays with 'active' status.
        """
        try:
            stay = self.get_object()
        except Exception:
            return not_found_response("Stay not found")

        if stay.status != 'active':
            return error_response(
                f'Can only extend active stays. Current status: {stay.status}',
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ExtendStaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                new_checkout_date = serializer.validated_data['check_out_date']
                
                # Validate that new checkout date is after current checkout date
                if new_checkout_date <= stay.check_out_date:
                    return error_response(
                        'New checkout date must be after the current checkout date',
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Update stay checkout date
                old_checkout_date = stay.check_out_date
                stay.check_out_date = new_checkout_date
                stay.save()

                # Also update booking checkout date if booking exists
                if stay.booking:
                    stay.booking.check_out_date = new_checkout_date
                    stay.booking.save()

                # Revoke the old extension reminder (deterministic task ID) and reschedule
                from celery import current_app
                current_app.control.revoke(f"extend_reminder_{stay.id}")
                from .tasks import schedule_checkout_extension_reminder, schedule_meal_reminders
                stay_id = stay.id

                # Schedule meal reminders for the newly added days.
                # Deterministic date-based task IDs make this idempotent for already-scheduled days.
                if stay.guest.whatsapp_number:
                    breakfast_enabled = stay.hotel.breakfast_reminder and stay.breakfast_reminder
                    lunch_enabled = stay.lunch_reminder
                    dinner_enabled = stay.hotel.dinner_reminder and stay.dinner_reminder

                    def schedule_extended_stay_reminders_after_commit():
                        schedule_checkout_extension_reminder.delay(stay_id)
                        if breakfast_enabled or lunch_enabled or dinner_enabled:
                            schedule_meal_reminders.delay(stay_id)

                    transaction.on_commit(schedule_extended_stay_reminders_after_commit)
                else:
                    transaction.on_commit(lambda: schedule_checkout_extension_reminder.delay(stay_id))

                logger.info(f"Extended stay for guest {stay.guest.full_name} from {old_checkout_date} to {new_checkout_date}")

                return success_response(data={
                    'stay_id': stay.id,
                    'old_checkout_date': old_checkout_date,
                    'new_checkout_date': new_checkout_date,
                    'message': 'Stay extended successfully'
                })

        except Exception as e:
            logger.error(f"Error extending stay: {str(e)}")
            return error_response(
                f'Failed to extend stay: {str(e)}',
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'], url_path='reject-checkin')
    def reject_checkin(self, request, pk=None):
        """
        Reject a pending checkin request.
        Cleans up all pending data and notifies the guest via WhatsApp.
        """
        try:
            stay = self.get_object()
        except Exception:
            return not_found_response("Stay not found")

        if stay.status not in ['pending']:
            return error_response(
                f'Can only reject pending checkins. Current status: {stay.status}',
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                guest = stay.guest
                
                # Clean up all pending stays and bookings for this guest (both new and returning guests)
                from chat.flows.checkin_flow import cleanup_incomplete_guest_data, cleanup_incomplete_guest_data_preserve_personal_info
                
                # Check if guest has completed stays before (returning guest)
                from guest.models import Stay as GuestStay
                # Always preserve guest personal information - just clean incomplete bookings/stays
                # Guests can update their info if needed
                cleanup_incomplete_guest_data_preserve_personal_info(guest)
                
                # Close all active conversations for this guest
                from chat.models import Conversation
                closed_conversations_count = Conversation.objects.filter(
                    guest=guest,
                    hotel=stay.hotel,
                    status='active'
                ).update(status='closed')
                
                logger.info(f"Closed {closed_conversations_count} active conversations for guest {guest.full_name} after rejection")

                # Send rejection message to guest via WhatsApp
                if guest.whatsapp_number:
                    def send_rejection_message_async():
                        try:
                            rejection_message = "Sorry, the hotel has declined your check-in request. Have a nice day!"
                            send_whatsapp_text_message(
                                recipient_number=guest.whatsapp_number,
                                message_text=rejection_message
                            )
                            logger.info(f"Rejection message sent to guest {guest.full_name} ({guest.whatsapp_number})")
                        except Exception as e:
                            logger.error(f"Failed to send rejection message to guest {guest.whatsapp_number}: {str(e)}")

                    # Send rejection message asynchronously
                    thread = threading.Thread(target=send_rejection_message_async)
                    thread.daemon = True
                    thread.start()

                return success_response(data={
                    'guest_id': guest.id,
                    'guest_name': guest.full_name,
                    'whatsapp_number': guest.whatsapp_number,
                    'message': 'Checkin rejected and guest notified successfully'
                })

        except Exception as e:
            logger.error(f"Error rejecting checkin: {str(e)}")
            return error_response(
                f'Failed to reject checkin: {str(e)}',
                status=status.HTTP_400_BAD_REQUEST
            )


class ScheduleTestReminderView(APIView):
    """
    Platform admin/staff only — schedule a one-off WhatsApp reminder for a stay.

    POST body:
        hotel_id      (required) — hotel UUID
        stay_id       (required) — stay integer PK
        guest_id      (required) — guest integer PK
        reminder_date (required) — "YYYY-MM-DD"  (hotel local date)
        reminder_time (required) — "HH:MM"       (hotel local 24-hour time)

    The reminder is sent using send_extend_checkin_reminder with is_test=True,
    which bypasses the 4-hour stale-reminder guard.
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin | IsPlatformStaff]

    def post(self, request):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        from datetime import datetime as dt

        # --- Validate required fields ---
        hotel_id = request.data.get('hotel_id')
        stay_id = request.data.get('stay_id')
        guest_id = request.data.get('guest_id')
        reminder_date = request.data.get('reminder_date')   # "YYYY-MM-DD"
        reminder_time = request.data.get('reminder_time')   # "HH:MM"

        missing = [f for f, v in [
            ('hotel_id', hotel_id), ('stay_id', stay_id), ('guest_id', guest_id),
            ('reminder_date', reminder_date), ('reminder_time', reminder_time)
        ] if not v]
        if missing:
            return error_response(f"Missing required fields: {', '.join(missing)}", status=status.HTTP_400_BAD_REQUEST)

        # --- Parse date/time ---
        try:
            naive_dt = dt.strptime(f"{reminder_date} {reminder_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            return error_response(
                "Invalid date/time format. Use reminder_date=YYYY-MM-DD and reminder_time=HH:MM",
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Fetch objects ---
        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            return not_found_response("Hotel not found")

        try:
            stay = Stay.objects.select_related('guest', 'hotel').get(id=stay_id, hotel=hotel)
        except Stay.DoesNotExist:
            return not_found_response("Stay not found for this hotel")

        if str(stay.guest.id) != str(guest_id):
            return error_response("guest_id does not match the stay's guest", status=status.HTTP_400_BAD_REQUEST)

        if not stay.guest.whatsapp_number:
            return error_response("Guest has no WhatsApp number", status=status.HTTP_400_BAD_REQUEST)

        # --- Convert hotel-local datetime to UTC countdown ---
        try:
            hotel_tz = ZoneInfo(hotel.time_zone or 'UTC')
        except (ZoneInfoNotFoundError, KeyError):
            hotel_tz = ZoneInfo('UTC')

        reminder_dt_local = naive_dt.replace(tzinfo=hotel_tz)
        now = timezone.now()
        countdown = int((reminder_dt_local - now).total_seconds())

        if countdown <= 0:
            return error_response(
                f"reminder_date/time is in the past (hotel local: {naive_dt}, hotel tz: {hotel.time_zone})",
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Schedule ---
        from .tasks import send_extend_checkin_reminder
        task_id = f"test_reminder_{stay_id}_{reminder_date}_{reminder_time.replace(':', '')}"
        send_extend_checkin_reminder.apply_async(
            args=[stay_id, True],
            countdown=countdown,
            task_id=task_id
        )

        logger.info(
            f"Platform user {request.user.email} scheduled test reminder for stay {stay_id} "
            f"at {naive_dt} {hotel.time_zone} (countdown={countdown}s, task_id={task_id})"
        )

        return success_response(data={
            'task_id': task_id,
            'stay_id': stay_id,
            'guest_id': str(stay.guest.id),
            'whatsapp_number': stay.guest.whatsapp_number,
            'scheduled_for_local': str(naive_dt),
            'hotel_timezone': hotel.time_zone,
            'countdown_seconds': countdown,
        })
