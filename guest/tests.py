from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from chat.models import Conversation
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

    def test_verify_checkin_room_ids_can_expand_booking_like_offline_checkin(self):
        guest = Guest.objects.create(
            full_name="Expand Booking Guest",
            whatsapp_number="+15550000777",
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
            guest_names=[guest.full_name, guest.full_name],
        )

        base_room = self.room
        base_room.status = "occupied"
        base_room.current_guest = guest
        base_room.save(update_fields=["status", "current_guest"])

        target_room_one = Room.objects.create(
            hotel=self.hotel,
            room_number="105",
            category=self.room.category,
            floor=1,
            status="available",
        )
        target_room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="106",
            category=self.room.category,
            floor=1,
            status="available",
        )

        primary_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=base_room,
            check_in_date=now,
            check_out_date=now + timedelta(days=1),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )

        response = self.client.patch(
            f"/api/guest/stay-management/{primary_stay.id}/verify-checkin/",
            {"room_ids": [target_room_one.id, target_room_two.id], "register_number": "REG-ROOM-003"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertCountEqual(response.data["data"]["room_ids"], [target_room_one.id, target_room_two.id])
        self.assertEqual(len(response.data["data"]["activated_stay_ids"]), 2)

        booking_stays = list(Stay.objects.filter(booking=booking).order_by("id"))
        self.assertEqual(len(booking_stays), 2)
        self.assertCountEqual([s.room_id for s in booking_stays], [target_room_one.id, target_room_two.id])
        self.assertTrue(all(s.status == "active" for s in booking_stays))

        base_room.refresh_from_db()
        target_room_one.refresh_from_db()
        target_room_two.refresh_from_db()
        self.assertEqual(base_room.status, "available")
        self.assertIsNone(base_room.current_guest)
        self.assertEqual(target_room_one.status, "occupied")
        self.assertEqual(target_room_two.status, "occupied")
        self.assertEqual(target_room_one.current_guest_id, guest.id)
        self.assertEqual(target_room_two.current_guest_id, guest.id)

    def test_verify_checkin_creates_booking_for_unbooked_pending_stays(self):
        guest = Guest.objects.create(
            full_name="No Booking Verify Guest",
            whatsapp_number="+15550000666",
            status="pending_checkin",
        )
        now = timezone.now()
        second_room = Room.objects.create(
            hotel=self.hotel,
            room_number="117",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        self.room.status = "occupied"
        self.room.current_guest = guest
        self.room.save(update_fields=["status", "current_guest"])

        primary_stay = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=now,
            check_out_date=now + timedelta(days=1),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )
        secondary_stay = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=second_room,
            check_in_date=now,
            check_out_date=now + timedelta(days=1),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )

        response = self.client.patch(
            f"/api/guest/stay-management/{primary_stay.id}/verify-checkin/",
            {"register_number": "REG-NO-BOOKING-001"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])

        primary_stay.refresh_from_db()
        secondary_stay.refresh_from_db()
        self.assertIsNotNone(primary_stay.booking_id)
        self.assertEqual(primary_stay.booking_id, secondary_stay.booking_id)
        self.assertEqual(primary_stay.status, "active")
        self.assertEqual(secondary_stay.status, "active")

        booking = Booking.objects.get(id=primary_stay.booking_id)
        self.assertEqual(booking.primary_guest_id, guest.id)
        self.assertEqual(booking.status, "confirmed")

    def test_verify_checkin_room_ids_expansion_without_booking_uses_created_booking(self):
        guest = Guest.objects.create(
            full_name="No Booking Expansion Guest",
            whatsapp_number="+15550000667",
            status="pending_checkin",
        )
        now = timezone.now()

        occupied_source_room = self.room
        occupied_source_room.status = "occupied"
        occupied_source_room.current_guest = guest
        occupied_source_room.save(update_fields=["status", "current_guest"])

        target_room_one = Room.objects.create(
            hotel=self.hotel,
            room_number="118",
            category=self.room.category,
            floor=1,
            status="available",
        )
        target_room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="119",
            category=self.room.category,
            floor=1,
            status="available",
        )

        primary_stay = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=occupied_source_room,
            check_in_date=now,
            check_out_date=now + timedelta(days=1),
            status="pending",
            identity_verified=False,
            documents_uploaded=True,
        )

        response = self.client.patch(
            f"/api/guest/stay-management/{primary_stay.id}/verify-checkin/",
            {"register_number": "REG-NO-BOOKING-002", "room_ids": [target_room_one.id, target_room_two.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["data"]["activated_stay_ids"]), 2)

        stays = list(Stay.objects.filter(guest=guest, hotel=self.hotel).order_by("id"))
        self.assertEqual(len(stays), 2)
        self.assertIsNotNone(stays[0].booking_id)
        self.assertEqual(stays[0].booking_id, stays[1].booking_id)
        self.assertCountEqual([s.room_id for s in stays], [target_room_one.id, target_room_two.id])
        self.assertTrue(all(s.status == "active" for s in stays))

    def test_checked_in_users_grouped_returns_one_row_per_guest_with_billing(self):
        now = timezone.now()
        guest = Guest.objects.create(
            full_name="Grouped Guest",
            whatsapp_number="+15550000222",
            status="checked_in",
        )
        room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="107",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        self.room.status = "occupied"
        self.room.current_guest = guest
        self.room.save(update_fields=["status", "current_guest"])

        stay_one = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=1),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        stay_two = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=room_two,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=2),
            actual_check_in=now - timedelta(days=1),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )

        response = self.client.get(
            "/api/guest/stay-management/checked-in-users-grouped/",
            {"page": 1, "page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["count"], 1)
        grouped_row = response.data["data"]["results"][0]
        self.assertEqual(grouped_row["guest"]["id"], guest.id)
        self.assertTrue(grouped_row["is_checked_in"])
        self.assertCountEqual(grouped_row["active_stay_ids"], [stay_one.id, stay_two.id])
        self.assertEqual(len(grouped_row["stays"]), 2)
        self.assertIn("billing", grouped_row)
        self.assertIn("current_bill_total", grouped_row["billing"])
        self.assertIn("expected_bill_total", grouped_row["billing"])
        self.assertEqual(len(grouped_row["billing"]["rooms"]), 2)

    def test_stays_history_grouped_includes_completed_history_for_search(self):
        now = timezone.now()
        guest = Guest.objects.create(
            full_name="History Guest",
            whatsapp_number="+15550000223",
            status="checked_in",
        )
        booking = Booking.objects.create(
            hotel=self.hotel,
            primary_guest=guest,
            check_in_date=now - timedelta(days=3),
            check_out_date=now + timedelta(days=1),
            status="confirmed",
            total_amount=0,
            guest_names=[guest.full_name],
        )
        room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="112",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        self.room.status = "occupied"
        self.room.current_guest = guest
        self.room.save(update_fields=["status", "current_guest"])

        active_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=1),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        completed_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=room_two,
            check_in_date=now - timedelta(days=3),
            check_out_date=now - timedelta(days=1),
            actual_check_in=now - timedelta(days=3),
            actual_check_out=now - timedelta(days=1),
            status="completed",
            identity_verified=True,
            documents_uploaded=True,
        )

        active_response = self.client.get("/api/guest/stay-management/checked-in-users-grouped/")
        self.assertEqual(active_response.status_code, 200)
        active_row = active_response.data["data"]["results"][0]
        self.assertEqual(len(active_row["stays"]), 1)
        self.assertEqual(active_row["stays"][0]["id"], active_stay.id)

        history_response = self.client.get(
            "/api/guest/stay-management/stays-history-grouped/",
            {"search": "History Guest", "page": 1, "page_size": 10},
        )
        self.assertEqual(history_response.status_code, 200)
        self.assertTrue(history_response.data["success"])
        self.assertEqual(history_response.data["data"]["count"], 1)
        history_row = history_response.data["data"]["results"][0]
        self.assertCountEqual(
            [stay["id"] for stay in history_row["stays"]],
            [active_stay.id, completed_stay.id],
        )
        self.assertCountEqual(history_row["active_stay_ids"], [active_stay.id])
        self.assertCountEqual(history_row["completed_stay_ids"], [completed_stay.id])
        self.assertEqual(history_row["booking"]["id"], booking.id)

    def test_stays_history_grouped_returns_separate_rows_for_separate_bookings_same_guest(self):
        now = timezone.now()
        guest = Guest.objects.create(
            full_name="Two Booking Guest",
            whatsapp_number="+15550000224",
            status="checked_out",
        )
        room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="120",
            category=self.room.category,
            floor=1,
            status="available",
        )
        booking_one = Booking.objects.create(
            hotel=self.hotel,
            primary_guest=guest,
            check_in_date=now - timedelta(days=7),
            check_out_date=now - timedelta(days=5),
            status="completed",
            total_amount=1000,
            guest_names=[guest.full_name],
        )
        booking_two = Booking.objects.create(
            hotel=self.hotel,
            primary_guest=guest,
            check_in_date=now - timedelta(days=2),
            check_out_date=now + timedelta(days=1),
            status="confirmed",
            total_amount=1200,
            guest_names=[guest.full_name],
        )

        stay_one = Stay.objects.create(
            booking=booking_one,
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=booking_one.check_in_date,
            check_out_date=booking_one.check_out_date,
            actual_check_in=booking_one.check_in_date,
            actual_check_out=booking_one.check_out_date,
            status="completed",
            identity_verified=True,
            documents_uploaded=True,
        )
        stay_two = Stay.objects.create(
            booking=booking_two,
            hotel=self.hotel,
            guest=guest,
            room=room_two,
            check_in_date=booking_two.check_in_date,
            check_out_date=booking_two.check_out_date,
            actual_check_in=booking_two.check_in_date,
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )

        response = self.client.get(
            "/api/guest/stay-management/stays-history-grouped/",
            {"search": "Two Booking Guest", "page": 1, "page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["count"], 2)
        results = response.data["data"]["results"]
        returned_booking_ids = {row["booking"]["id"] for row in results}
        self.assertSetEqual(returned_booking_ids, {booking_one.id, booking_two.id})

        booking_map = {row["booking"]["id"]: row for row in results}
        self.assertEqual(len(booking_map[booking_one.id]["stays"]), 1)
        self.assertEqual(booking_map[booking_one.id]["stays"][0]["id"], stay_one.id)
        self.assertEqual(len(booking_map[booking_two.id]["stays"]), 1)
        self.assertEqual(booking_map[booking_two.id]["stays"][0]["id"], stay_two.id)

    def test_stays_history_grouped_returns_one_row_for_multi_room_booking(self):
        now = timezone.now()
        guest = Guest.objects.create(
            full_name="Multi Room History Guest",
            whatsapp_number="+15550000225",
            status="checked_in",
        )
        room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="121",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        room_three = Room.objects.create(
            hotel=self.hotel,
            room_number="122",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        self.room.status = "occupied"
        self.room.current_guest = guest
        self.room.save(update_fields=["status", "current_guest"])

        booking = Booking.objects.create(
            hotel=self.hotel,
            primary_guest=guest,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=2),
            status="confirmed",
            total_amount=0,
            guest_names=[guest.full_name, guest.full_name, guest.full_name],
        )
        stay_one = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=booking.check_in_date,
            check_out_date=booking.check_out_date,
            actual_check_in=booking.check_in_date,
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        stay_two = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=room_two,
            check_in_date=booking.check_in_date,
            check_out_date=booking.check_out_date,
            actual_check_in=booking.check_in_date,
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        stay_three = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=room_three,
            check_in_date=booking.check_in_date,
            check_out_date=booking.check_out_date,
            actual_check_in=booking.check_in_date,
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )

        response = self.client.get("/api/guest/stay-management/stays-history-grouped/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["count"], 1)
        row = response.data["data"]["results"][0]
        self.assertEqual(row["booking"]["id"], booking.id)
        self.assertEqual(len(row["stays"]), 3)
        self.assertCountEqual([stay["id"] for stay in row["stays"]], [stay_one.id, stay_two.id, stay_three.id])

    def test_stays_history_grouped_search_supports_room_and_register_number(self):
        now = timezone.now()
        guest = Guest.objects.create(
            full_name="Search History Guest",
            whatsapp_number="+15550000226",
            status="checked_in",
        )
        target_room = Room.objects.create(
            hotel=self.hotel,
            room_number="A-701",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        booking = Booking.objects.create(
            hotel=self.hotel,
            primary_guest=guest,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=1),
            status="confirmed",
            total_amount=0,
            guest_names=[guest.full_name],
        )
        target_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=target_room,
            register_number="REG-HISTORY-777",
            check_in_date=booking.check_in_date,
            check_out_date=booking.check_out_date,
            actual_check_in=booking.check_in_date,
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        sibling_room = Room.objects.create(
            hotel=self.hotel,
            room_number="A-702",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        sibling_stay = Stay.objects.create(
            booking=booking,
            hotel=self.hotel,
            guest=guest,
            room=sibling_room,
            register_number="REG-HISTORY-778",
            check_in_date=booking.check_in_date,
            check_out_date=booking.check_out_date,
            actual_check_in=booking.check_in_date,
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )

        other_guest = Guest.objects.create(
            full_name="Other History Guest",
            whatsapp_number="+15550000227",
            status="checked_in",
        )
        other_booking = Booking.objects.create(
            hotel=self.hotel,
            primary_guest=other_guest,
            check_in_date=now - timedelta(days=2),
            check_out_date=now + timedelta(days=2),
            status="confirmed",
            total_amount=0,
            guest_names=[other_guest.full_name],
        )
        Stay.objects.create(
            booking=other_booking,
            hotel=self.hotel,
            guest=other_guest,
            room=self.room,
            register_number="REG-OTHER-001",
            check_in_date=other_booking.check_in_date,
            check_out_date=other_booking.check_out_date,
            actual_check_in=other_booking.check_in_date,
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )

        by_room = self.client.get(
            "/api/guest/stay-management/stays-history-grouped/",
            {"search": "A-701"},
        )
        self.assertEqual(by_room.status_code, 200)
        self.assertEqual(by_room.data["data"]["count"], 1)
        self.assertEqual(by_room.data["data"]["results"][0]["booking"]["id"], booking.id)
        self.assertCountEqual(
            [stay["id"] for stay in by_room.data["data"]["results"][0]["stays"]],
            [target_stay.id, sibling_stay.id],
        )

        by_register = self.client.get(
            "/api/guest/stay-management/stays-history-grouped/",
            {"search": "REG-HISTORY-777"},
        )
        self.assertEqual(by_register.status_code, 200)
        self.assertEqual(by_register.data["data"]["count"], 1)
        self.assertEqual(by_register.data["data"]["results"][0]["booking"]["id"], booking.id)
        self.assertCountEqual(
            [stay["id"] for stay in by_register.data["data"]["results"][0]["stays"]],
            [target_stay.id, sibling_stay.id],
        )

    @patch("guest.views.send_whatsapp_list_message")
    @patch("guest.views.send_whatsapp_text_message")
    @patch("guest.views.send_whatsapp_image_with_link")
    @patch("guest.views.process_template")
    def test_checkout_bulk_skips_messages_when_guest_still_has_active_stays(
        self,
        mock_process_template,
        mock_send_image,
        mock_send_text,
        mock_send_list,
    ):
        guest = Guest.objects.create(
            full_name="Bulk Checkout Guest",
            whatsapp_number="+15550000333",
            status="checked_in",
        )
        now = timezone.now()
        room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="108",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        room_three = Room.objects.create(
            hotel=self.hotel,
            room_number="109",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        self.room.status = "occupied"
        self.room.current_guest = guest
        self.room.save(update_fields=["status", "current_guest"])

        checkout_stay = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=now - timedelta(days=2),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=2),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        # Guest still has one active stay after partial checkout.
        active_stay = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=room_two,
            check_in_date=now - timedelta(days=2),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=2),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=room_three,
            check_in_date=now - timedelta(days=2),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=2),
            status="completed",
            identity_verified=True,
            documents_uploaded=True,
        )

        response = self.client.post(
            "/api/guest/stay-management/checkout-bulk/",
            {"guest_id": guest.id, "stay_ids": [checkout_stay.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        payload = response.data["data"]
        self.assertEqual(payload["guest_id"], guest.id)
        self.assertEqual(payload["checked_out_stay_ids"], [checkout_stay.id])
        self.assertTrue(payload["guest_has_active_stays"])
        self.assertFalse(payload["checkout_message_sent"])
        self.assertFalse(payload["feedback_triggered"])

        guest.refresh_from_db()
        checkout_stay.refresh_from_db()
        active_stay.refresh_from_db()
        self.assertEqual(guest.status, "checked_in")
        self.assertEqual(checkout_stay.status, "completed")
        self.assertEqual(active_stay.status, "active")

        mock_process_template.assert_not_called()
        mock_send_image.assert_not_called()
        mock_send_text.assert_not_called()
        mock_send_list.assert_not_called()

    @patch("guest.views.send_whatsapp_list_message")
    @patch("guest.views.send_whatsapp_text_message")
    @patch("guest.views.send_whatsapp_image_with_link")
    @patch("guest.views.process_template")
    def test_checkout_bulk_sends_messages_when_last_active_stays_checkout(
        self,
        mock_process_template,
        mock_send_image,
        mock_send_text,
        mock_send_list,
    ):
        mock_process_template.return_value = {
            "success": True,
            "processed_content": "Thanks for staying!",
            "media_url": "",
        }
        guest = Guest.objects.create(
            full_name="Final Checkout Guest",
            whatsapp_number="+15550000444",
            status="checked_in",
        )
        now = timezone.now()
        room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="110",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest,
        )
        self.room.status = "occupied"
        self.room.current_guest = guest
        self.room.save(update_fields=["status", "current_guest"])

        stay_one = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=now - timedelta(days=2),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=2),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        stay_two = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=room_two,
            check_in_date=now - timedelta(days=2),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=2),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )

        response = self.client.post(
            "/api/guest/stay-management/checkout-bulk/",
            {"guest_id": guest.id, "stay_ids": [stay_one.id, stay_two.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.data["data"]
        self.assertFalse(payload["guest_has_active_stays"])
        self.assertTrue(payload["checkout_message_sent"])
        self.assertTrue(payload["feedback_triggered"])
        self.assertCountEqual(payload["checked_out_stay_ids"], [stay_one.id, stay_two.id])

        guest.refresh_from_db()
        stay_one.refresh_from_db()
        stay_two.refresh_from_db()
        self.room.refresh_from_db()
        room_two.refresh_from_db()

        self.assertEqual(guest.status, "checked_out")
        self.assertEqual(stay_one.status, "completed")
        self.assertEqual(stay_two.status, "completed")
        self.assertEqual(self.room.status, "cleaning")
        self.assertEqual(room_two.status, "cleaning")
        self.assertIsNone(self.room.current_guest)
        self.assertIsNone(room_two.current_guest)

        mock_process_template.assert_called_once()
        mock_send_text.assert_called_once()
        mock_send_list.assert_called_once()

        feedback_conversations = Conversation.objects.filter(
            guest=guest,
            hotel=self.hotel,
            conversation_type="feedback",
        )
        self.assertTrue(feedback_conversations.exists())

    def test_checkout_bulk_rejects_stays_from_different_guest(self):
        now = timezone.now()
        guest_one = Guest.objects.create(
            full_name="Guest One",
            whatsapp_number="+15550000445",
            status="checked_in",
        )
        guest_two = Guest.objects.create(
            full_name="Guest Two",
            whatsapp_number="+15550000446",
            status="checked_in",
        )
        room_two = Room.objects.create(
            hotel=self.hotel,
            room_number="111",
            category=self.room.category,
            floor=1,
            status="occupied",
            current_guest=guest_two,
        )
        self.room.status = "occupied"
        self.room.current_guest = guest_one
        self.room.save(update_fields=["status", "current_guest"])

        stay_one = Stay.objects.create(
            hotel=self.hotel,
            guest=guest_one,
            room=self.room,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=1),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )
        stay_two = Stay.objects.create(
            hotel=self.hotel,
            guest=guest_two,
            room=room_two,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=1),
            status="active",
            identity_verified=True,
            documents_uploaded=True,
        )

        response = self.client.post(
            "/api/guest/stay-management/checkout-bulk/",
            {"guest_id": guest_one.id, "stay_ids": [stay_one.id, stay_two.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("All stays must belong to the provided guest_id", response.data["message"])

    def test_checkout_bulk_rejects_non_active_stay(self):
        now = timezone.now()
        guest = Guest.objects.create(
            full_name="Guest Non Active",
            whatsapp_number="+15550000447",
            status="checked_in",
        )
        self.room.status = "occupied"
        self.room.current_guest = guest
        self.room.save(update_fields=["status", "current_guest"])

        stay = Stay.objects.create(
            hotel=self.hotel,
            guest=guest,
            room=self.room,
            check_in_date=now - timedelta(days=1),
            check_out_date=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=1),
            status="completed",
            identity_verified=True,
            documents_uploaded=True,
        )

        response = self.client.post(
            "/api/guest/stay-management/checkout-bulk/",
            {"guest_id": guest.id, "stay_ids": [stay.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("All stays must be active", response.data["message"])
