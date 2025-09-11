from rest_framework import serializers
from .models import SubscriptionPlan, Transaction, HotelSubscription
from hotel.models import Hotel
from hotel.serializers import HotelSerializer


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class TransactionSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    
    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'hotel_name', 'plan_name')


class HotelSubscriptionSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = HotelSubscription
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'hotel_name', 'plan_name', 'is_expired', 'days_until_expiry')


class HotelSubscriptionDetailSerializer(serializers.ModelSerializer):
    hotel = HotelSerializer(read_only=True)
    plan = SubscriptionPlanSerializer(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = HotelSubscription
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'is_expired', 'days_until_expiry')


class SubscribeToPlanSerializer(serializers.Serializer):
    plan = serializers.UUIDField()
    
    def validate_plan(self, value):
        try:
            SubscriptionPlan.objects.get(id=value)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Plan not found")
        return value


class ProcessPaymentSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    payment_details = serializers.DictField(required=False)