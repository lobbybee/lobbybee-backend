from rest_framework import serializers
from .models import Conversation, Message
from user.models import User


class ConversationListSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source='stay.guest.full_name', read_only=True)
    room_number = serializers.CharField(source='stay.room.room_number', read_only=True)
    last_message = serializers.SerializerMethodField()
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)

    class Meta:
        model = Conversation
        fields = ['id', 'stay_id', 'guest_name', 'room_number', 'status', 'department_name', 'last_message', 'updated_at']

    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return {
                'content': last_message.content[:100],
                'timestamp': last_message.timestamp,
                'sender_type': last_message.sender_type
            }
        return None


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'content', 'sender_type', 'sender_name', 'timestamp']

    def get_sender_name(self, obj):
        if obj.staff_sender:
            return obj.staff_sender.get_full_name()
        elif obj.sender_type == 'guest':
            return obj.conversation.stay.guest.full_name if obj.conversation.stay else "Guest"
        return "System"


class ConversationDetailSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source='stay.guest.full_name', read_only=True)
    room_number = serializers.CharField(source='stay.room.room_number', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    guest_phone = serializers.CharField(source='stay.guest.whatsapp_number', read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'stay_id', 'guest_name', 'room_number', 'guest_phone', 'status', 'department_name', 'context_data', 'created_at', 'updated_at']


class CreateMessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1000)
    
    def validate_text(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message text cannot be empty")
        return value