from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from chat.views.flow_processsor import (
    handle_incoming_whatsapp_message,
    handle_start_menu_command,
)
from guest.models import Guest, Stay
from hotel.models import Hotel, Room, RoomCategory


class FlowProcessorStayHistoryTest(TestCase):
    def setUp(self):
        self.guest = Guest.objects.create(
            whatsapp_number="+15550001111",
            full_name="History Guest",
            status="checked_out",
        )

    @patch("chat.views.flow_processsor.adapt_checkin_response_to_whatsapp")
    @patch("chat.utils.template_util.process_template")
    def test_start_menu_always_shows_history_option(self, mock_template, mock_adapt):
        mock_template.return_value = {"success": False}
        mock_adapt.side_effect = lambda payload, _number: payload

        response_payload, status_code = handle_incoming_whatsapp_message(
            self.guest.whatsapp_number,
            {"message": "hi", "message_type": "text"},
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(response_payload[1]["type"], "button")
        option_ids = [option["id"] for option in response_payload[1]["options"]]
        self.assertIn("start_history", option_ids)

    @patch("chat.views.flow_processsor.adapt_checkin_response_to_whatsapp")
    @patch("chat.utils.template_util.process_template")
    def test_start_menu_shows_history_when_past_stays_exist(self, mock_template, mock_adapt):
        hotel, room = self._build_hotel_and_room("History Hotel")
        Stay.objects.create(
            hotel=hotel,
            guest=self.guest,
            room=room,
            check_in_date=timezone.now() - timedelta(days=3),
            check_out_date=timezone.now() - timedelta(days=1),
            status="completed",
        )

        mock_template.return_value = {"success": False}
        mock_adapt.side_effect = lambda payload, _number: payload

        response_payload, status_code = handle_incoming_whatsapp_message(
            self.guest.whatsapp_number,
            {"message": "hello", "message_type": "text"},
        )

        self.assertEqual(status_code, 200)
        option_ids = [option["id"] for option in response_payload[1]["options"]]
        self.assertIn("start_history", option_ids)

    @patch("chat.views.flow_processsor.adapt_checkin_response_to_whatsapp")
    @patch("chat.utils.template_util.process_template")
    def test_start_menu_matches_guest_on_formatted_number(self, mock_template, mock_adapt):
        formatted_guest = Guest.objects.create(
            whatsapp_number="15550002222",
            full_name="Formatted Number Guest",
            status="checked_out",
        )
        hotel, room = self._build_hotel_and_room("Number Match Hotel")
        Stay.objects.create(
            hotel=hotel,
            guest=formatted_guest,
            room=room,
            check_in_date=timezone.now() - timedelta(days=3),
            check_out_date=timezone.now() - timedelta(days=1),
            status="completed",
        )

        mock_template.return_value = {"success": False}
        mock_adapt.side_effect = lambda payload, _number: payload

        response_payload, status_code = handle_incoming_whatsapp_message(
            "+1 (555) 000-2222",
            {"message": "hello", "message_type": "text"},
        )

        self.assertEqual(status_code, 200)
        option_ids = [option["id"] for option in response_payload[1]["options"]]
        self.assertIn("start_history", option_ids)

    @patch("chat.views.flow_processsor.adapt_checkin_response_to_whatsapp")
    @patch("chat.utils.template_util.process_template")
    def test_start_menu_shows_history_for_past_due_non_cancelled_stay(self, mock_template, mock_adapt):
        hotel, room = self._build_hotel_and_room("Past Due Hotel")
        Stay.objects.create(
            hotel=hotel,
            guest=self.guest,
            room=room,
            check_in_date=timezone.now() - timedelta(days=4),
            check_out_date=timezone.now() - timedelta(days=1),
            status="active",
        )

        mock_template.return_value = {"success": False}
        mock_adapt.side_effect = lambda payload, _number: payload

        response_payload, status_code = handle_incoming_whatsapp_message(
            self.guest.whatsapp_number,
            {"message": "hello", "message_type": "text"},
        )

        self.assertEqual(status_code, 200)
        option_ids = [option["id"] for option in response_payload[1]["options"]]
        self.assertIn("start_history", option_ids)

    def test_start_history_returns_latest_five_stays_with_required_fields(self):
        now = timezone.now()
        for index in range(6):
            hotel_name = f"Hotel {index}"
            hotel, room = self._build_hotel_and_room(hotel_name)
            Stay.objects.create(
                hotel=hotel,
                guest=self.guest,
                room=room,
                check_in_date=now - timedelta(days=(index + 2)),
                check_out_date=now - timedelta(days=index),
                status="completed",
            )

        result = handle_start_menu_command(self.guest, "start_history")

        self.assertEqual(result["type"], "text")
        self.assertIn("Stay History (Last 5)", result["text"])
        self.assertIn("1. Hotel 0", result["text"])
        self.assertIn("5. Hotel 4", result["text"])
        self.assertNotIn("Hotel 5", result["text"])
        self.assertIn("Contact:", result["text"])
        self.assertIn("Date:", result["text"])
        self.assertIn("Nights:", result["text"])
        self.assertNotIn("Room:", result["text"])
        self.assertNotIn("Status:", result["text"])

    def test_start_history_returns_no_record_for_guest_without_past_stays(self):
        result = handle_start_menu_command(self.guest, "start_history")
        self.assertEqual(result["type"], "text")
        self.assertEqual(result["text"], "You don't have any stay record yet.")

    def _build_hotel_and_room(self, hotel_name):
        hotel = Hotel.objects.create(name=hotel_name, phone="+1234567890")
        category = RoomCategory.objects.create(
            hotel=hotel,
            name="Standard",
            description="Standard room",
            base_price=100.00,
            max_occupancy=2,
        )
        room = Room.objects.create(
            hotel=hotel,
            room_number=f"R-{hotel_name.replace(' ', '-')}",
            category=category,
            floor=1,
        )
        return hotel, room
