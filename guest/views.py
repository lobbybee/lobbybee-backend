from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
import threading

from .models import Guest, GuestIdentityDocument, Stay, Booking
from .serializers import (
    CreateGuestSerializer, CheckinOfflineSerializer, VerifyCheckinSerializer,
    StayListSerializer, BookingListSerializer, GuestResponseSerializer
)
from hotel.models import Hotel, Room
from hotel.permissions import IsHotelStaff, IsSameHotelUser
from .permissions import CanManageGuests, CanViewAndManageStays
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

                return Response({
                    'primary_guest_id': primary_guest.id,
                    'accompanying_guest_ids': accompanying_guest_ids,
                    'message': 'Guests created successfully'
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating guests: {str(e)}")
            return Response(
                {'error': f'Failed to create guests: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='guests')
    def list_guests(self, request):
        """
        List all guests for the hotel with optional search functionality
        Query parameters:
        - search: Search term to filter guests by name or phone number
        """
        queryset = self.get_queryset()
        search_term = request.query_params.get('search', None)

        if search_term:
            queryset = queryset.filter(
                Q(full_name__icontains=search_term) |
                Q(whatsapp_number__icontains=search_term)
            )

        serializer = GuestResponseSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='bookings')
    def list_bookings(self, request):
        """
        List all bookings for the hotel
        """
        bookings = Booking.objects.filter(hotel=request.user.hotel)
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)


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
                        documents_uploaded=True
                    )
                    stays.append(stay)

                    # Update room status to occupied
                    room.status = 'occupied'
                    room.current_guest = primary_guest
                    room.save()

                return Response({
                    'booking_id': booking.id,
                    'stay_ids': [stay.id for stay in stays],
                    'message': 'Check-in created successfully. Pending verification.'
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating check-in: {str(e)}")
            return Response(
                {'error': f'Failed to create check-in: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['patch'], url_path='verify-checkin')
    def verify_checkin(self, request, pk=None):
        """
        Verify and activate a stay. Updates register number and marks as checked in.
        Can optionally update room assignment and checkout date.
        """
        stay = self.get_object()

        if stay.status != 'pending':
            return Response(
                {'error': f'Stay is not pending. Current status: {stay.status}'},
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
                            # Process the welcome template with complete guest context
                            template_result = process_template(
                                hotel_id=stay.hotel.id,
                                template_name='lobbybee_hotel_welcome',
                                guest_id=stay.guest.id
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

                return Response({
                    'stay_id': stay.id,
                    'register_number': stay.register_number,
                    'check_out_date': stay.check_out_date,
                    'message': 'Check-in verified and activated successfully'
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error verifying check-in: {str(e)}")
            return Response(
                {'error': f'Failed to verify check-in: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='pending-stays')
    def pending_stays(self, request):
        """
        List all stays that are pending verification
        """
        stays = self.get_queryset().filter(status='pending').order_by('-created_at')
        serializer = StayListSerializer(stays, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='checked-in-users')
    def checked_in_users(self, request):
        """
        List all checked-in users (active stays)
        """
        stays = self.get_queryset().filter(status='active').order_by('-actual_check_in')
        serializer = StayListSerializer(stays, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='checkout')
    def checkout_user(self, request, pk=None):
        """
        Check out a guest by changing stay status to checked-out
        Also updates guest status and room status to cleaning
        Automatically initiates feedback flow
        Accepts optional internal_rating and internal_note for staff use
        """
        # Set to True for debugging WhatsApp messages without changing status
        # Set to False for normal operation
        debug = False

        stay = self.get_object()

        # Validate optional checkout data
        from .serializers import CheckoutSerializer
        checkout_serializer = CheckoutSerializer(data=request.data)
        checkout_serializer.is_valid(raise_exception=True)

        if stay.status != 'active':
            return Response(
                {'error': f'Stay is not active. Current status: {stay.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if debug:
            logger.info(f"DEBUG MODE: Skipping status changes for stay {stay.id} - guest {stay.guest.full_name}")

        try:
            with transaction.atomic():
                if debug is not True:
                    logger.info(f"Updating status for stay {stay.id} - guest {stay.guest.full_name}")
                    # Update stay status
                    stay.status = 'completed'
                    stay.actual_check_out = timezone.now()
                    
                    # Update optional internal rating and note if provided
                    if 'internal_rating' in checkout_serializer.validated_data:
                        stay.internal_rating = checkout_serializer.validated_data['internal_rating']
                    if 'internal_note' in checkout_serializer.validated_data:
                        stay.internal_note = checkout_serializer.validated_data['internal_note']
                    
                    stay.save()

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
                    'message': 'Guest checked out successfully'
                }
                
                # Include internal rating and note in response if they were set
                if stay.internal_rating is not None:
                    response_data['internal_rating'] = stay.internal_rating
                if stay.internal_note:
                    response_data['internal_note'] = stay.internal_note
                    
                return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error checking out guest: {str(e)}")
            return Response(
                {'error': f'Failed to check out guest: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'], url_path='reject-checkin')
    def reject_checkin(self, request, pk=None):
        """
        Reject a pending checkin request.
        Cleans up all pending data and notifies the guest via WhatsApp.
        """
        stay = self.get_object()

        if stay.status not in ['pending']:
            return Response(
                {'error': f'Can only reject pending checkins. Current status: {stay.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                guest = stay.guest
                
                # Clean up all pending stays and bookings for this guest (both new and returning guests)
                from chat.flows.checkin_flow import cleanup_incomplete_guest_data, cleanup_incomplete_guest_data_preserve_personal_info
                
                # Check if guest has completed stays before (returning guest)
                from guest.models import Stay as GuestStay
                has_completed_stays = GuestStay.objects.filter(
                    guest=guest,
                    status='completed'
                ).exists()
                
                if has_completed_stays:
                    # Returning guest - preserve personal info but clean up pending attempts
                    cleanup_incomplete_guest_data_preserve_personal_info(guest)
                else:
                    # New guest - clean up everything
                    cleanup_incomplete_guest_data(guest)
                
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

                return Response({
                    'guest_id': guest.id,
                    'guest_name': guest.full_name,
                    'whatsapp_number': guest.whatsapp_number,
                    'message': 'Checkin rejected and guest notified successfully'
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error rejecting checkin: {str(e)}")
            return Response(
                {'error': f'Failed to reject checkin: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
