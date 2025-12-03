from django.urls import path
from . import views

urlpatterns = [
    path('overview/', views.AdminOverviewView.as_view(), name='admin-overview'),
    path('hotels/', views.AdminHotelsStatsView.as_view(), name='admin-hotels-stats'),
    path('conversations/', views.AdminConversationsStatsView.as_view(), name='admin-conversations-stats'),
    path('payments/', views.AdminPaymentsStatsView.as_view(), name='admin-payments-stats'),
]