from rest_framework import serializers
from .models import Guest, GuestIdentityDocument, Stay, Booking
from django.db import transaction
from hotel.models import Room
import logging

logger = logging.getLogger(__name__)


class AccompanyingGuestSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200)
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
    primary_guest = serializers.DictField()
    accompanying_guests = AccompanyingGuestSerializer(many=True, required=False)
    
    def validate_primary_guest(self, value):
        required_fields = ['full_name', 'whatsapp_number']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"'{field}' is required in primary_guest")
        return value

class CheckinOfflineSerializer(serializers.Serializer):
    primary_guest_id = serializers.IntegerField()
    room_ids = serializers.ListField(child=serializers.IntegerField())
    check_in_date = serializers.DateTimeField()
    check_out_date = serializers.DateTimeField()
    guest_names = serializers.ListField(child=serializers.CharField(), required=False)

class VerifyCheckinSerializer(serializers.Serializer):
    register_number = serializers.CharField(required=False, allow_blank=True)
    room_id = serializers.IntegerField(required=False)
    guest_updates = serializers.DictField(required=False)

# Response serializers
class GuestResponseSerializer(serializers.ModelSerializer):
    documents = serializers.SerializerMethodField()
    
    class Meta:
        model = Guest
        fields = [
            "id", "whatsapp_number", "full_name", "email", 
            "status", "is_primary_guest", "identity_documents"
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
    
    class Meta:
        model = Stay
        fields = [
            "id", "guest", "status", "check_in_date", "check_out_date",
            "room", "room_details", "register_number", "identity_verified"
        ]
    
    def get_room_details(self, obj):
        return {
            "id": obj.room.id,
            "room_number": obj.room.room_number,
            "floor": obj.room.floor,
            "category": obj.room.category.name if obj.room.category else None
        }

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

class BookingListSerializer(serializers.ModelSerializer):
    primary_guest = GuestResponseSerializer(read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            "id", "primary_guest", "check_in_date", "check_out_date",
            "status", "total_amount", "guest_names"
        ]