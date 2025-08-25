from rest_framework import serializers
from .models import User
from hotel.models import Hotel
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        data = super().validate(attrs)
        user_data = UserSerializer(self.user).data
        if self.user.user_type in ['hotel_admin', 'manager', 'receptionist'] and self.user.hotel:
            user_data['hotel_id'] = str(self.user.hotel.id)
        data['user'] = user_data
        return data


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False) # Make password optional for updates

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'user_type', 'phone_number', 'password', 'hotel', 'created_by', 'is_active_hotel_user']
        read_only_fields = ['hotel', 'created_by', 'is_active_hotel_user'] # These fields are set by the system, not directly by the user

    def create(self, validated_data):
        # For staff creation, hotel and created_by are passed directly to serializer.save()
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            user_type=validated_data.get('user_type'),
            phone_number=validated_data.get('phone_number', ''),
            hotel=validated_data.get('hotel'), # Added hotel
            created_by=validated_data.get('created_by'), # Added created_by
            is_active_hotel_user=validated_data.get('is_active_hotel_user', True) # Added is_active_hotel_user
        )
        return user

    def update(self, instance, validated_data):
        # Handle password update separately
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
