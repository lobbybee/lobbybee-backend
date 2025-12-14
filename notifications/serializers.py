from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    group_type_display = serializers.CharField(source='get_group_type_display', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'group_type', 'group_type_display', 'hotel', 
            'title', 'message', 'link', 'link_label', 'is_read', 'created_at'
        ]
        extra_kwargs = {
            'user': {'required': False},
            'group_type': {'required': False},
            'hotel': {'required': False},
        }


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications with validation"""
    
    class Meta:
        model = Notification
        fields = [
            'user', 'group_type', 'title', 'message', 
            'link', 'link_label'
        ]
        extra_kwargs = {
            'hotel': {'read_only': True}  # Hotel will be set automatically in view
        }
    
    def validate(self, data):
        """
        Validate that either user or group_type is provided
        """
        user = data.get('user')
        group_type = data.get('group_type')
        
        # Either user or group_type must be provided
        if not user and not group_type:
            raise serializers.ValidationError(
                "Either 'user' or 'group_type' must be provided"
            )
        
        # Cannot provide both user and group_type
        if user and group_type:
            raise serializers.ValidationError(
                "Cannot specify both 'user' and 'group_type'. Use one or the other."
            )
        
        # If creating hotel staff notification, user must have hotel
        if group_type == 'hotel_staff':
            # Hotel will be validated in the view based on the authenticated user
            pass
        
        return data