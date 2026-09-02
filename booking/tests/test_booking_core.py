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
        self.third_user = User.objects.create_user(
            username="third@example.com",
            email="third@example.com",
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
        self.other_station = Station.objects.create(name="Other Station")

    def add_weekday_schedule(self, target_date, start="09:00", end="18:00", station=None):
        StationWeeklySchedule.objects.create(
            station=station or self.station,
            weekday=target_date.weekday(),
            work_start=time.fromisoformat(start),
            work_end=time.fromisoformat(end),
        )

    def create_appointment(self, station=None, user=None, car=None, start_hour=10):
        station = station or self.station
        user = user or self.user
        car = car or self.car
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target, station=station)
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, start_hour, 0))
        return Appointment.objects.create(
            user=user,
            car=car,
            station=station,
            start=start,
            end=start + timedelta(minutes=30),
            name="Client",
            phone="123",
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

    def test_car_by_plate_api_requires_station_id(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.client.login(username="other@example.com", password="test-password")

        url = reverse("car_by_plate_api")
        response = self.client.get(url, {"plate": self.car.plate_number})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "plate and station_id required")

    def test_car_by_plate_api_forbids_regular_client(self):
        self.client.login(username="client@example.com", password="test-password")

        url = reverse("car_by_plate_api")
        response = self.client.get(
            url,
            {"plate": self.car.plate_number, "station_id": self.station.id},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "forbidden")

    def test_car_by_plate_api_allows_station_staff_for_station_client(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.create_appointment()

        self.client.login(username="other@example.com", password="test-password")
        url = reverse("car_by_plate_api")
        response = self.client.get(
            url,
            {"plate": self.car.plate_number, "station_id": self.station.id},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertFalse(data["ambiguous"])
        self.assertEqual(len(data["matches"]), 1)
        self.assertEqual(data["matches"][0]["id"], self.car.id)
        self.assertEqual(data["matches"][0]["brand"], "Test")
        self.assertEqual(data["matches"][0]["model"], "Passenger")

    def test_car_by_plate_api_blocks_car_from_another_station(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.create_appointment(station=self.other_station)

        self.client.login(username="other@example.com", password="test-password")
        url = reverse("car_by_plate_api")
        response = self.client.get(
            url,
            {"plate": self.car.plate_number, "station_id": self.station.id},
        )

        self.assertEqual(response.status_code, 404)

    def test_car_by_plate_api_blocks_staff_of_another_station(self):
        StationStaff.objects.create(
            station=self.other_station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.client.login(username="other@example.com", password="test-password")

        url = reverse("car_by_plate_api")
        response = self.client.get(
            url,
            {"plate": self.car.plate_number, "station_id": self.station.id},
        )

        self.assertEqual(response.status_code, 403)

    @patch("booking.views.station_appointment_create.notify_client_booked")
    @patch("booking.views.station_appointment_create.notify_station_staff_booked")
    def test_station_staff_can_create_manual_appointment(self, notify_staff, notify_client):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.create_appointment(start_hour=9)
        self.client.login(username="other@example.com", password="test-password")
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target, "09:00", "18:00")

        url = reverse("station_appointment_create", kwargs={"station_id": self.station.id})
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
        appointment = Appointment.objects.filter(station=self.station, car=self.car).order_by("-id").first()
        self.assertEqual(appointment.user, self.car.owner)
        self.assertEqual(appointment.name, "client@example.com")
        self.assertIsNone(appointment.phone)
        self.assertEqual(appointment.start, timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0)))
        self.assertEqual(appointment.end, appointment.start + timedelta(minutes=30))
        notify_staff.assert_called_once_with(appointment)
        notify_client.assert_called_once_with(appointment)

    def test_client_sees_only_own_appointments(self):
        own = self.create_appointment(station=self.station)
        foreign = self.create_appointment(station=self.other_station, user=self.other_user, car=self.other_car, start_hour=11)

        self.client.login(username="client@example.com", password="test-password")
        response = self.client.get(reverse("cabinet_appointments"))

        self.assertEqual(response.status_code, 200)
        appointments = list(response.context["appointments"])
        self.assertIn(own, appointments)
        self.assertNotIn(foreign, appointments)

    def test_client_cannot_cancel_foreign_appointment(self):
        foreign = self.create_appointment(user=self.other_user, car=self.other_car)

        self.client.login(username="client@example.com", password="test-password")
        response = self.client.post(
            reverse("cabinet_cancel_appointment", kwargs={"pk": foreign.pk})
        )

        self.assertEqual(response.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, "BOOKED")

    def test_operator_cannot_access_other_station_appointments(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.client.login(username="other@example.com", password="test-password")

        response = self.client.get(
            reverse("station_appointments", kwargs={"station_id": self.other_station.id})
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )

    def test_operator_cannot_change_foreign_station_appointment_status(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        foreign = self.create_appointment(station=self.other_station)

        self.client.login(username="other@example.com", password="test-password")
        response = self.client.post(
            reverse(
                "station_appointment_status",
                kwargs={"station_id": self.other_station.id, "pk": foreign.pk},
            ),
            {"status": "DONE"},
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, "BOOKED")

    def test_operator_cannot_open_foreign_station_appointment_detail(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        foreign = self.create_appointment(station=self.other_station)

        self.client.login(username="other@example.com", password="test-password")
        response = self.client.get(
            reverse(
                "station_appointment_detail",
                kwargs={"station_id": self.other_station.id, "pk": foreign.pk},
            )
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )

    def test_operator_cannot_manage_station_staff(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.client.login(username="other@example.com", password="test-password")

        response = self.client.get(
            reverse("station_staff", kwargs={"station_id": self.station.id})
        )

        self.assertRedirects(
            response,
            reverse("station_dashboard", kwargs={"station_id": self.station.id}),
            fetch_redirect_response=False,
        )

    def test_station_owner_can_manage_station_staff(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.user,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        self.client.login(username="client@example.com", password="test-password")

        response = self.client.get(
            reverse("station_staff", kwargs={"station_id": self.station.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_operator_cannot_change_foreign_station_status_even_with_valid_post(self):
        StationStaff.objects.create(
            station=self.station,
            user=self.other_user,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        foreign = self.create_appointment(station=self.other_station)

        self.client.login(username="other@example.com", password="test-password")
        response = self.client.post(
            reverse(
                "station_appointment_status",
                kwargs={"station_id": self.other_station.id, "pk": foreign.pk},
            ),
            {"status": "CANCELLED", "comment": "attempt"},
        )

        self.assertEqual(response.status_code, 302)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, "BOOKED")

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
            conflicting.save()
