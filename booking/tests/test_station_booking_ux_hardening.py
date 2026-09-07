from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Station, StationStaff, StationWeeklySchedule


class StationBookingUxHardeningTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(username="operator-ux", password="test-password")
        self.station = Station.objects.create(name="UX Station", slot_duration=30)
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.client.login(username="operator-ux", password="test-password")

    def test_station_staff_can_request_truck_slots_before_new_car_exists(self):
        response = self.client.get(
            reverse("station_slots_api", kwargs={"station_id": self.station.pk}),
            {"date": "2099-02-03", "vehicle_type": "TRUCK"},
        )

        self.assertEqual(response.status_code, 200)
        slots = response.json()["slots"]
        self.assertTrue(slots)
        self.assertEqual(slots[0]["start"][:16], "2099-02-03T09:00")
        self.assertEqual(slots[0]["end"][:16], "2099-02-03T10:00")

    def test_regular_user_cannot_override_slot_duration_with_vehicle_type(self):
        regular = User.objects.create_user(username="regular-ux", password="test-password")
        self.client.logout()
        self.client.login(username=regular.username, password="test-password")

        response = self.client.get(
            reverse("station_slots_api", kwargs={"station_id": self.station.pk}),
            {"date": "2099-02-03", "vehicle_type": "TRUCK"},
        )

        self.assertEqual(response.status_code, 200)
        slots = response.json()["slots"]
        self.assertTrue(slots)
        self.assertEqual(slots[0]["end"][:16], "2099-02-03T09:30")
