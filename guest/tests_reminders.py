from datetime import timedelta, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from guest.models import Guest, ReminderLog, Stay
from guest.tasks import (
    schedule_checkin_reminder,
    schedule_meal_reminders,
    send_extend_checkin_reminder,
)
from hotel.models import Hotel


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

    def _create_active_stay(self, checkout_delta_hours=30):
        now = timezone.now()
        return Stay.objects.create(
            hotel=self.hotel,
            guest=self.guest,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(hours=checkout_delta_hours),
            status='active',
            breakfast_reminder=True,
            lunch_reminder=True,
            dinner_reminder=True,
            identity_verified=True,
        )

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
