from rest_framework import serializers
from django.db.models import Sum, Count, Q


class StatisticsPeriodSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class HotelStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    registered = serializers.IntegerField()
    verified = serializers.IntegerField()
    unverified = serializers.IntegerField()
    inactive = serializers.IntegerField()
    suspended = serializers.IntegerField()
    rejected = serializers.IntegerField()


class ConversationStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    closed = serializers.IntegerField()
    archived = serializers.IntegerField()
    fulfilled = serializers.IntegerField()


class RevenueStatsSerializer(serializers.Serializer):
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    completed_transactions = serializers.IntegerField()
    pending_transactions = serializers.IntegerField()
    failed_transactions = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()


class OverviewSerializer(serializers.Serializer):
    period = StatisticsPeriodSerializer()
    hotels = HotelStatsSerializer()
    conversations = ConversationStatsSerializer()
    revenue = RevenueStatsSerializer()


class HotelDataSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    status = serializers.CharField()
    is_verified = serializers.BooleanField()
    is_active = serializers.BooleanField()
    registration_date = serializers.DateTimeField()
    city = serializers.CharField()
    country = serializers.CharField()


class HotelsStatsResponseSerializer(serializers.Serializer):
    period = StatisticsPeriodSerializer()
    summary = HotelStatsSerializer()
    data = HotelDataSerializer(many=True)


class ConversationDataSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    hotel_name = serializers.CharField()
    guest_name = serializers.CharField()
    status = serializers.CharField()
    conversation_type = serializers.CharField()
    created_at = serializers.DateTimeField()
    last_message_at = serializers.DateTimeField()
    message_count = serializers.IntegerField()
    is_fulfilled = serializers.BooleanField()


class ConversationsStatsResponseSerializer(serializers.Serializer):
    period = StatisticsPeriodSerializer()
    summary = ConversationStatsSerializer()
    data = ConversationDataSerializer(many=True)


class TransactionDataSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    hotel_name = serializers.CharField()
    plan_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    transaction_type = serializers.CharField()
    created_at = serializers.DateTimeField()


class PaymentsStatsResponseSerializer(serializers.Serializer):
    period = StatisticsPeriodSerializer()
    summary = RevenueStatsSerializer()
    data = TransactionDataSerializer(many=True)