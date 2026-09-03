from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class StationTimezoneTests(TestCase):
    def setUp(self):
        self.samars_station = Station.objects.create(
            name="Самара",
            latitude=53.1959,
            longitude=50.1002,
        )
        self.moscow_station = Station.objects.create(
            name="Москва",
            latitude=55.7558,
            longitude=37.6173,
        )

    def test_timezone_is_detected_from_coordinates(self):
        self.assertEqual(self.samars_station.timezone, "Europe/Samara")
        self.assertEqual(self.moscow_station.timezone, "Europe/Moscow")

    def test_manual_timezone_is_preserved_when_coordinates_change(self):
        self.samars_station.timezone = "Asia/Yekaterinburg"
        self.samars_station.latitude = 55.0
        self.samars_station.longitude = 60.0
        self.samars_station.save()
        self.samars_station.refresh_from_db()
        self.assertEqual(self.samars_station.timezone, "Asia/Yekaterinburg")

    def test_available_slots_use_station_local_current_time(self):
        selected_date = date(2026, 9, 3)
        StationWeeklySchedule.objects.create(
            station=self.samars_station,
            weekday=selected_date.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )

        # 08:01 UTC = 12:01 in Samara. 12:00 must be past, 12:30 future.
        mocked_now = timezone.datetime(2026, 9, 3, 8, 1, tzinfo=timezone.utc)
        with patch("booking.timezones.timezone.now", return_value=mocked_now):
            slots = self.samars_station.get_available_slots(selected_date)

        starts = [slot["start"] for slot in slots]
        self.assertNotIn("2026-09-03T12:00:00+04:00", starts)
        self.assertIn("2026-09-03T12:30:00+04:00", starts)

    def test_appointment_validation_uses_station_local_calendar(self):
        selected_date = date(2026, 9, 3)
        StationWeeklySchedule.objects.create(
            station=self.samars_station,
            weekday=selected_date.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        user = User.objects.create_user(username="tz-client")
        brand = Brand.objects.create(name="TZ Brand")
        model = CarModel.objects.create(brand=brand, name="TZ Model")
        car = Car.objects.create(owner=user, model=model, plate_number="А123АА63")

        start = self.samars_station.make_local_datetime(selected_date, time(9, 30))
        from booking.models import Appointment
        appointment = Appointment.objects.create(
            station=self.samars_station,
            user=user,
            car=car,
            start=start,
            end=start,
            name="Тест",
        )

        self.assertEqual(appointment.local_start.isoformat(), "2026-09-03T09:30:00+04:00")

    def test_calendar_defaults_to_station_local_today(self):
        owner = User.objects.create_user(username="tz-owner", password="Strong-owner-123!")
        StationStaff.objects.create(
            station=self.samars_station,
            user=owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        mocked_now = timezone.datetime(2026, 9, 3, 20, 30, tzinfo=timezone.utc)
        self.client.login(username="tz-owner", password="Strong-owner-123!")

        with patch("booking.timezones.timezone.now", return_value=mocked_now):
            response = self.client.get(
                reverse("station_day_calendar", kwargs={"station_id": self.samars_station.pk})
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["today"], date(2026, 9, 4))
