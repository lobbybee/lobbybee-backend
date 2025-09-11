from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import SubscriptionPlan, Transaction, HotelSubscription
from hotel.models import Hotel
from user.models import User


class PaymentModelsTest(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a test hotel
        self.hotel = Hotel.objects.create(
            name='Test Hotel',
            description='A test hotel',
            address='123 Test Street',
            city='Test City',
            state='Test State',
            country='Test Country',
            pincode='123456',
            phone='1234567890'
        )
        
        # Store the initial count of subscription plans
        self.initial_plan_count = SubscriptionPlan.objects.count()
        
        # Create subscription plans
        self.trial_plan = SubscriptionPlan.objects.create(
            name='Trial Plan Test',
            plan_type='trial',
            price=Decimal('0.00'),
            duration_days=14,
            description='Free trial plan for 14 days'
        )
        
        self.standard_plan = SubscriptionPlan.objects.create(
            name='Standard Plan Test',
            plan_type='standard',
            price=Decimal('99.99'),
            duration_days=30,
            description='Standard monthly plan'
        )
    
    def test_subscription_plan_creation(self):
        """Test that subscription plans can be created"""
        # Check that we have 2 more plans than before
        self.assertEqual(SubscriptionPlan.objects.count(), self.initial_plan_count + 2)
        self.assertEqual(self.trial_plan.plan_type, 'trial')
        self.assertEqual(self.standard_plan.plan_type, 'standard')
    
    def test_transaction_creation(self):
        """Test that transactions can be created"""
        transaction = Transaction.objects.create(
            hotel=self.hotel,
            plan=self.standard_plan,
            amount=self.standard_plan.price,
            transaction_id='txn_123456',
            notes='Test transaction'
        )
        
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(transaction.hotel, self.hotel)
        self.assertEqual(transaction.plan, self.standard_plan)
        self.assertEqual(transaction.amount, self.standard_plan.price)
    
    def test_hotel_subscription_creation(self):
        """Test that hotel subscriptions can be created"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=30)
        
        subscription = HotelSubscription.objects.create(
            hotel=self.hotel,
            plan=self.standard_plan,
            start_date=start_date,
            end_date=end_date
        )
        
        self.assertEqual(HotelSubscription.objects.count(), 1)
        self.assertEqual(subscription.hotel, self.hotel)
        self.assertEqual(subscription.plan, self.standard_plan)
        self.assertTrue(subscription.is_active)
        self.assertFalse(subscription.is_expired())
    
    def test_hotel_subscription_expiry(self):
        """Test that hotel subscription expiry works correctly"""
        # Create an expired subscription
        start_date = timezone.now() - timedelta(days=60)
        end_date = timezone.now() - timedelta(days=30)
        
        subscription = HotelSubscription.objects.create(
            hotel=self.hotel,
            plan=self.standard_plan,
            start_date=start_date,
            end_date=end_date
        )
        
        self.assertTrue(subscription.is_expired())
        self.assertEqual(subscription.days_until_expiry(), 0)
    
    def test_hotel_subscription_days_until_expiry(self):
        """Test that days until expiry calculation works"""
        # Create a subscription that expires in 15 days
        start_date = timezone.now()
        end_date = timezone.now() + timedelta(days=15)
        
        subscription = HotelSubscription.objects.create(
            hotel=self.hotel,
            plan=self.standard_plan,
            start_date=start_date,
            end_date=end_date
        )
        
        # The days until expiry should be approximately 15 (may be 14 or 15 depending on timing)
        self.assertIn(subscription.days_until_expiry(), [14, 15])
