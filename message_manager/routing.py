from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/staff/', consumers.StaffConsumer.as_asgi()),
]