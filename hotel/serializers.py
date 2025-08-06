from rest_framework import serializers
from .models import Hotel, HotelDocument

class HotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = '__all__'
        read_only_fields = ('status', 'is_verified', 'verified_at')

class UserHotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        exclude = ('status', 'verified_by', 'verified_at', 'invited_by')

class HotelDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelDocument
        fields = '__all__'
        read_only_fields = ('hotel',)
