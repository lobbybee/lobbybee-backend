from rest_framework import serializers
from .models import Guest, GuestIdentityDocument, Stay, Booking
from django.db import transaction
from hotel.models import Room
import logging
import json

logger = logging.getLogger(__name__)


class JSONField(serializers.Field):
    """
    Custom field that accepts both JSON strings and Python objects.
    Parses strings to Python objects before validation.
    """
    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid JSON format")
        return data
    
    def to_representation(self, value):
        return value


class AccompanyingGuestSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    documents = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )
    document_type = serializers.ChoiceField(
        choices=GuestIdentityDocument.DOCUMENT_TYPES,
        write_only=True,
        required=False
    )

class DocumentUploadSerializer(serializers.Serializer):
    document_file = serializers.FileField()
    document_file_back = serializers.FileField(required=False)
    document_type = serializers.ChoiceField(choices=GuestIdentityDocument.DOCUMENT_TYPES)
    document_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(default=False)

class CreateGuestSerializer(serializers.Serializer):
    primary_guest = JSONField()
    accompanying_guests = JSONField(required=False)
    
    def validate_primary_guest(self, value):
        required_fields = ['full_name', 'whatsapp_number']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"'{field}' is required in primary_guest")
        return value
    
    def validate_accompanying_guests(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("accompanying_guests must be a list")
        
        # Validate each accompanying guest using the serializer
        serializer = AccompanyingGuestSerializer(data=value, many=True)
        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)
        
        return value

class CheckinOfflineSerializer(serializers.Serializer):
    primary_guest_id = serializers.IntegerField()
    room_ids = serializers.ListField(child=serializers.IntegerField())
    check_in_date = serializers.DateTimeField()
    check_out_date = serializers.DateTimeField()
    guest_names = serializers.ListField(child=serializers.CharField(), required=False)
    hours_24 = serializers.BooleanField(default=False, help_text="Indicates if this is a 24-hour stay")

class VerifyCheckinSerializer(serializers.Serializer):
    register_number = serializers.CharField(required=False, allow_blank=True)
    room_id = serializers.IntegerField(required=False)
    guest_updates = serializers.DictField(required=False)
    check_out_date = serializers.DateTimeField(required=False)
    breakfast_reminder = serializers.BooleanField(
        default=False,
        help_text="Enable breakfast reminders for this stay"
    )
    dinner_reminder = serializers.BooleanField(
        default=False,
        help_text="Enable dinner reminders for this stay"
    )
    # Document verification fields
    verified_document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of document IDs to mark as verified"
    )
    verify_all_documents = serializers.BooleanField(
        default=False,
        help_text="If True, marks all guest documents as verified"
    )

class CheckoutSerializer(serializers.Serializer):
    internal_rating = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=5,
        help_text="Internal rating from 1 to 5 (optional)"
    )
    internal_note = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Internal notes about the guest stay (optional)"
    )
    flag_user = serializers.BooleanField(
        default=False,
        help_text="Flag this guest for future reference"
    )
    
    def validate(self, attrs):
        if attrs.get('flag_user', False) and not attrs.get('internal_note'):
            raise serializers.ValidationError(
                "Internal note is required when flagging a guest"
            )
        return attrs

class ExtendStaySerializer(serializers.Serializer):
    check_out_date = serializers.DateTimeField(
        required=True,
        help_text="New checkout date and time for extending the stay"
    )
    
    def validate_check_out_date(self, value):
        """
        Validate that the new checkout date is in the future
        """
        from django.utils import timezone
        if value <= timezone.now():
            raise serializers.ValidationError(
                "New checkout date must be in the future"
            )
        return value

# Response serializers
class GuestResponseSerializer(serializers.ModelSerializer):
    documents = serializers.SerializerMethodField()
    
    class Meta:
        model = Guest
        fields = [
            "id", "whatsapp_number", "full_name", "email", 
            "status", "is_primary_guest", "documents", "nationality",
            "register_number", "date_of_birth", "preferred_language",
            "is_whatsapp_active", "loyalty_points", "notes"
        ]
    
    def get_documents(self, obj):
        docs = obj.identity_documents.filter(is_accompanying_guest=False)
        return [{
            "id": doc.id,
            "document_type": doc.document_type,
            "document_number": doc.document_number,
            "is_verified": doc.is_verified,
            "document_file_url": doc.document_file.url if doc.document_file else None,
            "document_file_back_url": doc.document_file_back.url if doc.document_file_back else None,
        } for doc in docs]

class StayListSerializer(serializers.ModelSerializer):
    guest = GuestResponseSerializer(read_only=True)
    room_details = serializers.SerializerMethodField()
    booking_details = serializers.SerializerMethodField()
    billing = serializers.SerializerMethodField()

    class Meta:
        model = Stay
        fields = [
            "id", "guest", "status", "check_in_date", "check_out_date",
            "room", "room_details", "register_number", "identity_verified", "booking_details",
            "internal_rating", "internal_note", "hours_24", "breakfast_reminder", "dinner_reminder", "billing"
        ]
    
    def get_room_details(self, obj):
        return {
            "id": obj.room.id if obj.room else None,
            "room_number": obj.room.room_number if obj.room else None,
            "floor": obj.room.floor if obj.room else None,
            "category": obj.room.category.name if obj.room and obj.room.category else None
        }
    
    def get_booking_details(self, obj):
        if obj.booking:
            return {
                "id": obj.booking.id,
                "status": obj.booking.status,
                "total_amount": obj.booking.total_amount,
                "is_via_whatsapp": obj.booking.is_via_whatsapp,
                "guest_names": obj.booking.guest_names,
                "booking_date": obj.booking.booking_date
            }
        return None

    def get_billing(self, obj):
        from .services import calculate_stay_billing
        return calculate_stay_billing(obj)

# Legacy serializers for compatibility with other parts of the codebase
class GuestSerializer(serializers.ModelSerializer):
    """Legacy GuestSerializer for backward compatibility"""
    class Meta:
        model = Guest
        fields = [
            "id",
            "whatsapp_number",
            "register_number",
            "full_name",
            "email",
            "date_of_birth",
            "nationality",
            "is_primary_guest",
            "status",
            "first_contact_date",
            "last_activity",
            "preferred_language",
            "is_whatsapp_active",
            "loyalty_points",
            "notes",
        ]

# Additional response serializers for API consistency
class BookingListSerializer(serializers.ModelSerializer):
    primary_guest = GuestResponseSerializer(read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            "id", "primary_guest", "check_in_date", "check_out_date",
            "status", "total_amount", "guest_names", "is_via_whatsapp"
        ]