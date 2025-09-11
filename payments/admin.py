from django.contrib import admin
from .models import SubscriptionPlan, Transaction, HotelSubscription


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price', 'duration_days', 'is_active')
    list_filter = ('plan_type', 'is_active')
    search_fields = ('name', 'description')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'plan', 'amount', 'transaction_type', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('hotel__name', 'transaction_id')
    date_hierarchy = 'created_at'


@admin.register(HotelSubscription)
class HotelSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'plan', 'start_date', 'end_date', 'is_active', 'is_expired')
    list_filter = ('is_active', 'plan', 'start_date')
    search_fields = ('hotel__name',)
    date_hierarchy = 'start_date'
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
