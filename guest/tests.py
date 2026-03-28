from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from guest.models import Guest, GuestIdentityDocument, Stay
from hotel.models import Hotel, Room, RoomCategory
from user.models import User


class GuestAndStayEndpointTests(APITestCase):
    def setUp(self):
        self.hotel = Hotel.objects.create(name="Hotel One")
        self.other_hotel = Hotel.objects.create(name="Hotel Two")

        self.user = User.objects.create_user(
            username="hoteladmin",
            email="hoteladmin@example.com",
            password="password123",
            user_type="hotel_admin",
            hotel=self.hotel,
        )
        self.client.force_authenticate(user=self.user)

        category_one = RoomCategory.objects.create(
            hotel=self.hotel,
            name="Deluxe",
            base_price=1000,
            max_occupancy=2,
            amenities=[],
        )
        category_two = RoomCategory.objects.create(
            hotel=self.other_hotel,
            name="Suite",
            base_price=2000,
            max_occupancy=2,
            amenities=[],
        )

        self.room = Room.objects.create(
            hotel=self.hotel,
            room_number="101",
            category=category_one,
            floor=1,
            status="available",
        )
        self.other_room = Room.objects.create(
            hotel=self.other_hotel,
            room_number="201",
            category=category_two,
            floor=2,
            status="available",
        )

    def _create_guest_with_document(self, hotel, name, phone, doc_number):
        guest = Guest.objects.create(
            full_name=name,
            whatsapp_number=phone,
            status="pending_checkin",
        )
        GuestIdentityDocument.objects.create(
            guest=guest,
            document_type="national_id",
            document_number=doc_number,
            document_file=SimpleUploadedFile("id.jpg", b"fake-image", content_type="image/jpeg"),
            is_primary=True,
        )

        room = self.room if hotel == self.hotel else self.other_room
        now = timezone.now()
        Stay.objects.create(
            hotel=hotel,
            guest=guest,
            room=room,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=1),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )
        return guest

    def test_guest_management_search_supports_id_number_and_is_not_paginated(self):
        self._create_guest_with_document(
            hotel=self.hotel,
            name="Alice Guest",
            phone="+15550000001",
            doc_number="ALICE-ID-7788",
        )
        duplicate_guest = self._create_guest_with_document(
            hotel=self.hotel,
            name="Bob Duplicate",
            phone="+15550000002",
            doc_number="DUP-55",
        )

        GuestIdentityDocument.objects.create(
            guest=duplicate_guest,
            document_type="other",
            document_number="DUP-55-SECOND",
            document_file=SimpleUploadedFile("id2.jpg", b"fake-image-2", content_type="image/jpeg"),
            is_primary=False,
        )

        response = self.client.get("/api/guest/guest-management/guests/", {"search": "DUP-55"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIsInstance(response.data["data"], list)
        self.assertNotIn("count", response.data["data"])
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["id"], duplicate_guest.id)

    def test_checked_in_users_returns_all_stays_with_pagination_and_is_checked_in(self):
        now = timezone.now()
        active_guest = self._create_guest_with_document(
            hotel=self.hotel,
            name="Active User",
            phone="+15550000010",
            doc_number="ACTIVE-111",
        )
        completed_guest = self._create_guest_with_document(
            hotel=self.hotel,
            name="Completed User",
            phone="+15550000011",
            doc_number="COMPLETE-222",
        )
        pending_guest = self._create_guest_with_document(
            hotel=self.hotel,
            name="Pending User",
            phone="+15550000012",
            doc_number="PENDING-333",
        )
        self._create_guest_with_document(
            hotel=self.other_hotel,
            name="Other Hotel User",
            phone="+15550000099",
            doc_number="OTHER-999",
        )

        Stay.objects.filter(guest=active_guest, hotel=self.hotel).update(
            status="active",
            actual_check_in=now - timedelta(hours=4),
        )
        Stay.objects.filter(guest=completed_guest, hotel=self.hotel).update(
            status="completed",
            actual_check_out=now - timedelta(hours=2),
        )
        Stay.objects.filter(guest=pending_guest, hotel=self.hotel).update(status="pending")

        response = self.client.get(
            "/api/guest/stay-management/checked-in-users/",
            {"page": 1, "page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("data", response.data)
        self.assertIn("count", response.data["data"])
        self.assertIn("results", response.data["data"])
        self.assertEqual(response.data["data"]["count"], 3)

        results = response.data["data"]["results"]
        self.assertEqual(len(results), 3)
        returned_guest_ids = {item["guest"]["id"] for item in results}
        self.assertIn(active_guest.id, returned_guest_ids)
        self.assertIn(completed_guest.id, returned_guest_ids)
        self.assertIn(pending_guest.id, returned_guest_ids)

        is_checked_in_by_guest_id = {item["guest"]["id"]: item["isCheckedIn"] for item in results}
        self.assertTrue(is_checked_in_by_guest_id[active_guest.id])
        self.assertFalse(is_checked_in_by_guest_id[completed_guest.id])
        self.assertFalse(is_checked_in_by_guest_id[pending_guest.id])

    def test_checked_in_users_search_supports_identity_document_number(self):
        matching_guest = self._create_guest_with_document(
            hotel=self.hotel,
            name="Searchable Stay",
            phone="+15550000101",
            doc_number="SEARCH-ID-ABC-1",
        )
        self._create_guest_with_document(
            hotel=self.hotel,
            name="Non Matching Stay",
            phone="+15550000102",
            doc_number="NONMATCH-XYZ-2",
        )

        response = self.client.get(
            "/api/guest/stay-management/checked-in-users/",
            {"search": "SEARCH-ID-ABC-1", "page": 1, "page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 1)
        result = response.data["data"]["results"][0]
        self.assertEqual(result["guest"]["id"], matching_guest.id)
        self.assertFalse(result["isCheckedIn"])
