from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Appointment, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class StationClientIdentitySeparationTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="client-directory-operator",
            password="Strong-test-password-123!",
        )
        self.station = Station.objects.create(name="Client directory station")
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
        )
        brand = Brand.objects.create(name="Client directory brand")
        model = CarModel.objects.create(brand=brand, name="Client directory model")
        target = date(2099, 4, 5)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )

        staff_car = Car.objects.create(
            owner=self.operator,
            model=model,
            plate_number="А100АА77",
        )
        staff_start = self.station.make_local_datetime(target, time(10, 0))
        Appointment.objects.create(
            station=self.station,
            user=self.operator,
            car=staff_car,
            start=staff_start,
            end=staff_start,
            name="Legacy staff client",
        )

        self.client_user = User.objects.create_user(
            username="pure-client-directory",
            first_name="Иван",
            last_name="Клиентов",
        )
        client_car = Car.objects.create(
            owner=self.client_user,
            model=model,
            plate_number="В200ВВ77",
        )
        client_start = self.station.make_local_datetime(target, time(11, 0))
        Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=client_car,
            start=client_start,
            end=client_start,
            name="Клиентов Иван",
        )

        self.client.force_login(self.operator)

    def test_station_client_directory_excludes_staff_identities(self):
        response = self.client.get(
            reverse("station_clients", kwargs={"station_id": self.station.pk})
        )

        self.assertEqual(response.status_code, 200)
        client_ids = set(response.context["clients"].values_list("pk", flat=True))
        self.assertEqual(client_ids, {self.client_user.pk})
