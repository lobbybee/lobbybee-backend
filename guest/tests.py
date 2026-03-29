from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from guest.models import Booking, Guest, GuestIdentityDocument, Stay
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

    def test_verify_checkin_activates_all_pending_stays_for_same_booking(self):
        guest = Guest.objects.create(
            full_name="Multi Room Guest",
            whatsapp_number="+15550000999",
            status="pending_checkin",
        )
        now = timezone.now()
        booking = Booking.objects.create(
            hotel=self.hotel,
            primary_guest=guest,
            check_in_date=now,
            check_out_date=now + timedelta(days=2),
            status="pending",
            total_amount=0,
            guest_names=[guest.full_name],
        )

        second_room = Room.objects.create(
            hotel=self.hotel,
            room_number="102",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        self.room.status = "occupied"
        self.room.current_guest = guest
        self.room.save(update_fields=["status", "current_guest"])

        primary_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=now,
            check_out_date=now + timedelta(days=2),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )
        secondary_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=second_room,
            check_in_date=now,
            check_out_date=now + timedelta(days=2),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )

        payload = {"register_number": "REG-MULTI-001"}
        response = self.client.patch(
            f"/api/guest/stay-management/{primary_stay.id}/verify-checkin/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertCountEqual(
            response.data["data"]["activated_stay_ids"],
            [primary_stay.id, secondary_stay.id],
        )

        primary_stay.refresh_from_db()
        secondary_stay.refresh_from_db()
        booking.refresh_from_db()
        guest.refresh_from_db()

        self.assertEqual(primary_stay.status, "active")
        self.assertEqual(secondary_stay.status, "active")
        self.assertTrue(primary_stay.identity_verified)
        self.assertTrue(secondary_stay.identity_verified)
        self.assertIsNotNone(primary_stay.actual_check_in)
        self.assertIsNotNone(secondary_stay.actual_check_in)
        self.assertEqual(guest.status, "checked_in")
        self.assertEqual(booking.status, "confirmed")

    def test_verify_checkin_accepts_room_ids_and_reassigns_all_pending_stays(self):
        guest = Guest.objects.create(
            full_name="Room Switch Guest",
            whatsapp_number="+15550000888",
            status="pending_checkin",
        )
        now = timezone.now()
        booking = Booking.objects.create(
            hotel=self.hotel,
            primary_guest=guest,
            check_in_date=now,
            check_out_date=now + timedelta(days=1),
            status="pending",
            total_amount=0,
            guest_names=[guest.full_name],
        )

        old_room_one = self.room
        old_room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="102",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        old_room_one.status = "occupied"
        old_room_one.current_guest = guest
        old_room_one.save(update_fields=["status", "current_guest"])

        new_room_one = Room.objects.create(
            hotel=self.hotel,
            room_number="103",
            category=self.room.category,
            floor=1,
            status="available",
        )
        new_room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="104",
            category=self.room.category,
            floor=1,
            status="available",
        )

        primary_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=old_room_one,
            check_in_date=now,
            check_out_date=now + timedelta(days=1),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )
        secondary_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=old_room_two,
            check_in_date=now,
            check_out_date=now + timedelta(days=1),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )

        response = self.client.patch(
            f"/api/guest/stay-management/{primary_stay.id}/verify-checkin/",
            {"room_ids": [new_room_one.id, new_room_two.id], "register_number": "REG-ROOM-002"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertCountEqual(response.data["data"]["room_ids"], [new_room_one.id, new_room_two.id])
        self.assertIn("2 stay(s)", response.data["data"]["message"])

        primary_stay.refresh_from_db()
        secondary_stay.refresh_from_db()
        old_room_one.refresh_from_db()
        old_room_two.refresh_from_db()
        new_room_one.refresh_from_db()
        new_room_two.refresh_from_db()

        self.assertCountEqual([primary_stay.room_id, secondary_stay.room_id], [new_room_one.id, new_room_two.id])
        self.assertEqual(old_room_one.status, "available")
        self.assertEqual(old_room_two.status, "available")
        self.assertIsNone(old_room_one.current_guest)
        self.assertIsNone(old_room_two.current_guest)
        self.assertEqual(new_room_one.status, "occupied")
        self.assertEqual(new_room_two.status, "occupied")
        self.assertEqual(new_room_one.current_guest_id, guest.id)
        self.assertEqual(new_room_two.current_guest_id, guest.id)
