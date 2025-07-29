from rest_framework import serializers
from .models import User
from hotel.models import Hotel

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    hotel_name = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'user_type', 'phone_number', 'password', 'hotel_name']

    def create(self, validated_data):
        hotel_name = validated_data.pop('hotel_name', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            user_type=validated_data.get('user_type'),
            phone_number=validated_data.get('phone_number', '')
        )
        if hotel_name:
            hotel = Hotel.objects.create(name=hotel_name, email=user.email)
            user.hotel = hotel
            user.save()
        return user
