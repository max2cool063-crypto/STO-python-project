from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Brand, Car, CarModel, Station, StationWeeklySchedule


class ClientBookingDurationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="truck-client@example.com",
            email="truck-client@example.com",
            password="test-password",
        )
        brand = Brand.objects.create(name="GAZ")
        truck_model = CarModel.objects.create(
            brand=brand,
            name="GAZelle Next",
            vehicle_type="TRUCK",
        )
        self.truck = Car.objects.create(
            owner=self.user,
            model=truck_model,
            plate_number="A822KE763",
        )
        self.station = Station.objects.create(name="Truck Duration Station")
        self.target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=self.target.weekday(),
            work_start=time(9, 0),
            work_end=time(13, 0),
        )
        self.client.login(
            username="truck-client@example.com",
            password="test-password",
        )

    def test_client_truck_slots_are_sixty_minutes(self):
        response = self.client.get(
            reverse("station_slots_api", kwargs={"station_id": self.station.id}),
            {"date": self.target.isoformat(), "car": self.truck.id},
        )

        self.assertEqual(response.status_code, 200)
        slots = response.json()["slots"]
        self.assertTrue(slots)

        first = slots[0]
        start = datetime.fromisoformat(first["start"])
        end = datetime.fromisoformat(first["end"])
        self.assertEqual((end - start).total_seconds(), 60 * 60)
