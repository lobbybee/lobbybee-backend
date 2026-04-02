from datetime import timedelta, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from chat.models import Conversation, Message
from guest.models import Guest, ReminderLog, Stay
from guest.tasks import (
    schedule_checkin_reminder,
    schedule_meal_reminders,
    send_breakfast_reminder,
    send_extend_checkin_reminder,
    send_lunch_reminder,
)
from hotel.models import Hotel, Room, RoomCategory


class ReminderTaskTests(TestCase):
    def setUp(self):
        self.hotel_tz = ZoneInfo('Asia/Kolkata')
        self.hotel = Hotel.objects.create(
            name='Reminder Test Hotel',
            time_zone='Asia/Kolkata',
            status='verified',
            is_active=True,
            breakfast_reminder=True,
            dinner_reminder=True,
            breakfast_time=time(7, 30),
            lunch_time=None,
            dinner_time=time(19, 0),
        )
        self.guest = Guest.objects.create(
            whatsapp_number='+10000000001',
            full_name='Reminder Guest',
            status='checked_in',
        )
        self.room_category = RoomCategory.objects.create(
            hotel=self.hotel,
            name='Deluxe',
            base_price=1000,
            max_occupancy=2,
            amenities=[],
        )
        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number='101',
            category=self.room_category,
            floor=1,
            status='occupied',
        )
        self.conversation = Conversation.objects.create(
            guest=self.guest,
            hotel=self.hotel,
            department='Reception',
            conversation_type='checked_in',
            status='active',
        )

    def _create_active_stay(self, checkout_delta_hours=30):
        now = timezone.now()
        return Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=self.room,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(hours=checkout_delta_hours),
            status='active',
            breakfast_reminder=True,
            lunch_reminder=True,
            dinner_reminder=True,
            identity_verified=True,
        )

    def _create_guest_message(self, created_at):
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type='guest',
            message_type='text',
            content='Need help',
        )
        Message.objects.filter(id=message.id).update(created_at=created_at)
        message.refresh_from_db()
        return message

    @patch('guest.tasks.send_whatsapp_button_message')
    def test_checkout_send_is_skipped_if_already_sent(self, mock_send_button):
        stay = self._create_active_stay(checkout_delta_hours=2)
        reminder_date = stay.check_out_date.astimezone(self.hotel_tz).date()

        ReminderLog.objects.create(
            stay=stay,
            reminder_type='checkout',
            reminder_date=reminder_date,
            status='sent',
            sent_at=timezone.now(),
        )

        result = send_extend_checkin_reminder(stay.id, False, reminder_date.isoformat())

        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'already_sent')
        mock_send_button.assert_not_called()

        log = ReminderLog.objects.get(
            stay=stay,
            reminder_type='checkout',
            reminder_date=reminder_date,
        )
        self.assertEqual(log.status, 'sent')

    @patch('guest.tasks.send_breakfast_reminder.apply_async')
    @patch('guest.tasks.send_lunch_reminder.apply_async')
    @patch('guest.tasks.send_dinner_reminder.apply_async')
    def test_meal_schedule_uses_hotel_times_and_lunch_fallback(
        self,
        mock_dinner_apply_async,
        mock_lunch_apply_async,
        mock_breakfast_apply_async,
    ):
        stay = self._create_active_stay(checkout_delta_hours=48)

        result = schedule_meal_reminders(stay.id)

        self.assertEqual(result['status'], 'success')
        self.assertGreaterEqual(result['breakfast_scheduled'], 1)
        self.assertGreaterEqual(result['lunch_scheduled'], 1)
        self.assertGreaterEqual(result['dinner_scheduled'], 1)

        breakfast_log = ReminderLog.objects.filter(stay=stay, reminder_type='breakfast').earliest('reminder_date')
        lunch_log = ReminderLog.objects.filter(stay=stay, reminder_type='lunch').earliest('reminder_date')
        dinner_log = ReminderLog.objects.filter(stay=stay, reminder_type='dinner').earliest('reminder_date')

        self.assertIsNotNone(breakfast_log.scheduled_for)
        self.assertIsNotNone(lunch_log.scheduled_for)
        self.assertIsNotNone(dinner_log.scheduled_for)

        breakfast_local = breakfast_log.scheduled_for.astimezone(self.hotel_tz)
        lunch_local = lunch_log.scheduled_for.astimezone(self.hotel_tz)
        dinner_local = dinner_log.scheduled_for.astimezone(self.hotel_tz)

        self.assertEqual((breakfast_local.hour, breakfast_local.minute), (7, 30))
        self.assertEqual((lunch_local.hour, lunch_local.minute), (12, 30))
        self.assertEqual((dinner_local.hour, dinner_local.minute), (19, 0))

        self.assertGreaterEqual(mock_breakfast_apply_async.call_count, 1)
        self.assertGreaterEqual(mock_lunch_apply_async.call_count, 1)
        self.assertGreaterEqual(mock_dinner_apply_async.call_count, 1)

    @patch('guest.tasks.send_breakfast_reminder.apply_async')
    @patch('guest.tasks.send_lunch_reminder.apply_async')
    @patch('guest.tasks.send_dinner_reminder.apply_async')
    def test_meal_schedule_is_idempotent_for_existing_scheduled_logs(
        self,
        mock_dinner_apply_async,
        mock_lunch_apply_async,
        mock_breakfast_apply_async,
    ):
        stay = self._create_active_stay(checkout_delta_hours=48)

        first_result = schedule_meal_reminders(stay.id)
        self.assertEqual(first_result['status'], 'success')

        mock_breakfast_apply_async.reset_mock()
        mock_lunch_apply_async.reset_mock()
        mock_dinner_apply_async.reset_mock()

        second_result = schedule_meal_reminders(stay.id)

        self.assertEqual(second_result['status'], 'success')
        self.assertEqual(second_result['breakfast_scheduled'], 0)
        self.assertEqual(second_result['lunch_scheduled'], 0)
        self.assertEqual(second_result['dinner_scheduled'], 0)
        self.assertGreaterEqual(second_result['breakfast_already_present'], 1)
        self.assertGreaterEqual(second_result['lunch_already_present'], 1)
        self.assertGreaterEqual(second_result['dinner_already_present'], 1)

        mock_breakfast_apply_async.assert_not_called()
        mock_lunch_apply_async.assert_not_called()
        mock_dinner_apply_async.assert_not_called()

    @patch('guest.tasks.send_extend_checkin_reminder.apply_async')
    def test_checkout_schedule_skips_if_already_sent(self, mock_apply_async):
        stay = self._create_active_stay(checkout_delta_hours=8)
        reminder_date = stay.check_out_date.astimezone(self.hotel_tz).date()

        ReminderLog.objects.create(
            stay=stay,
            reminder_type='checkout',
            reminder_date=reminder_date,
            status='sent',
            sent_at=timezone.now(),
        )

        result = schedule_checkin_reminder(stay.id)

        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'already_sent')
        mock_apply_async.assert_not_called()

    @patch('guest.tasks.send_whatsapp_text_message')
    @patch('guest.tasks.send_whatsapp_template_message')
    def test_meal_reminder_uses_session_text_within_24_hours(self, mock_template_send, mock_text_send):
        stay = self._create_active_stay(checkout_delta_hours=30)
        self._create_guest_message(timezone.now() - timedelta(hours=2))

        result = send_breakfast_reminder(stay.id)

        self.assertEqual(result['status'], 'success')
        mock_text_send.assert_called_once()
        mock_template_send.assert_not_called()

        log = ReminderLog.objects.get(stay=stay, reminder_type='breakfast')
        self.assertEqual(log.metadata['delivery_mode'], 'session_text')
        self.assertIsNone(log.metadata['template_name'])
        self.assertIsNotNone(log.metadata['last_guest_message_at'])

    @patch('guest.tasks.send_whatsapp_text_message')
    @patch('guest.tasks.send_whatsapp_template_message')
    def test_meal_reminder_uses_template_when_guest_message_is_stale(self, mock_template_send, mock_text_send):
        stay = self._create_active_stay(checkout_delta_hours=30)
        self._create_guest_message(timezone.now() - timedelta(hours=25))
        mock_template_send.return_value = {'messages': [{'id': 'wamid-1'}]}

        result = send_breakfast_reminder(stay.id)

        self.assertEqual(result['status'], 'success')
        mock_text_send.assert_not_called()
        mock_template_send.assert_called_once()
        self.assertEqual(mock_template_send.call_args.kwargs['template_name'], 'meal_reminder')
        self.assertEqual(mock_template_send.call_args.kwargs['language_code'], 'en')

        log = ReminderLog.objects.get(stay=stay, reminder_type='breakfast')
        self.assertEqual(log.metadata['delivery_mode'], 'template')
        self.assertEqual(log.metadata['template_name'], 'meal_reminder')

    @patch('guest.tasks.send_whatsapp_text_message')
    @patch('guest.tasks.send_whatsapp_template_message')
    def test_meal_reminder_uses_template_when_no_guest_message_exists(self, mock_template_send, mock_text_send):
        stay = self._create_active_stay(checkout_delta_hours=30)
        mock_template_send.return_value = {'messages': [{'id': 'wamid-2'}]}

        result = send_breakfast_reminder(stay.id)

        self.assertEqual(result['status'], 'success')
        mock_text_send.assert_not_called()
        mock_template_send.assert_called_once()

        log = ReminderLog.objects.get(stay=stay, reminder_type='breakfast')
        self.assertEqual(log.metadata['delivery_mode'], 'template')
        self.assertIsNone(log.metadata['last_guest_message_at'])

    @patch('guest.tasks.send_whatsapp_template_message')
    def test_meal_template_uses_hotel_time_plus_three_hours(self, mock_template_send):
        stay = self._create_active_stay(checkout_delta_hours=30)
        mock_template_send.return_value = {'messages': [{'id': 'wamid-3'}]}

        send_breakfast_reminder(stay.id)

        components = mock_template_send.call_args.kwargs['components']
        body_parameters = components[0]['parameters']
        parameter_map = {item['parameter_name']: item['text'] for item in body_parameters}

        self.assertEqual(parameter_map['day_greeting'], 'Morning')
        self.assertEqual(parameter_map['guest_name'], 'Reminder')
        self.assertEqual(parameter_map['meal_name'], 'Breakfast')
        self.assertEqual(parameter_map['meal_start'], '7:30 AM')
        self.assertEqual(parameter_map['meal_end'], '10:30 AM')

    @patch('guest.tasks.send_whatsapp_template_message')
    def test_lunch_template_uses_fallback_time_plus_three_hours(self, mock_template_send):
        stay = self._create_active_stay(checkout_delta_hours=30)
        mock_template_send.return_value = {'messages': [{'id': 'wamid-4'}]}

        send_lunch_reminder(stay.id)

        components = mock_template_send.call_args.kwargs['components']
        body_parameters = components[0]['parameters']
        parameter_map = {item['parameter_name']: item['text'] for item in body_parameters}

        self.assertEqual(parameter_map['day_greeting'], 'Afternoon')
        self.assertEqual(parameter_map['meal_name'], 'Lunch')
        self.assertEqual(parameter_map['meal_start'], '12:30 PM')
        self.assertEqual(parameter_map['meal_end'], '3:30 PM')

    @patch('guest.tasks.send_whatsapp_button_message')
    @patch('guest.tasks.send_whatsapp_template_message')
    def test_checkout_reminder_uses_session_button_within_24_hours(self, mock_template_send, mock_button_send):
        stay = self._create_active_stay(checkout_delta_hours=2)
        self._create_guest_message(timezone.now() - timedelta(hours=3))
        mock_button_send.return_value = {'messages': [{'id': 'wamid-5'}]}

        result = send_extend_checkin_reminder(stay.id, False, stay.check_out_date.astimezone(self.hotel_tz).date().isoformat())

        self.assertEqual(result['status'], 'success')
        mock_button_send.assert_called_once()
        mock_template_send.assert_not_called()

        log = ReminderLog.objects.get(stay=stay, reminder_type='checkout')
        self.assertEqual(log.metadata['delivery_mode'], 'session_button')
        self.assertIsNone(log.metadata['template_name'])

    @patch('guest.tasks.send_whatsapp_button_message')
    @patch('guest.tasks.send_whatsapp_template_message')
    def test_checkout_reminder_uses_template_when_guest_message_is_stale(self, mock_template_send, mock_button_send):
        stay = self._create_active_stay(checkout_delta_hours=2)
        self._create_guest_message(timezone.now() - timedelta(hours=30))
        mock_template_send.return_value = {'messages': [{'id': 'wamid-6'}]}

        result = send_extend_checkin_reminder(stay.id, False, stay.check_out_date.astimezone(self.hotel_tz).date().isoformat())

        self.assertEqual(result['status'], 'success')
        mock_button_send.assert_not_called()
        mock_template_send.assert_called_once()
        self.assertEqual(mock_template_send.call_args.kwargs['template_name'], 'chekout_reminder')

        components = mock_template_send.call_args.kwargs['components']
        self.assertEqual(components[1]['parameters'][0]['payload'], f'stay_extend_yes_{stay.id}')
        self.assertEqual(components[2]['parameters'][0]['payload'], f'stay_extend_no_{stay.id}')

        log = ReminderLog.objects.get(stay=stay, reminder_type='checkout')
        self.assertEqual(log.metadata['delivery_mode'], 'template')
        self.assertEqual(log.metadata['template_name'], 'chekout_reminder')

    @patch('guest.tasks.send_whatsapp_template_message')
    def test_checkout_template_uses_aggregated_room_numbers(self, mock_template_send):
        stay = self._create_active_stay(checkout_delta_hours=2)
        room_two = Room.objects.create(
            hotel=self.hotel,
            room_number='102',
            category=self.room_category,
            floor=1,
            status='occupied',
        )
        Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            room=room_two,
            check_in_date=timezone.now() - timedelta(days=1),
            check_out_date=timezone.now() + timedelta(hours=2),
            status='active',
            breakfast_reminder=False,
            lunch_reminder=False,
            dinner_reminder=False,
            identity_verified=True,
        )
        mock_template_send.return_value = {'messages': [{'id': 'wamid-7'}]}

        send_extend_checkin_reminder(stay.id, False, stay.check_out_date.astimezone(self.hotel_tz).date().isoformat())

        components = mock_template_send.call_args.kwargs['components']
        body_parameters = components[0]['parameters']
        parameter_map = {item['parameter_name']: item['text'] for item in body_parameters}
        self.assertEqual(parameter_map['room_number'], '101, 102')
