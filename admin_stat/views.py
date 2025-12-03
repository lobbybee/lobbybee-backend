from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from hotel.models import Hotel
from chat.models import Conversation, Message
from payments.models import Transaction, HotelSubscription
from hotel.permissions import CanManagePlatform
from .serializers import (
    OverviewSerializer,
    HotelsStatsResponseSerializer,
    ConversationsStatsResponseSerializer,
    PaymentsStatsResponseSerializer,
    StatisticsPeriodSerializer
)


class DateFilterMixin:
    """Mixin to handle date filtering for statistics endpoints"""
    
    def get_date_range(self, request):
        """Get date range from query parameters or default to last 30 days"""
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = timezone.now().date() - timedelta(days=30)
                end_date = timezone.now().date()
        else:
            # Default to last 30 days
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
            
        # Convert to datetime for database queries
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        return start_datetime, end_datetime
    
    def get_period_data(self, request):
        """Get period data for response"""
        start_datetime, end_datetime = self.get_date_range(request)
        return {
            'start_date': start_datetime.date(),
            'end_date': end_datetime.date()
        }


class AdminOverviewView(DateFilterMixin, APIView):
    """
    Overview endpoint with total counts for all major statistics
    """
    permission_classes = [CanManagePlatform]
    
    def get(self, request):
        start_datetime, end_datetime = self.get_date_range(request)
        
        # Hotel statistics
        hotel_stats = Hotel.objects.aggregate(
            total=Count('id'),
            registered=Count('id', filter=Q(registration_date__lte=end_datetime)),
            verified=Count('id', filter=Q(is_verified=True)),
            unverified=Count('id', filter=Q(is_verified=False)),
            inactive=Count('id', filter=Q(is_active=False)),
            suspended=Count('id', filter=Q(status='suspended')),
            rejected=Count('id', filter=Q(status='rejected'))
        )
        
        # Conversation statistics
        conversation_stats = Conversation.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
            closed=Count('id', filter=Q(status='closed')),
            archived=Count('id', filter=Q(status='archived')),
            fulfilled=Count('id', filter=Q(is_request_fulfilled=True))
        )
        
        # Revenue statistics
        revenue_stats = Transaction.objects.filter(
            created_at__range=(start_datetime, end_datetime)
        ).aggregate(
            total_revenue=Sum('amount', filter=Q(status='completed')),
            completed_transactions=Count('id', filter=Q(status='completed')),
            pending_transactions=Count('id', filter=Q(status='pending')),
            failed_transactions=Count('id', filter=Q(status='failed'))
        )
        
        # Active subscriptions
        active_subscriptions = HotelSubscription.objects.filter(
            is_active=True,
            end_date__gte=timezone.now()
        ).count()
        
        # Prepare response data
        response_data = {
            'period': self.get_period_data(request),
            'hotels': {
                'total': hotel_stats['total'],
                'registered': hotel_stats['registered'],
                'verified': hotel_stats['verified'],
                'unverified': hotel_stats['unverified'],
                'inactive': hotel_stats['inactive'],
                'suspended': hotel_stats['suspended'],
                'rejected': hotel_stats['rejected']
            },
            'conversations': {
                'total': conversation_stats['total'],
                'active': conversation_stats['active'],
                'closed': conversation_stats['closed'],
                'archived': conversation_stats['archived'],
                'fulfilled': conversation_stats['fulfilled']
            },
            'revenue': {
                'total_revenue': revenue_stats['total_revenue'] or 0,
                'completed_transactions': revenue_stats['completed_transactions'] or 0,
                'pending_transactions': revenue_stats['pending_transactions'] or 0,
                'failed_transactions': revenue_stats['failed_transactions'] or 0,
                'active_subscriptions': active_subscriptions
            }
        }
        
        serializer = OverviewSerializer(response_data)
        return Response(serializer.data)


class AdminHotelsStatsView(DateFilterMixin, APIView):
    """
    Hotel statistics with detailed data and date filtering
    """
    permission_classes = [CanManagePlatform]
    
    def get(self, request):
        start_datetime, end_datetime = self.get_date_range(request)
        
        # Filter hotels by registration date range
        hotels = Hotel.objects.filter(
            registration_date__range=(start_datetime, end_datetime)
        ).select_related().order_by('-registration_date')
        
        # Get summary statistics
        summary_stats = Hotel.objects.filter(
            registration_date__range=(start_datetime, end_datetime)
        ).aggregate(
            total=Count('id'),
            registered=Count('id'),
            verified=Count('id', filter=Q(is_verified=True)),
            unverified=Count('id', filter=Q(is_verified=False)),
            inactive=Count('id', filter=Q(is_active=False)),
            suspended=Count('id', filter=Q(status='suspended')),
            rejected=Count('id', filter=Q(status='rejected'))
        )
        
        # Prepare detailed hotel data
        hotel_data = []
        for hotel in hotels:
            hotel_data.append({
                'id': hotel.id,
                'name': hotel.name,
                'email': hotel.email,
                'status': hotel.status,
                'is_verified': hotel.is_verified,
                'is_active': hotel.is_active,
                'registration_date': hotel.registration_date,
                'city': hotel.city,
                'country': hotel.country
            })
        
        response_data = {
            'period': self.get_period_data(request),
            'summary': summary_stats,
            'data': hotel_data
        }
        
        serializer = HotelsStatsResponseSerializer(response_data)
        return Response(serializer.data)


class AdminConversationsStatsView(DateFilterMixin, APIView):
    """
    Conversation statistics with detailed data and date filtering
    """
    permission_classes = [CanManagePlatform]
    
    def get(self, request):
        start_datetime, end_datetime = self.get_date_range(request)
        
        # Filter conversations by creation date range
        conversations = Conversation.objects.filter(
            created_at__range=(start_datetime, end_datetime)
        ).select_related('hotel', 'guest').prefetch_related('messages').order_by('-created_at')
        
        # Get summary statistics
        summary_stats = Conversation.objects.filter(
            created_at__range=(start_datetime, end_datetime)
        ).aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
            closed=Count('id', filter=Q(status='closed')),
            archived=Count('id', filter=Q(status='archived')),
            fulfilled=Count('id', filter=Q(is_request_fulfilled=True))
        )
        
        # Prepare detailed conversation data
        conversation_data = []
        for conv in conversations:
            message_count = conv.messages.count()
            
            conversation_data.append({
                'id': conv.id,
                'hotel_name': conv.hotel.name if conv.hotel else 'N/A',
                'guest_name': conv.guest.full_name if conv.guest else 'N/A',
                'status': conv.status,
                'conversation_type': conv.conversation_type,
                'created_at': conv.created_at,
                'last_message_at': conv.last_message_at,
                'message_count': message_count,
                'is_fulfilled': conv.is_request_fulfilled
            })
        
        response_data = {
            'period': self.get_period_data(request),
            'summary': summary_stats,
            'data': conversation_data
        }
        
        serializer = ConversationsStatsResponseSerializer(response_data)
        return Response(serializer.data)


class AdminPaymentsStatsView(DateFilterMixin, APIView):
    """
    Payment/Revenue statistics with detailed data and date filtering
    """
    permission_classes = [CanManagePlatform]
    
    def get(self, request):
        start_datetime, end_datetime = self.get_date_range(request)
        
        # Filter transactions by creation date range
        transactions = Transaction.objects.filter(
            created_at__range=(start_datetime, end_datetime)
        ).select_related('hotel', 'plan').order_by('-created_at')
        
        # Get summary statistics
        revenue_stats = Transaction.objects.filter(
            created_at__range=(start_datetime, end_datetime)
        ).aggregate(
            total_revenue=Sum('amount', filter=Q(status='completed')),
            completed_transactions=Count('id', filter=Q(status='completed')),
            pending_transactions=Count('id', filter=Q(status='pending')),
            failed_transactions=Count('id', filter=Q(status='failed'))
        )
        
        # Get active subscriptions count
        active_subscriptions = HotelSubscription.objects.filter(
            is_active=True,
            end_date__gte=timezone.now()
        ).count()
        
        # Prepare detailed transaction data
        transaction_data = []
        for transaction in transactions:
            transaction_data.append({
                'id': transaction.id,
                'hotel_name': transaction.hotel.name,
                'plan_name': transaction.plan.name,
                'amount': transaction.amount,
                'status': transaction.status,
                'transaction_type': transaction.transaction_type,
                'created_at': transaction.created_at
            })
        
        response_data = {
            'period': self.get_period_data(request),
            'summary': {
                'total_revenue': revenue_stats['total_revenue'] or 0,
                'completed_transactions': revenue_stats['completed_transactions'] or 0,
                'pending_transactions': revenue_stats['pending_transactions'] or 0,
                'failed_transactions': revenue_stats['failed_transactions'] or 0,
                'active_subscriptions': active_subscriptions
            },
            'data': transaction_data
        }
        
        serializer = PaymentsStatsResponseSerializer(response_data)
        return Response(serializer.data)