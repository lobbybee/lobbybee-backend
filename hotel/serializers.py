from rest_framework import serializers
from django.db import models
from .models import Hotel, HotelDocument, Room, RoomCategory, PaymentQRCode, WiFiCredential
from user.serializers import UserSerializer

class HotelDocumentSerializer(serializers.ModelSerializer):
    document_file_url = serializers.SerializerMethodField()

    class Meta:
        model = HotelDocument
        fields = ('id', 'hotel', 'document_type', 'document_file', 'document_file_url', 'uploaded_at')
        read_only_fields = ('hotel',)
        extra_kwargs = {
            'document_file': {'write_only': True}
        }

    def get_document_file_url(self, obj):
        if obj.document_file:
            return obj.document_file.url
        return None

class HotelSerializer(serializers.ModelSerializer):
    admin = serializers.SerializerMethodField()
    documents = HotelDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Hotel
        fields = [
            'id', 'name', 'description', 'address', 'city', 'state', 'country',
            'pincode', 'phone', 'email', 'google_review_link', 'latitude',
            'longitude', 'qr_code_url', 'unique_qr_code',
            'check_in_time', 'time_zone', 'breakfast_reminder', 'dinner_reminder',
            'status', 'is_verified', 'is_active',
            'is_demo', 'verification_notes', 'registration_date', 'verified_at',
            'updated_at', 'admin', 'documents'
        ]
        read_only_fields = ('status', 'is_verified', 'verified_at')

    def get_admin(self, obj):
        admin_user = obj.get_admin()
        if admin_user:
            return UserSerializer(admin_user).data
        return None

class UserHotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        exclude = ('status', 'verified_at')


class AdminHotelUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for platform admins to update hotel details.
    Excludes system-managed fields and read-only fields.
    """
    class Meta:
        model = Hotel
        fields = [
            'name', 'description', 'address', 'city', 'state', 'country',
            'pincode', 'phone', 'email', 'google_review_link', 'latitude',
            'longitude', 'qr_code_url', 'check_in_time', 'time_zone',
            'breakfast_reminder', 'dinner_reminder'
        ]


class AdminHotelDocumentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for platform admins to update hotel documents.
    """
    document_file_url = serializers.SerializerMethodField()

    class Meta:
        model = HotelDocument
        fields = ('id', 'hotel', 'document_type', 'document_file', 'document_file_url', 'uploaded_at')
        read_only_fields = ('hotel', 'uploaded_at')
        extra_kwargs = {
            'document_file': {'write_only': True, 'required': False}
        }

    def get_document_file_url(self, obj):
        if obj.document_file:
            return obj.document_file.url
        return None


class RoomCategorySerializer(serializers.ModelSerializer):
    room_count = serializers.ReadOnlyField()

    class Meta:
        model = RoomCategory
        fields = '__all__'
        read_only_fields = ('hotel',)


class RoomSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display_name')

    class Meta:
        model = Room
        fields = '__all__'
        read_only_fields = ('hotel',)

    def to_representation(self, instance):
        from guest.serializers import GuestSerializer
        representation = super().to_representation(instance)
        if instance.category:
            representation['category'] = {
                'id': instance.category.id,
                'name': instance.category.name
            }
        if instance.current_guest:
            representation['current_guest'] = GuestSerializer(instance.current_guest).data
        return representation


class RoomStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ('status',)




class BulkCreateRoomSerializer(serializers.Serializer):
    category = serializers.IntegerField()
    floor = serializers.IntegerField()
    start_number = serializers.CharField(max_length=10)
    end_number = serializers.CharField(max_length=10)

    def validate_category(self, value):
        request = self.context.get('request')
        try:
            category = RoomCategory.objects.get(pk=value, hotel=request.user.hotel)
        except RoomCategory.DoesNotExist:
            raise serializers.ValidationError("RoomCategory not found for this hotel.")
        return category


class PaymentQRCodeSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PaymentQRCode
        fields = ('id', 'hotel', 'name', 'image', 'image_url', 'upi_id', 'active', 'created_at', 'updated_at')
        read_only_fields = ('hotel', 'created_at', 'updated_at')
        extra_kwargs = {
            'image': {'write_only': True}
        }

    def get_image_url(self, obj):
        """
        Generate the full URL for the QR code image.
        Compatible with both local storage and S3.
        """
        return obj.get_image_url()

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['hotel'] = request.user.hotel
        return super().create(validated_data)


class WiFiCredentialSerializer(serializers.ModelSerializer):
    room_category_name = serializers.CharField(source='room_category.name', read_only=True)

    class Meta:
        model = WiFiCredential
        fields = (
            'id', 'hotel', 'floor', 'room_category', 'room_category_name', 
            'network_name', 'password', 'is_active', 'created_at', 'updated_at'
        )
        read_only_fields = ('hotel', 'created_at', 'updated_at')

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['hotel'] = request.user.hotel
        return super().create(validated_data)

    def validate(self, data):
        """
        Validate that the floor exists and no duplicate credentials exist for the same floor and room category.
        """
        request = self.context.get('request')
        hotel = request.user.hotel
        
        # Check if the floor exists in the hotel
        floor_exists = Room.objects.filter(hotel=hotel, floor=data['floor']).exists()
        if not floor_exists:
            raise serializers.ValidationError(
                f"Floor {data['floor']} does not exist in this hotel. Please create rooms on this floor first."
            )
        
        existing = WiFiCredential.objects.filter(
            hotel=hotel,
            floor=data['floor'],
            room_category=data.get('room_category')
        ).exclude(id=self.instance.id if self.instance else None)
        
        if existing.exists():
            if data.get('room_category'):
                raise serializers.ValidationError(
                    f"WiFi credentials already exist for floor {data['floor']} and room category {data['room_category'].name}"
                )
            else:
                raise serializers.ValidationError(
                    f"WiFi credentials already exist for floor {data['floor']} (all categories)"
                )
        
        return data


class RoomWiFiCredentialSerializer(serializers.ModelSerializer):
    """
    Serializer to get WiFi credentials for a specific room.
    Returns the most specific credentials available for the room.
    """
    wifi_credentials = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ('id', 'room_number', 'floor', 'category', 'wifi_credentials')

    def get_wifi_credentials(self, obj):
        # Get the most specific WiFi credentials for this room
        credential = WiFiCredential.objects.filter(
            hotel=obj.hotel,
            floor=obj.floor,
            is_active=True
        ).filter(
            models.Q(room_category=obj.category) | models.Q(room_category__isnull=True)
        ).order_by('-room_category__id').first()  # Prefer room-specific credentials

        if credential:
            return {
                'network_name': credential.network_name,
                'password': credential.password,
                'floor': credential.floor,
                'room_category': credential.room_category.name if credential.room_category else 'All categories'
            }
        return None
