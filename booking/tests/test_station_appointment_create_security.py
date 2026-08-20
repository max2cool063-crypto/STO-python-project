from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import (
    Appointment,
    Brand,
    Car,
    CarModel,
    Station,
    StationStaff,
    StationWeeklySchedule,
)


class StationAppointmentCreateSecurityTests(TestCase):
    TARGET_DATE = date(2099, 2, 3)

    def setUp(self):
        self.operator = User.objects.create_user(
            username="operator@example.com",
            password="test-password",
        )
        self.client_user = User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="test-password",
        )
        self.other_client = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="test-password",
        )

        self.station = Station.objects.create(name="Station A", slot_duration=30)
        self.other_station = Station.objects.create(name="Station B", slot_duration=30)
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )

        for station in (self.station, self.other_station):
            StationWeeklySchedule.objects.create(
                station=station,
                weekday=self.TARGET_DATE.weekday(),
                work_start=time(9, 0),
                work_end=time(18, 0),
            )

        brand = Brand.objects.create(name="Test")
        model = CarModel.objects.create(
            brand=brand,
            name="Passenger",
            vehicle_type="CAR",
        )
        self.station_car = Car.objects.create(
            owner=self.client_user,
            model=model,
            plate_number="A111AA",
        )
        self.foreign_car = Car.objects.create(
            owner=self.other_client,
            model=model,
            plate_number="B222BB",
        )

        Appointment.objects.create(
            station=self.other_station,
            user=self.other_client,
            car=self.foreign_car,
            start="2099-02-03T09:00:00+03:00",
            end="2099-02-03T09:30:00+03:00",
            name="Other client",
        )

        self.client.login(username="operator@example.com", password="test-password")

    def post_create(self, car_id, start="2099-02-03T10:00"):
        return self.client.post(
            reverse(
                "station_appointment_create",
                kwargs={"station_id": self.station.id},
            ),
            {
                "car_id": car_id,
                "start": start,
                "client_name": "Client",
                "client_phone": "123456789",
            },
        )

    def test_operator_cannot_attach_foreign_station_car_by_id(self):
        before = Appointment.objects.count()

        response = self.post_create(self.foreign_car.id)

        self.assertRedirects(
            response,
            reverse(
                "station_appointments",
                kwargs={"station_id": self.station.id},
            ),
        )
        self.assertEqual(Appointment.objects.count(), before)
        self.assertFalse(
            Appointment.objects.filter(
                station=self.station,
                car=self.foreign_car,
            ).exists()
        )

    def test_operator_can_use_car_already_known_by_current_station(self):
        Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=self.station_car,
            start="2099-02-03T09:00:00+03:00",
            end="2099-02-03T09:30:00+03:00",
            name="Client",
        )
        before = Appointment.objects.count()

        response = self.post_create(self.station_car.id, start="2099-02-03T10:00")

        self.assertRedirects(
            response,
            reverse(
                "station_appointments",
                kwargs={"station_id": self.station.id},
            ),
        )
        self.assertEqual(Appointment.objects.count(), before + 1)
        self.assertTrue(
            Appointment.objects.filter(
                station=self.station,
                car=self.station_car,
                start__hour=10,
            ).exists()
        )
