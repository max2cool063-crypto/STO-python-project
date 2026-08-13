from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Appointment,
    Brand,
    Car,
    CarModel,
    Station,
    StationStaff,
    StationWeeklySchedule,
)


class IdorRegressionTests(TestCase):
    TEST_DATE = datetime(2099, 3, 3).date()

    def setUp(self):
        self.user = User.objects.create_user(username="u1@example.com", password="pass")
        self.other_user = User.objects.create_user(username="u2@example.com", password="pass")
        self.operator = User.objects.create_user(username="op@example.com", password="pass")
        self.brand = Brand.objects.create(name="Test")
        self.model = CarModel.objects.create(brand=self.brand, name="Model", vehicle_type="CAR")
        self.station = Station.objects.create(name="A", address="A")
        self.other_station = Station.objects.create(name="B", address="B")
        StationWeeklySchedule.objects.create(
            station=self.station, weekday=self.TEST_DATE.weekday(), work_start="09:00", work_end="18:00"
        )
        StationWeeklySchedule.objects.create(
            station=self.other_station, weekday=self.TEST_DATE.weekday(), work_start="09:00", work_end="18:00"
        )
        StationStaff.objects.create(
            station=self.station, user=self.operator,
            role=StationStaff.ROLE_OPERATOR, is_active=True,
        )
        self.car = Car.objects.create(
            owner=self.user, model=self.model, plate_number="A111AA", vin="VIN1", is_active=True
        )
        self.other_car = Car.objects.create(
            owner=self.other_user, model=self.model, plate_number="B222BB", vin="VIN2", is_active=True
        )

    def _appointment(self, user, car, station):
        start = timezone.make_aware(datetime(2099, 3, 3, 10, 0))
        return Appointment.objects.create(
            user=user, station=station, car=car,
            start=start, end=start + timedelta(minutes=30),
            name="Test User", phone="+70000000000",
            status="BOOKED",
        )

    def test_client_cannot_cancel_foreign_appointment(self):
        appointment = self._appointment(self.other_user, self.other_car, self.station)
        client = Client()
        client.login(username="u1@example.com", password="pass")
        response = client.post(reverse("cabinet_cancel_appointment", kwargs={"pk": appointment.id}))
        self.assertEqual(response.status_code, 404)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "BOOKED")

    def test_operator_cannot_open_foreign_station_appointment_detail(self):
        appointment = self._appointment(self.user, self.car, self.other_station)
        client = Client()
        client.login(username="op@example.com", password="pass")
        response = client.get(
            reverse("station_appointment_detail", kwargs={"station_id": self.station.id, "pk": appointment.id})
        )
        self.assertEqual(response.status_code, 404)

    def test_operator_cannot_change_foreign_station_appointment_status(self):
        appointment = self._appointment(self.user, self.car, self.other_station)
        client = Client()
        client.login(username="op@example.com", password="pass")
        response = client.post(
            reverse("station_appointment_status", kwargs={"station_id": self.station.id, "pk": appointment.id}),
            {"status": "DONE"},
        )
        self.assertEqual(response.status_code, 404)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "BOOKED")

    def test_operator_cannot_export_foreign_station_csv(self):
        client = Client()
        client.login(username="op@example.com", password="pass")
        response = client.get(reverse("station_appointments_csv", kwargs={"station_id": self.other_station.id}))
        self.assertEqual(response.status_code, 302)

    def test_operator_cannot_access_foreign_station_slot_blocks(self):
        client = Client()
        client.login(username="op@example.com", password="pass")
        response = client.get(reverse("station_slot_blocks", kwargs={"station_id": self.other_station.id}))
        self.assertEqual(response.status_code, 302)

    def test_operator_cannot_access_foreign_station_schedule(self):
        client = Client()
        client.login(username="op@example.com", password="pass")
        response = client.get(reverse("station_schedule", kwargs={"station_id": self.other_station.id}))
        self.assertEqual(response.status_code, 302)

    def test_car_api_does_not_expose_foreign_car(self):
        client = Client()
        client.login(username="u1@example.com", password="pass")
        response = client.get(reverse("car_api", kwargs={"car_id": self.other_car.id}))
        self.assertIn(response.status_code, (403, 404))
