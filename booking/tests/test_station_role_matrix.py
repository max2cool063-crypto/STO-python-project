from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
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


class StationRoleMatrixTests(TestCase):
    def setUp(self):
        self.station_a = Station.objects.create(name="Station A")
        self.station_b = Station.objects.create(name="Station B")
        self.station_c = Station.objects.create(name="Station C")

        self.operator = User.objects.create_user(
            username="operator@example.com",
            password="test-password",
        )
        self.owner = User.objects.create_user(
            username="owner@example.com",
            password="test-password",
        )
        self.client_user = User.objects.create_user(
            username="client@example.com",
            password="test-password",
        )
        self.other_client = User.objects.create_user(
            username="other-client@example.com",
            password="test-password",
        )

        StationStaff.objects.create(
            station=self.station_a,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        StationStaff.objects.create(
            station=self.station_a,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        StationStaff.objects.create(
            station=self.station_b,
            user=self.owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )

        brand = Brand.objects.create(name="Test")
        model = CarModel.objects.create(
            brand=brand,
            name="Passenger",
            vehicle_type="CAR",
        )
        self.car = Car.objects.create(
            owner=self.client_user,
            model=model,
            plate_number="A111AA",
        )
        self.other_car = Car.objects.create(
            owner=self.other_client,
            model=model,
            plate_number="B222BB",
        )

    def create_appointment(self, station, user, car, hour=10):
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.get_or_create(
            station=station,
            weekday=target.weekday(),
            defaults={"work_start": time(9, 0), "work_end": time(18, 0)},
        )
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, hour, 0))
        return Appointment.objects.create(
            station=station,
            user=user,
            car=car,
            start=start,
            end=start + timedelta(hours=1),
            name="Client",
            phone="123",
        )

    def test_operator_can_access_clients_of_own_station(self):
        self.create_appointment(self.station_a, self.client_user, self.car)
        self.client.login(username="operator@example.com", password="test-password")

        response = self.client.get(
            reverse("station_clients", kwargs={"station_id": self.station_a.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.client_user, response.context["clients"])

    def test_operator_cannot_access_clients_of_foreign_station(self):
        self.create_appointment(self.station_b, self.other_client, self.other_car)
        self.client.login(username="operator@example.com", password="test-password")

        response = self.client.get(
            reverse("station_clients", kwargs={"station_id": self.station_b.id})
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )

    def test_owner_with_two_stations_can_switch_between_them(self):
        self.create_appointment(self.station_a, self.client_user, self.car)
        self.create_appointment(self.station_b, self.other_client, self.other_car, hour=11)
        self.client.login(username="owner@example.com", password="test-password")

        select_response = self.client.get(reverse("station_select"))
        self.assertEqual(select_response.status_code, 200)
        station_ids = set(select_response.context["stations"].values_list("id", flat=True))
        self.assertEqual(station_ids, {self.station_a.id, self.station_b.id})

        response_a = self.client.get(
            reverse("station_clients", kwargs={"station_id": self.station_a.id})
        )
        self.assertEqual(response_a.status_code, 200)
        self.assertIn(self.client_user, response_a.context["clients"])
        self.assertNotIn(self.other_client, response_a.context["clients"])

        response_b = self.client.get(
            reverse("station_clients", kwargs={"station_id": self.station_b.id})
        )
        self.assertEqual(response_b.status_code, 200)
        self.assertIn(self.other_client, response_b.context["clients"])
        self.assertNotIn(self.client_user, response_b.context["clients"])

    def test_owner_cannot_access_station_without_assignment(self):
        self.client.login(username="owner@example.com", password="test-password")

        response = self.client.get(
            reverse("station_dashboard", kwargs={"station_id": self.station_c.id})
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )

    def test_operator_cannot_open_staff_management(self):
        self.client.login(username="operator@example.com", password="test-password")

        response = self.client.get(
            reverse("station_staff", kwargs={"station_id": self.station_a.id})
        )

        self.assertRedirects(
            response,
            reverse("station_dashboard", kwargs={"station_id": self.station_a.id}),
            fetch_redirect_response=False,
        )
