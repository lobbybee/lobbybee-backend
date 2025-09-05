from rest_framework import serializers
from .models import Guest, GuestIdentityDocument, Stay, Booking
from django.db import transaction
from hotel.models import Room


class BookingSerializer(serializers.ModelSerializer):
    # This field will accept a list of room IDs for the booking
    room_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True
    )
    # Make primary_guest writable by its ID
    primary_guest = serializers.PrimaryKeyRelatedField(queryset=Guest.objects.all())

    class Meta:
        model = Booking
        fields = [
            'id', 'primary_guest', 'check_in_date', 'check_out_date',
            'guest_names', 'room_ids', 'status', 'total_amount'
        ]
        read_only_fields = ['id', 'status', 'total_amount']

    def create(self, validated_data):
        room_ids = validated_data.pop('room_ids')
        hotel = self.context['request'].user.hotel

        # Use a transaction to ensure all stays are created or none are
        with transaction.atomic():
            # Create the main booking record
            booking = Booking.objects.create(hotel=hotel, **validated_data)

            # Create a separate Stay record for each room
            for room_id in room_ids:
                try:
                    room = Room.objects.get(id=room_id, hotel=hotel)
                    Stay.objects.create(
                        booking=booking,
                        hotel=hotel,
                        guest=booking.primary_guest,
                        room=room,
                        check_in_date=booking.check_in_date,
                        check_out_date=booking.check_out_date,
                        status='pending' # Default status for a new stay
                    )
                except Room.DoesNotExist:
                    # Handle case where a room might not exist or belong to the hotel
                    raise serializers.ValidationError(f"Room with ID {room_id} not found in this hotel.")

        return booking


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = [
            "id",
            "full_name",
            "email",
            "whatsapp_number",
            "date_of_birth",
            "nationality",
            "status",
        ]


class StaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Stay
        fields = "__all__"
        read_only_fields = ("hotel",)

    def to_representation(self, instance):
        from hotel.serializers import RoomSerializer

        representation = super().to_representation(instance)
        guest_data = GuestSerializer(instance.guest).data
        guest_data['identity_documents'] = GuestIdentityDocumentSerializer(instance.guest.identity_documents.all(), many=True).data
        representation["guest"] = guest_data
        representation["room"] = RoomSerializer(instance.room).data
        return representation


class GuestIdentityDocumentSerializer(serializers.ModelSerializer):
    document_file_url = serializers.SerializerMethodField()

    class Meta:
        model = GuestIdentityDocument
        fields = "__all__"
        read_only_fields = ("guest", "verified_by")
        extra_kwargs = {
            'document_file': {'write_only': True}
        }

    def get_document_file_url(self, obj):
        if obj.document_file:
            return obj.document_file.url
        return None


class CheckInSerializer(serializers.Serializer):
    stay_id = serializers.IntegerField()


class CheckOutSerializer(serializers.Serializer):
    stay_id = serializers.IntegerField()
