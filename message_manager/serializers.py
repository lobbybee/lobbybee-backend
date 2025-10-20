from rest_framework import serializers
from .models import Conversation, Message
from user.models import User


class ConversationListSerializer(serializers.ModelSerializer):
    guest_name = serializers.SerializerMethodField()
    room_number = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    stay_id = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'stay_id', 'guest_name', 'room_number', 'status', 'last_message', 'updated_at']

    def get_guest_name(self, obj):
        if obj.stay and obj.stay.guest:
            return obj.stay.guest.full_name
        return "Demo Guest"

    def get_room_number(self, obj):
        if obj.stay and obj.stay.room:
            return obj.stay.room.room_number
        return "N/A"

    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return {
                'content': last_message.content[:100],
                'timestamp': last_message.timestamp,
                'sender_type': last_message.sender_type
            }
        return None

    def get_stay_id(self, obj):
        return obj.stay.id if obj.stay else None


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'content', 'sender_type', 'sender_name', 'timestamp']

    def get_sender_name(self, obj):
        if obj.staff_sender:
            return obj.staff_sender.get_full_name()
        elif obj.sender_type == 'guest':
            if obj.conversation.stay and obj.conversation.stay.guest:
                return obj.conversation.stay.guest.full_name
            return "Guest"
        return "System"


class ConversationDetailSerializer(serializers.ModelSerializer):
    guest_name = serializers.SerializerMethodField()
    room_number = serializers.SerializerMethodField()
    guest_phone = serializers.SerializerMethodField()
    stay_id = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'stay_id', 'guest_name', 'room_number', 'guest_phone', 'status', 'context_data', 'created_at', 'updated_at']

    def get_guest_name(self, obj):
        if obj.stay and obj.stay.guest:
            return obj.stay.guest.full_name
        return "Demo Guest"

    def get_room_number(self, obj):
        if obj.stay and obj.stay.room:
            return obj.stay.room.room_number
        return "N/A"

    def get_guest_phone(self, obj):
        if obj.stay and obj.stay.guest:
            return obj.stay.guest.whatsapp_number
        return "N/A"

    def get_stay_id(self, obj):
        return obj.stay.id if obj.stay else None


class CreateMessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1000)
    
    def validate_text(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message text cannot be empty")
        return value
