from rest_framework import serializers
from .models import Hotel, HotelDocument, Room, RoomCategory, Department
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
            'pincode', 'phone', 'email', 'latitude', 
            'longitude', 'qr_code_url', 'unique_qr_code', 'wifi_password', 
            'check_in_time', 'time_zone', 'status', 'is_verified', 'is_active', 
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
        if instance.current_guest:
            representation['current_guest'] = GuestSerializer(instance.current_guest).data
        return representation


class RoomStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ('status',)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ('hotel',)

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
