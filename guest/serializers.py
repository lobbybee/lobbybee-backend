from rest_framework import serializers
from .models import Guest, GuestIdentityDocument, Stay


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = [
            "id",
            "full_name",
            "email",
            "whatsapp_number",
            "nationality",
            "status",
        ]


class StaySerializer(serializers.ModelSerializer):
    guest = GuestSerializer(read_only=True)

    class Meta:
        model = Stay
        fields = "__all__"
        read_only_fields = ("hotel",)

    def to_representation(self, instance):
        from hotel.serializers import RoomSerializer

        representation = super().to_representation(instance)
        representation["room"] = RoomSerializer(instance.room).data
        return representation


class GuestIdentityDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestIdentityDocument
        fields = "__all__"
        read_only_fields = ("guest", "verified_by")


class CheckInSerializer(serializers.Serializer):
    stay_id = serializers.IntegerField()


class CheckOutSerializer(serializers.Serializer):
    stay_id = serializers.IntegerField()
