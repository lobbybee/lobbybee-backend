from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from .models import SubscriptionPlan, Transaction, HotelSubscription
from .serializers import SubscriptionPlanSerializer, TransactionSerializer, HotelSubscriptionSerializer, HotelSubscriptionDetailSerializer, SubscribeToPlanSerializer, ProcessPaymentSerializer
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
            # But hotel admins can create payment transactions for their own hotel
            permission_classes = [IsAuthenticated]
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
    
    def create(self, request, *args, **kwargs):
        # Override create to ensure hotel admins can only create transactions for their own hotel
        user = request.user
        if (hasattr(user, 'hotel') and user.hotel and 
            request.data.get('hotel') == str(user.hotel.id)):
            # Hotel admin is creating transaction for their own hotel
            return super().create(request, *args, **kwargs)
        elif user.is_staff or user.is_superuser:
            # Platform staff can create transactions for any hotel
            return super().create(request, *args, **kwargs)
        else:
            return Response(
                {'detail': 'You do not have permission to perform this action.'},
                status=status.HTTP_403_FORBIDDEN
            )


class HotelSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = HotelSubscription.objects.all()
    serializer_class = HotelSubscriptionSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Only platform staff can manage subscriptions
            permission_classes = [IsAuthenticated, CanManagePlatform]
        elif self.action in ['subscribe_to_plan', 'process_payment']:
            # Hotel admins can subscribe to plans and process payments
            permission_classes = [IsAuthenticated, IsHotelAdmin]
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
        """Create a new subscription for a hotel (platform admin only)"""
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
        """Extend an existing subscription for a hotel (platform admin only)"""
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
    
    @action(detail=False, methods=['post'])
    def subscribe_to_plan(self, request):
        """Allow hotel admin to subscribe to a plan"""
        serializer = SubscribeToPlanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        plan_id = serializer.validated_data['plan']
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            return Response({'detail': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if hotel already has a subscription
        if hasattr(request.user, 'hotel') and hasattr(request.user.hotel, 'subscription'):
            return Response({'detail': 'Hotel already has a subscription'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create subscription
        hotel = request.user.hotel
        start_date = timezone.now()
        end_date = start_date + timedelta(days=plan.duration_days)
        
        subscription = HotelSubscription.objects.create(
            hotel=hotel,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=False  # Not active until payment is processed
        )
        
        # Create transaction record
        transaction = Transaction.objects.create(
            hotel=hotel,
            plan=plan,
            amount=plan.price,
            transaction_type='subscription',
            status='pending',  # Pending until payment is processed
            notes=f'Subscription initiated for {plan.name}'
        )
        
        serializer = HotelSubscriptionSerializer(subscription)
        return Response({
            'subscription': serializer.data,
            'transaction_id': transaction.id,
            'amount': transaction.amount
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def process_payment(self, request):
        """Process payment for a subscription"""
        serializer = ProcessPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        transaction_id = serializer.validated_data['transaction_id']
        payment_details = serializer.validated_data.get('payment_details', {})
        
        try:
            transaction = Transaction.objects.get(id=transaction_id, hotel=request.user.hotel)
        except Transaction.DoesNotExist:
            return Response({'detail': 'Transaction not found or not authorized'}, status=status.HTTP_404_NOT_FOUND)
        
        # Here you would integrate with a payment gateway
        # For now, we'll simulate a successful payment
        payment_successful = True  # This would be determined by the payment gateway response
        
        if payment_successful:
            # Update transaction status
            transaction.status = 'completed'
            transaction.transaction_id = payment_details.get('gateway_transaction_id', '')
            transaction.notes = f"Payment processed successfully. {transaction.notes}"
            transaction.save()
            
            # Activate the subscription since payment was successful
            subscription = HotelSubscription.objects.get(hotel=request.user.hotel)
            subscription.is_active = True
            subscription.save()
            
            return Response({
                'detail': 'Payment processed successfully',
                'transaction_id': transaction.id,
                'status': transaction.status
            }, status=status.HTTP_200_OK)
        else:
            # Update transaction status to failed
            transaction.status = 'failed'
            transaction.notes = f"Payment failed. {transaction.notes}"
            transaction.save()
            
            return Response({
                'detail': 'Payment failed',
                'transaction_id': transaction.id,
                'status': transaction.status
            }, status=status.HTTP_400_BAD_REQUEST)