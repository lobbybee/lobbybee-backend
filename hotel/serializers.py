from rest_framework import serializers
from .models import Hotel, HotelDocument, Room, RoomCategory, Department

class HotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = '__all__'
        read_only_fields = ('status', 'is_verified', 'verified_at')

class UserHotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        exclude = ('status', 'verified_at')

class HotelDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelDocument
        fields = '__all__'
        read_only_fields = ('hotel',)

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
