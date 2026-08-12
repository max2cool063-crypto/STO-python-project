from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Appointment,
    Brand,
    Car,
    CarModel,
    Station,
    StationSchedule,
    StationStaff,
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
        self.station = Station.objects.create(name="Test Station")

    def add_weekday_schedule(self, target_date, start="09:00", end="18:00"):
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target_date.weekday(),
            work_start=time.fromisoformat(start),
            work_end=time.fromisoformat(end),
        )

    def test_station_default_slot_duration_is_30_minutes(self):
        self.assertEqual(self.station.slot_duration, 30)

    def test_passenger_appointment_duration_is_30_minutes(self):
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target, "09:00", "18:00")
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))

        appointment = Appointment.objects.create(
            user=self.user,
            car=self.car,
            station=self.station,
            start=start,
            end=start + timedelta(hours=1),
            name="Client",
            phone="123",
        )

        self.assertEqual(appointment.end, start + timedelta(minutes=30))

    def test_truck_requires_60_minutes_and_starts_every_30_minutes(self):
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target, "09:00", "13:00")

        slots = self.station.get_available_slots(target, vehicle_type="TRUCK")

        expected = [
            ("09:00", "10:00"),
            ("09:30", "10:30"),
            ("10:00", "11:00"),
            ("10:30", "11:30"),
            ("11:00", "12:00"),
            ("11:30", "12:30"),
            ("12:00", "13:00"),
        ]
        self.assertEqual(
            [(slot["start"][11:16], slot["end"][11:16]) for slot in slots],
            expected,
        )

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
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target)

        url = reverse("station_slots_api", kwargs={"station_id": self.station.id})
        response = self.client.get(url, {"date": target.isoformat(), "car": self.other_car.id})

        self.assertEqual(response.status_code, 404)

    def test_car_by_plate_api_forbids_regular_client(self):
        self.client.login(username="client@example.com", password="test-password")

        url = reverse("car_by_plate_api")
        response = self.client.get(url, {"plate": self.car.plate_number})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "forbidden")

    def test_car_by_plate_api_allows_station_staff(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.client.login(username="other@example.com", password="test-password")

        url = reverse("car_by_plate_api")
        response = self.client.get(url, {"plate": self.car.plate_number})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.car.id)
        self.assertEqual(data["brand"], "Test")
        self.assertEqual(data["model"], "Passenger")

    @patch("booking.views.station_appointment_create.notify_client_booked")
    @patch("booking.views.station_appointment_create.notify_station_staff_booked")
    def test_station_staff_can_create_manual_appointment(self, notify_staff, notify_client):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.client.login(username="other@example.com", password="test-password")
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target, "09:00", "18:00")

        url = reverse(
            "station_appointment_create",
            kwargs={"station_id": self.station.id},
        )
        response = self.client.post(
            url,
            {
                "car_id": str(self.car.id),
                "start": "2099-02-03T10:00",
                "client_name": "Test Client",
                "client_phone": "+79990000000",
            },
        )

        self.assertRedirects(
            response,
            reverse("station_appointments", kwargs={"station_id": self.station.id}),
        )
        appointment = Appointment.objects.get(station=self.station, car=self.car)
        self.assertEqual(appointment.user, self.car.owner)
        self.assertEqual(appointment.name, "Test Client")
        self.assertEqual(appointment.start, timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0)))
        self.assertEqual(appointment.end, appointment.start + timedelta(minutes=30))
        notify_staff.assert_called_once_with(appointment)
        notify_client.assert_called_once_with(appointment)

    def test_appointment_rejects_conflicting_time(self):
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target)
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))

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
            start=start + timedelta(minutes=15),
            end=start + timedelta(minutes=90),
            name="Client",
            phone="123",
        )

        with self.assertRaises(ValidationError):
            conflicting.full_clean()

    def test_appointment_save_recalculates_end_for_truck(self):
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target, "09:00", "18:00")
        truck = Car.objects.create(
            owner=self.user,
            model=self.truck_model,
            plate_number="C333CC",
        )
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))

        appointment = Appointment.objects.create(
            user=self.user,
            car=truck,
            station=self.station,
            start=start,
            end=start + timedelta(minutes=1),
            name="Client",
            phone="123",
        )

        self.assertEqual(appointment.end, start + timedelta(hours=1))

    def test_cancelled_appointment_does_not_block_slot(self):
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target)
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))

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
