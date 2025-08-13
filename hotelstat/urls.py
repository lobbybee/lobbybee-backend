from django.urls import path
from .views import StatsView

urlpatterns = [
    path('stat/', StatsView.as_view(), name='global-hotel-stats'),
    path('stat/<str:stat_type>/', StatsView.as_view(), name='detailed-stats'),
]
