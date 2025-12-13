from rest_framework import serializers
from django.shortcuts import get_object_or_404
from .models import GuestFlag
from guest.models import Guest, Stay


class GuestFlagSerializer(serializers.ModelSerializer):
    """
    Serializer for creating guest flags
    """
    guest_id = serializers.IntegerField(write_only=True)
    stay_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = GuestFlag
        fields = [
            'guest_id', 'stay_id', 'internal_reason', 'global_note', 'flagged_by_police'
        ]
    
    def validate(self, attrs):
        request = self.context['request']
        user = request.user
        
        # Hotel staff must provide stay_id
        if user.user_type in ['hotel_admin', 'manager', 'receptionist']:
            if not attrs.get('stay_id'):
                raise serializers.ValidationError(
                    "Hotel staff must provide a stay_id when flagging a guest"
                )
            
            # Verify the stay belongs to the user's hotel
            stay = get_object_or_404(Stay, id=attrs['stay_id'])
            if stay.hotel != user.hotel:
                raise serializers.ValidationError(
                    "You can only flag guests from your own hotel"
                )
        
        # Only platform staff can set flagged_by_police
        if attrs.get('flagged_by_police') and user.user_type not in ['platform_admin', 'platform_staff']:
            raise serializers.ValidationError(
                "Only platform staff can set flagged_by_police"
            )
        
        return attrs
    
    def create(self, validated_data):
        request = self.context['request']
        validated_data['last_modified_by'] = request.user
        
        # Auto-set guest from stay if stay_id is provided
        if validated_data.get('stay_id'):
            stay = Stay.objects.get(id=validated_data['stay_id'])
            validated_data['guest_id'] = stay.guest.id
        
        return super().create(validated_data)


class GuestFlagResponseSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for flag response data - for hotel staff use
    """
    source = serializers.SerializerMethodField()
    flagged_by = serializers.CharField(source='last_modified_by.get_full_name', read_only=True)
    flagged_date = serializers.DateTimeField(source='created_at', read_only=True)
    hotel_name = serializers.SerializerMethodField()
    internal_rating = serializers.IntegerField(source='stay.internal_rating', read_only=True)
    
    class Meta:
        model = GuestFlag
        fields = [
            'id', 'global_note', 'flagged_by_police', 'source',
            'flagged_by', 'flagged_date', 'hotel_name', 'internal_rating'
        ]
    
    def get_source(self, obj):
        """Returns who flagged the guest"""
        if obj.flagged_by_police:
            return "Police"
        elif obj.stay:
            return obj.stay.hotel.name
        else:
            return "Platform"
    
    def get_hotel_name(self, obj):
        """Returns hotel name only if flagged by hotel staff"""
        return obj.stay.hotel.name if obj.stay else None


class GuestFlagSummarySerializer(serializers.Serializer):
    """
    Simplified flag summary for check-in
    """
    is_flagged = serializers.BooleanField()
    police_flagged = serializers.BooleanField()
    flags = GuestFlagResponseSerializer(many=True)


class ResetFlagSerializer(serializers.Serializer):
    """
    Serializer for resetting a flag
    """
    reset_reason = serializers.CharField(required=True, help_text="Reason for resetting the flag")