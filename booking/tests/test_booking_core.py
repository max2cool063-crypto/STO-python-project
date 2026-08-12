from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Appointment,
    Brand,
    Car,
    CarModel,
    Station,
    StationSchedule,
    StationWeeklySchedule,
)


class BookingCoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="test-password",
        )
        self.brand = Brand.objects.create(name="Test")
        self.car_model = CarModel.objects.create(
            brand=self.brand,
            name="Passenger",
            vehicle_type="CAR",
        )
        self.truck_model = CarModel.objects.create(
            brand=self.brand,
            name="Truck",
            vehicle_type="TRUCK",
        )
        self.car = Car.objects.create(
            owner=self.user,
            model=self.car_model,
            plate_number="A111AA",
        )
        self.other_car = Car.objects.create(
            owner=self.other_user,
            model=self.car_model,
            plate_number="B222BB",
        )
        self.station = Station.objects.create(
            name="Test Station",
            slot_duration=60,
        )

    def add_weekday_schedule(self, target_date, start="09:00", end="18:00"):
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target_date.weekday(),
            work_start=time.fromisoformat(start),
            work_end=time.fromisoformat(end),
        )

    def test_truck_requires_two_slots(self):
        target = date(2099, 1, 5)
        self.add_weekday_schedule(target, "09:00", "13:00")

        slots = self.station.get_available_slots(target, vehicle_type="TRUCK")

        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0]["start"][11:16], "09:00")
        self.assertEqual(slots[0]["end"][11:16], "11:00")
        self.assertEqual(slots[1]["start"][11:16], "10:00")
        self.assertEqual(slots[1]["end"][11:16], "12:00")

    def test_holiday_without_explicit_schedule_is_closed(self):
        target = date(2026, 1, 1)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )

        with patch("holidays.Russia", return_value={target: "Holiday"}):
            self.assertEqual(self.station.get_working_hours(target), (None, None))
            self.assertEqual(self.station.get_available_slots(target), [])

    def test_explicit_schedule_overrides_holiday(self):
        target = date(2026, 1, 1)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        StationSchedule.objects.create(
            station=self.station,
            date=target,
            work_start=time(10, 0),
            work_end=time(14, 0),
        )

        with patch("holidays.Russia", return_value={target: "Holiday"}):
            self.assertEqual(
                self.station.get_working_hours(target),
                (time(10, 0), time(14, 0)),
            )

    def test_station_slots_api_rejects_foreign_car(self):
        self.client.login(username="client@example.com", password="test-password")
        target = date(2099, 1, 5)
        self.add_weekday_schedule(target)

        url = reverse("station_slots_api", kwargs={"station_id": self.station.id})
        response = self.client.get(url, {"date": target.isoformat(), "car": self.other_car.id})

        self.assertEqual(response.status_code, 404)

    def test_appointment_rejects_conflicting_time(self):
        target = date(2099, 1, 5)
        self.add_weekday_schedule(target)
        start = timezone.make_aware(timezone.datetime(2099, 1, 5, 10, 0))

        Appointment.objects.create(
            user=self.user,
            car=self.car,
            station=self.station,
            start=start,
            end=start + timedelta(hours=1),
            name="Client",
            phone="123",
        )

        conflicting = Appointment(
            user=self.user,
            car=self.car,
            station=self.station,
            start=start + timedelta(minutes=30),
            end=start + timedelta(minutes=90),
            name="Client",
            phone="123",
        )

        with self.assertRaises(ValidationError):
            conflicting.full_clean()

    def test_appointment_save_recalculates_end_for_truck(self):
        target = date(2099, 1, 5)
        self.add_weekday_schedule(target, "09:00", "18:00")
        truck = Car.objects.create(
            owner=self.user,
            model=self.truck_model,
            plate_number="C333CC",
        )
        start = timezone.make_aware(timezone.datetime(2099, 1, 5, 10, 0))

        appointment = Appointment.objects.create(
            user=self.user,
            car=truck,
            station=self.station,
            start=start,
            end=start + timedelta(minutes=1),
            name="Client",
            phone="123",
        )

        self.assertEqual(appointment.end, start + timedelta(hours=2))

    def test_cancelled_appointment_does_not_block_slot(self):
        target = date(2099, 1, 5)
        self.add_weekday_schedule(target)
        start = timezone.make_aware(timezone.datetime(2099, 1, 5, 10, 0))

        Appointment.objects.create(
            user=self.user,
            car=self.car,
            station=self.station,
            start=start,
            end=start + timedelta(hours=1),
            name="Client",
            phone="123",
            status="CANCELLED",
        )

        slots = self.station.get_available_slots(target, vehicle_type="CAR")
        starts = {slot["start"][11:16] for slot in slots}
        self.assertIn("10:00", starts)
