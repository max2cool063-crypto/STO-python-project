from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, Station, StationStaff, StationWeeklySchedule


class StationClientAndPlateLookupTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="lookup-operator",
            password="test-password",
        )
        self.station = Station.objects.create(name="Lookup Station")
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )
        self.brand = Brand.objects.create(name="Lookup Brand")
        self.model = CarModel.objects.create(
            brand=self.brand,
            name="Lookup Model",
            vehicle_type="CAR",
        )
        target = date(2099, 3, 3)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.start = "2099-03-03T10:00:00+03:00"
        self.start_dt = timezone.make_aware(datetime(2099, 3, 3, 10, 0))
        self.client.login(username="lookup-operator", password="test-password")

    def test_clients_page_uses_user_first_and_last_name(self):
        user = User.objects.create_user(
            username="client-named",
            first_name="Иван",
            last_name="Иванов",
            email="ivan@example.com",
        )
        car = Car.objects.create(
            owner=user,
            model=self.model,
            plate_number="A111AA63",
        )
        Appointment.objects.create(
            station=self.station,
            user=user,
            car=car,
            start=self.start_dt,
            end=self.start_dt + timedelta(minutes=30),
            name="Иванов Иван",
        )

        response = self.client.get(reverse("station_clients", kwargs={"station_id": self.station.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Иванов Иван")

    def test_plate_lookup_returns_all_matches_instead_of_first(self):
        first_owner = User.objects.create_user(
            username="owner-one",
            first_name="Иван",
            last_name="Иванов",
        )
        second_owner = User.objects.create_user(
            username="owner-two",
            first_name="Пётр",
            last_name="Петров",
        )
        Car.objects.create(
            owner=first_owner,
            model=self.model,
            plate_number="A222AA63",
            vin="VINONE",
        )
        Car.objects.create(
            owner=second_owner,
            model=self.model,
            plate_number="A222AA63",
            vin="VINTWO",
        )

        response = self.client.get(
            reverse("car_by_plate_api"),
            {"plate": "A222AA63", "station_id": self.station.id},
        )
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ambiguous"])
        self.assertEqual(data["count"], 2)
        self.assertEqual({item["vin"] for item in data["matches"]}, {"VINONE", "VINTWO"})

    def test_plate_lookup_can_be_repeated_without_server_side_state(self):
        owner_one = User.objects.create_user(username="repeat-one", first_name="Один")
        owner_two = User.objects.create_user(username="repeat-two", first_name="Два")
        Car.objects.create(owner=owner_one, model=self.model, plate_number="A333AA63")
        Car.objects.create(owner=owner_two, model=self.model, plate_number="A444AA63")

        first = self.client.get(
            reverse("car_by_plate_api"),
            {"plate": "A333AA63", "station_id": self.station.id},
        ).json()
        second = self.client.get(
            reverse("car_by_plate_api"),
            {"plate": "A444AA63", "station_id": self.station.id},
        ).json()

        self.assertEqual(first["owner_name"], "Один")
        self.assertEqual(second["owner_name"], "Два")

    def test_manual_booking_persists_client_name_to_user(self):
        response = self.client.post(
            reverse("station_appointment_create", kwargs={"station_id": self.station.id}),
            {
                "plate": "A555AA63",
                "new_model_id": self.model.id,
                "new_user_email": "new-client@example.com",
                "client_name": "Сидоров Сергей",
                "client_phone": "+79990001122",
                "start": self.start,
            },
        )

        self.assertRedirects(
            response,
            reverse("station_appointments", kwargs={"station_id": self.station.id}),
        )
        appointment = Appointment.objects.get(station=self.station)
        self.assertEqual(appointment.user.last_name, "Сидоров")
        self.assertEqual(appointment.user.first_name, "Сергей")
        self.assertEqual(appointment.user.profile.phone, "+79990001122")

    def test_manual_booking_updates_existing_owner_identity(self):
        owner = User.objects.create_user(username="existing-owner")
        car = Car.objects.create(
            owner=owner,
            model=self.model,
            plate_number="A666AA63",
        )

        response = self.client.post(
            reverse("station_appointment_create", kwargs={"station_id": self.station.id}),
            {
                "car_id": car.id,
                "plate": "A666AA63",
                "client_name": "Орлов Олег",
                "client_phone": "+79990003344",
                "start": self.start,
            },
        )

        self.assertRedirects(
            response,
            reverse("station_appointments", kwargs={"station_id": self.station.id}),
        )
        owner.refresh_from_db()
        owner.profile.refresh_from_db()
        self.assertEqual(owner.last_name, "Орлов")
        self.assertEqual(owner.first_name, "Олег")
        self.assertEqual(owner.profile.phone, "+79990003344")
