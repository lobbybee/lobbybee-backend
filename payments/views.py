from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from .models import SubscriptionPlan, Transaction, HotelSubscription
from .serializers import SubscriptionPlanSerializer, TransactionSerializer, HotelSubscriptionSerializer, HotelSubscriptionDetailSerializer
from hotel.models import Hotel
from hotel.permissions import IsHotelAdmin, CanManagePlatform, IsSameHotelUser
from rest_framework.permissions import IsAuthenticated


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated, CanManagePlatform]
    
    def get_permissions(self):
        if self.action == 'list':
            # Allow hotel admins to view plans
            permission_classes = [IsAuthenticated]
        else:
            # Only platform admins can create/update/delete plans
            permission_classes = [IsAuthenticated, CanManagePlatform]
        return [permission() for permission in permission_classes]


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Only platform staff can manually manage transactions
            permission_classes = [IsAuthenticated, CanManagePlatform]
        else:
            # Hotel admins can view their own transactions
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Transaction.objects.all()
        elif hasattr(user, 'hotel') and user.hotel:
            return Transaction.objects.filter(hotel=user.hotel)
        return Transaction.objects.none()
    
    def perform_create(self, serializer):
        # For manual transactions, set the transaction type
        serializer.save(transaction_type='manual')


class HotelSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = HotelSubscription.objects.all()
    serializer_class = HotelSubscriptionSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Only platform staff can manage subscriptions
            permission_classes = [IsAuthenticated, CanManagePlatform]
        else:
            # Hotel admins can view their own subscription
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return HotelSubscriptionDetailSerializer
        return HotelSubscriptionSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return HotelSubscription.objects.all()
        elif hasattr(user, 'hotel') and user.hotel:
            return HotelSubscription.objects.filter(hotel=user.hotel)
        return HotelSubscription.objects.none()
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsHotelAdmin])
    def my_subscription(self, request):
        """Get the current subscription for the authenticated hotel user"""
        try:
            subscription = HotelSubscription.objects.get(hotel=request.user.hotel)
            serializer = HotelSubscriptionDetailSerializer(subscription)
            return Response(serializer.data)
        except HotelSubscription.DoesNotExist:
            return Response({'detail': 'No active subscription found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanManagePlatform])
    def create_subscription(self, request):
        """Create a new subscription for a hotel"""
        hotel_id = request.data.get('hotel')
        plan_id = request.data.get('plan')
        
        if not hotel_id or not plan_id:
            return Response({'detail': 'Hotel and plan are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            hotel = Hotel.objects.get(id=hotel_id)
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except (Hotel.DoesNotExist, SubscriptionPlan.DoesNotExist):
            return Response({'detail': 'Hotel or plan not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if hotel already has a subscription
        if hasattr(hotel, 'subscription'):
            return Response({'detail': 'Hotel already has a subscription'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create subscription
        start_date = timezone.now()
        end_date = start_date + timedelta(days=plan.duration_days)
        
        subscription = HotelSubscription.objects.create(
            hotel=hotel,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )
        
        # Create transaction record
        Transaction.objects.create(
            hotel=hotel,
            plan=plan,
            amount=plan.price,
            transaction_type='subscription',
            status='completed',
            notes=f'Subscription created for {plan.name}'
        )
        
        serializer = HotelSubscriptionSerializer(subscription)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanManagePlatform])
    def extend_subscription(self, request):
        """Extend an existing subscription for a hotel"""
        hotel_id = request.data.get('hotel')
        days = request.data.get('days', 30)  # Default to 30 days
        
        if not hotel_id:
            return Response({'detail': 'Hotel is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subscription = HotelSubscription.objects.get(hotel_id=hotel_id)
        except HotelSubscription.DoesNotExist:
            return Response({'detail': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Extend the subscription
        subscription.end_date += timedelta(days=days)
        subscription.save()
        
        # Create transaction record
        Transaction.objects.create(
            hotel=subscription.hotel,
            plan=subscription.plan,
            amount=0,  # No charge for extension
            transaction_type='manual',
            status='completed',
            notes=f'Subscription extended by {days} days'
        )
        
        serializer = HotelSubscriptionSerializer(subscription)
        return Response(serializer.data, status=status.HTTP_200_OK)