from django.test import TestCase
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from guest.models import Guest, Hotel, Room, Stay
from hotel.models import Department, RoomCategory
from message_manager.models import Conversation
from message_manager.consumers import StaffConsumer
from user.models import User
import datetime
from django.utils import timezone


class WebSocketTestCase(TestCase):
    def test_websocket_consumer_import(self):
        """Test that the StaffConsumer can be imported and instantiated"""
        consumer = StaffConsumer()
        self.assertIsNotNone(consumer)

    def test_channel_layer_group_send(self):
        """Test that we can send messages to channel groups"""
        # Get the channel layer
        channel_layer = get_channel_layer()
        
        # Send a message to a test group
        async_to_sync(channel_layer.group_send)(
            "test_group",
            {
                "type": "new_message",
                "message": "Test message"
            }
        )
        
        # If we get here without an exception, the test passes
        self.assertTrue(True)

    def test_websocket_consumer_import(self):
        """Test that the StaffConsumer can be imported and instantiated"""
        consumer = StaffConsumer()
        self.assertIsNotNone(consumer)

    def test_channel_layer_group_send(self):
        """Test that we can send messages to channel groups"""
        # Get the channel layer
        channel_layer = get_channel_layer()
        
        # Send a message to a test group
        async_to_sync(channel_layer.group_send)(
            "test_group",
            {
                "type": "new_message",
                "message": "Test message"
            }
        )
        
        # If we get here without an exception, the test passes
        self.assertTrue(True)