from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from django.db.models import Q, Sum
from lobbybee.utils.responses import success_response, error_response, created_response, not_found_response
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
import threading
import math
from decimal import Decimal

from .models import Guest, GuestIdentityDocument, Stay, Booking
from .serializers import (
    CreateGuestSerializer, CheckinOfflineSerializer, VerifyCheckinSerializer,
    StayListSerializer, BookingListSerializer, GuestResponseSerializer, ExtendStaySerializer
)
from hotel.models import Hotel, Room, WiFiCredential
from hotel.permissions import IsHotelStaff, IsSameHotelUser
from .permissions import CanManageGuests, CanViewAndManageStays
from flag_system.models import GuestFlag
from flag_system.services import get_flag_summary_for_guest, create_guest_flag
from chat.utils.template_util import process_template
from chat.utils.whatsapp_utils import send_whatsapp_image_with_link, send_whatsapp_button_message, send_whatsapp_list_message, send_whatsapp_text_message
import logging

logger = logging.getLogger(__name__)


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
        - search: Search term to filter guests by name or phone number
        """
        try:
            queryset = self.get_queryset()
            search_term = request.query_params.get('search', None)

            if search_term:
                queryset = queryset.filter(
                    Q(full_name__icontains=search_term) |
                    Q(whatsapp_number__icontains=search_term)
                )

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
                hours_24 = serializer.validated_data.get('hours_24', False)

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
                        hours_24=hours_24
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
        Can optionally update room assignment and checkout date.
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

                # Update checkout date if provided
                if 'check_out_date' in serializer.validated_data:
                    new_checkout_date = serializer.validated_data['check_out_date']
                    stay.check_out_date = new_checkout_date

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
                    stay.breakfast_reminder = serializer.validated_data['breakfast_reminder']
                if 'dinner_reminder' in serializer.validated_data:
                    stay.dinner_reminder = serializer.validated_data['dinner_reminder']

                # Mark identity as verified (assuming manual verification by staff)
                stay.identity_verified = True
                stay.status = 'active'
                stay.actual_check_in = timezone.now()
                stay.save()

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
                            template_context = self._build_checkin_template_context(stay)

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
                    # Schedule the reminder task asynchronously
                    schedule_checkout_extension_reminder.delay(stay.id, is_test_reminder)

                    # Schedule meal reminders if both hotel setting is true AND request has it true
                    breakfast_enabled = stay.hotel.breakfast_reminder and stay.breakfast_reminder
                    dinner_enabled = stay.hotel.dinner_reminder and stay.dinner_reminder

                    if breakfast_enabled or dinner_enabled:
                        schedule_meal_reminders.delay(stay.id)

                # Check for guest flags before completing check-in
                from flag_system.serializers import GuestFlagSummarySerializer, GuestFlagResponseSerializer
                
                flag_summary = get_flag_summary_for_guest(stay.guest.id)
                
                response_data = {
                    'stay_id': stay.id,
                    'register_number': stay.register_number,
                    'check_out_date': stay.check_out_date,
                    'message': 'Check-in verified and activated successfully'
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

    def _build_checkin_template_context(self, stay):
        """
        Build additional template context for check-in confirmation templates.
        """
        wifi_credential = self._get_wifi_credentials_for_stay(stay)
        checkin_dt = stay.actual_check_in or stay.check_in_date
        checkout_dt = stay.check_out_date

        room_number = stay.room.room_number if stay.room else ''
        room_floor = stay.room.floor if stay.room else ''

        return {
            # WiFi variables requested for templates.
            'wifi_name': wifi_credential.network_name if wifi_credential else '',
            'wifi_password': wifi_credential.password if wifi_credential else '',
            # Time variables requested for templates.
            'checkin_time': checkin_dt.strftime('%H:%M') if checkin_dt else '',
            'checkout_time': checkout_dt.strftime('%H:%M') if checkout_dt else '',
            # Compatibility aliases that some templates may already use.
            'check_in_time': checkin_dt.strftime('%H:%M') if checkin_dt else '',
            'check_out_time': checkout_dt.strftime('%H:%M') if checkout_dt else '',
            # Explicit room fallbacks for template edge cases.
            'room_number': room_number,
            'room_floor': room_floor,
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
        List all checked-in users (active stays)
        """
        stays = self.get_queryset().filter(status='active').order_by('-actual_check_in')
        serializer = StayListSerializer(stays, many=True)
        return success_response(data=serializer.data)

    @action(detail=True, methods=['post'], url_path='checkout')
    def checkout_user(self, request, pk=None):
        """
        Check out a guest by changing stay status to checked-out
        Also updates guest status and room status to cleaning
        Automatically initiates feedback flow
        Accepts optional internal_rating and internal_note for staff use
        """
        try:
            stay = self.get_object()
        except Exception:
            return not_found_response("Stay not found")

        # Set to True for debugging WhatsApp messages without changing status
        # Set to False for normal operation
        debug = False

        # Validate optional checkout data
        from .serializers import CheckoutSerializer
        checkout_serializer = CheckoutSerializer(data=request.data)
        checkout_serializer.is_valid(raise_exception=True)

        if stay.status != 'active':
            return error_response(
                f'Stay is not active. Current status: {stay.status}',
                status=status.HTTP_400_BAD_REQUEST
            )

        if debug:
            logger.info(f"DEBUG MODE: Skipping status changes for stay {stay.id} - guest {stay.guest.full_name}")

        try:
            with transaction.atomic():
                if debug is not True:
                    logger.info(f"Updating status for stay {stay.id} - guest {stay.guest.full_name}")
                    checkout_at = timezone.now()

                    amount_paid = checkout_serializer.validated_data.get('amount_paid')
                    if amount_paid is None:
                        amount_paid = self._calculate_checkout_amount(stay, checkout_at)

                    # Persist amount against this stay.
                    stay.total_amount = amount_paid

                    # Update stay status
                    stay.status = 'completed'
                    stay.actual_check_out = checkout_at
                    
                    # Update optional internal rating and note if provided
                    if 'internal_rating' in checkout_serializer.validated_data:
                        stay.internal_rating = checkout_serializer.validated_data['internal_rating']
                    if 'internal_note' in checkout_serializer.validated_data:
                        stay.internal_note = checkout_serializer.validated_data['internal_note']
                    
                    stay.save()

                    # Keep booking.total_amount in sync as the sum of associated stay totals.
                    if stay.booking:
                        booking_total = (
                            stay.booking.stays.aggregate(total=Sum('total_amount')).get('total')
                            or Decimal('0.00')
                        )
                        stay.booking.total_amount = booking_total
                        stay.booking.save(update_fields=['total_amount'])

                    # Create flag if flag_user is true
                    if checkout_serializer.validated_data.get('flag_user', False):
                        
                        # Check if there's already an active flag for this guest from this hotel
                        existing_flag = GuestFlag.objects.filter(
                            guest=stay.guest,
                            stay__hotel=stay.hotel,
                            is_active=True
                        ).first()
                        
                        if not existing_flag:
                            # Use the internal_note for both internal_reason and global_note
                            flag_note = stay.internal_note or "Flagged during checkout"
                            flag = create_guest_flag(
                                guest_id=stay.guest.id,
                                stay_id=stay.id,
                                internal_reason=flag_note,  # Use the internal note as reason
                                global_note=flag_note,       # Also use as global note
                                flagged_by_police=False,
                                user=request.user
                            )
                            logger.info(f"Created flag for guest {stay.guest.full_name} at checkout with note: {flag_note}")

                    # Update guest status
                    stay.guest.status = 'checked_out'
                    stay.guest.save()

                    # Update room status to cleaning
                    if stay.room:
                        stay.room.status = 'cleaning'
                        stay.room.current_guest = None
                        stay.room.save()
                else:
                    logger.info(f"DEBUG MODE: Status changes skipped - stay.status={stay.status}, guest.status={stay.guest.status}, room.status={stay.room.status if stay.room else 'No room'}")

                # Close all existing conversations for this guest before sending checkout message
                from chat.models import Conversation
                closed_conversations_count = Conversation.objects.filter(
                    guest=stay.guest,
                    hotel=stay.hotel,
                    status='active'
                ).update(status='closed')
                
                logger.info(f"Closed {closed_conversations_count} active conversations for guest {stay.guest.full_name} before checkout")

                # Send checkout thank-you template message
                if stay.guest.whatsapp_number:
                    try:
                        template_context = self._build_checkout_template_context(stay)
                        template_result = process_template(
                            hotel_id=stay.hotel.id,
                            template_name='lobbybee_checkout_thank_you',
                            guest_id=stay.guest.id,
                            additional_context=template_context
                        )

                        if template_result.get('success'):
                            checkout_message = template_result.get('processed_content', '')
                            checkout_media_url = template_result.get('media_url')

                            if checkout_media_url:
                                send_whatsapp_image_with_link(
                                    recipient_number=stay.guest.whatsapp_number,
                                    image_url=checkout_media_url,
                                    caption=checkout_message
                                )
                            elif checkout_message:
                                send_whatsapp_text_message(
                                    recipient_number=stay.guest.whatsapp_number,
                                    message_text=checkout_message
                                )
                        else:
                            logger.warning(
                                f"Checkout template processing failed for stay {stay.id}: "
                                f"{template_result.get('error', 'Unknown error')}"
                            )
                    except Exception as template_err:
                        logger.error(
                            f"Failed to send checkout thank-you template for stay {stay.id}: {template_err}",
                            exc_info=True
                        )

                # Initiate feedback flow automatically
                from .models import Feedback
                from chat.models import Conversation

                # Check if feedback already exists
                if not Feedback.objects.filter(stay=stay).exists():
                    # Archive any existing active feedback conversations for this guest
                    Conversation.objects.filter(
                        guest=stay.guest,
                        hotel=stay.hotel,
                        conversation_type='feedback',
                        status='active'
                    ).update(status='archived')

                    # Create new feedback conversation
                    conversation = Conversation.objects.create(
                        guest=stay.guest,
                        hotel=stay.hotel,
                        department='Reception',
                        conversation_type='feedback',
                        status='active'
                    )

                    # Send initial feedback list message manually
                    header_text = f"How was your stay at {stay.hotel.name}?"
                    body_text = f"""Thank you for staying with us at {stay.hotel.name}!

We hope you had a wonderful experience and your stay was comfortable. Your feedback helps us improve our service and ensure we continue to provide exceptional hospitality.

Please take a moment to rate your overall experience from 1 to 5 stars. We truly appreciate your time and feedback!"""

                    rating_options = [
                        {"id": "rating_1", "title": "⭐ Poor"},
                        {"id": "rating_2", "title": "⭐⭐ Fair"},
                        {"id": "rating_3", "title": "⭐⭐⭐ Good"},
                        {"id": "rating_4", "title": "⭐⭐⭐⭐ Very Good"},
                        {"id": "rating_5", "title": "⭐⭐⭐⭐⭐ Excellent"}
                    ]

                    try:
                        # Save the system message to conversation FIRST (like in feedback_flow.py)
                        from chat.flows.feedback_flow import save_system_message, FeedbackStep
                        save_system_message(
                            conversation,
                            f"{header_text}\n\n{body_text}",
                            FeedbackStep.RATING
                        )

                        # Then send the WhatsApp message
                        send_whatsapp_list_message(
                            recipient_number=stay.guest.whatsapp_number,
                            header_text=header_text,
                            body_text=body_text,
                            options=rating_options
                        )
                        logger.info(f"Feedback list message sent to guest {stay.guest.full_name} ({stay.guest.whatsapp_number})")
                    except Exception as e:
                        logger.error(f"Failed to send feedback list message: {e}")
                        # Continue with checkout even if WhatsApp message fails

                response_data = {
                    'stay_id': stay.id,
                    'message': 'Guest checked out successfully',
                    'total_amount': str(stay.total_amount)
                }
                
                # Include internal rating and note in response if they were set
                if stay.internal_rating is not None:
                    response_data['internal_rating'] = stay.internal_rating
                if stay.internal_note:
                    response_data['internal_note'] = stay.internal_note
                    
                return success_response(data=response_data)

        except Exception as e:
            logger.error(f"Error checking out guest: {str(e)}")
            return error_response(
                f'Failed to check out guest: {str(e)}',
                status=status.HTTP_400_BAD_REQUEST
            )

    def _calculate_checkout_amount(self, stay, checkout_at):
        """
        Fallback checkout billing when frontend amount is not provided.
        Uses room category base rate * number of stay days (minimum 1 day).
        """
        if not stay.room or not stay.room.category or stay.room.category.base_price is None:
            return Decimal('0.00')

        start_time = stay.actual_check_in or stay.check_in_date
        if not start_time:
            return Decimal('0.00')

        total_seconds = (checkout_at - start_time).total_seconds()
        days = max(1, math.ceil(max(total_seconds, 0) / (24 * 3600)))
        return Decimal(stay.room.category.base_price) * Decimal(days)

    def _build_checkout_template_context(self, stay):
        """
        Build additional template context for checkout thank-you templates.
        """
        checkin_dt = stay.actual_check_in or stay.check_in_date
        checkout_dt = stay.actual_check_out or timezone.now()
        room_number = stay.room.room_number if stay.room else ''

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
            'checkin_time': checkin_dt.strftime('%H:%M') if checkin_dt else '',
            'checkout_time': checkout_dt.strftime('%H:%M') if checkout_dt else '',
            'room_number': room_number,
            'stay_duration': stay_duration,
            # Compatibility aliases if template uses underscore style keys.
            'check_in_time': checkin_dt.strftime('%H:%M') if checkin_dt else '',
            'check_out_time': checkout_dt.strftime('%H:%M') if checkout_dt else '',
        }

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

                # Re-schedule checkout extension reminder based on new checkout time
                from .tasks import schedule_checkout_extension_reminder
                schedule_checkout_extension_reminder.delay(stay.id)

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
