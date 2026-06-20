from rest_framework.test import APITestCase

from hotel.models import Hotel
from .activity import log_activity
from .models import ActivityLog, User


class ActivityLogTests(APITestCase):
    def setUp(self):
        self.hotel_a = Hotel.objects.create(name='Hotel A')
        self.hotel_b = Hotel.objects.create(name='Hotel B')
        self.user_a = User.objects.create_user(
            username='recep_a', email='a@x.com', password='pw',
            user_type='receptionist', hotel=self.hotel_a, is_verified=True,
        )
        self.user_b = User.objects.create_user(
            username='recep_b', email='b@x.com', password='pw',
            user_type='receptionist', hotel=self.hotel_b, is_verified=True,
        )

    def test_log_activity_creates_one_scoped_row(self):
        log_activity(self.user_a, self.hotel_a, 'checked_out', 'Checked out John', guest_id=7)
        self.assertEqual(ActivityLog.objects.count(), 1)
        row = ActivityLog.objects.get()
        self.assertEqual(row.hotel, self.hotel_a)
        self.assertEqual(row.actor, self.user_a)
        self.assertEqual(row.metadata, {'guest_id': 7})

    def test_log_activity_never_raises(self):
        # None hotel is a no-op, not an error.
        log_activity(self.user_a, None, 'x', 'y')
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_endpoint_filters_by_hotel(self):
        log_activity(self.user_a, self.hotel_a, 'checked_in', 'A action')
        log_activity(self.user_b, self.hotel_b, 'checked_in', 'B action')

        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/recent-activity/')
        self.assertEqual(resp.status_code, 200)
        messages = [r['message'] for r in resp.data['data']['results']]
        self.assertEqual(messages, ['A action'])

    def test_filters(self):
        log_activity(self.user_a, self.hotel_a, 'checked_in', 'Checked in Alice')
        log_activity(self.user_a, self.hotel_a, 'checked_out', 'Checked out Alice')
        log_activity(self.user_a, self.hotel_a, 'room_status', 'Room 1: a → b')
        self.client.force_authenticate(self.user_a)

        def msgs(query):
            return [r['message'] for r in self.client.get('/api/recent-activity/' + query).data['data']['results']]

        # multi-value action filter
        self.assertEqual(len(msgs('?action=checked_in,checked_out')), 2)
        # search
        self.assertEqual(msgs('?search=Room'), ['Room 1: a → b'])
        # actor by username
        self.assertEqual(len(msgs('?actor=recep_a')), 3)
        self.assertEqual(len(msgs('?actor=recep_b')), 0)
