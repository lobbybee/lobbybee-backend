from datetime import timedelta

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from chat.utils.whatsapp_flow_utils import is_conversation_expired


class ConversationExpiryUtilsTest(SimpleTestCase):
    def test_recent_aware_timestamp_is_not_expired(self):
        last_message_at = timezone.now() - timedelta(seconds=30)

        self.assertFalse(is_conversation_expired(last_message_at, expiry_minutes=2))

    def test_old_timestamp_is_expired(self):
        last_message_at = timezone.now() - timedelta(minutes=3)

        self.assertTrue(is_conversation_expired(last_message_at, expiry_minutes=2))

    @override_settings(TIME_ZONE="America/New_York", USE_TZ=True)
    def test_recent_naive_local_timestamp_is_not_treated_as_utc(self):
        local_now = timezone.localtime(timezone.now())
        naive_local_time = local_now.replace(second=0, microsecond=0, tzinfo=None)

        self.assertFalse(is_conversation_expired(naive_local_time, expiry_minutes=2))

    def test_future_timestamp_is_not_expired(self):
        last_message_at = timezone.now() + timedelta(minutes=1)

        self.assertFalse(is_conversation_expired(last_message_at, expiry_minutes=2))
