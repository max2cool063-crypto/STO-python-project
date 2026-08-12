from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Appointment,
    Brand,
    Car,
    CarModel,
    SlotBlock,
    Station,
    StationSchedule,
    StationStaff,
    StationWeeklySchedule,
)


class StationSecurityTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="test-password",
        )
        self.client_user = User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="test-password",
        )
        self.other_client = User.objects.create_user(
            username="other-client@example.com",
            email="other-client@example.com",
            password="test-password",
        )

        self.station = Station.objects.create(name="Station A")
        self.other_station = Station.objects.create(name="Station B")

        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
            is_active=True,
        )

        self.brand = Brand.objects.create(name="Test")
        self.model = CarModel.objects.create(
            brand=self.brand,
            name="Passenger",
            vehicle_type="CAR",
        )
        self.car = Car.objects.create(
            owner=self.client_user,
            model=self.model,
            plate_number="A111AA",
        )
        self.other_car = Car.objects.create(
            owner=self.other_client,
            model=self.model,
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
            end=start,
            name="Client",
            phone="123",
        )

    def login_operator(self):
        self.client.login(username="operator@example.com", password="test-password")

    def test_operator_can_update_weekly_schedule(self):
        self.login_operator()

        response = self.client.post(
            reverse("station_schedule", kwargs={"station_id": self.station.id}),
            {
                "action": "save_weekly",
                "work_start_0": "08:00",
                "work_end_0": "18:00",
            },
        )

        self.assertRedirects(
            response,
            reverse("station_schedule", kwargs={"station_id": self.station.id}),
        )
        schedule = StationWeeklySchedule.objects.get(
            station=self.station,
            weekday=0,
        )
        self.assertEqual(schedule.work_start, time(8, 0))
        self.assertEqual(schedule.work_end, time(18, 0))

    def test_operator_can_add_and_delete_schedule_exception(self):
        self.login_operator()
        target = "2099-02-03"
        url = reverse("station_schedule", kwargs={"station_id": self.station.id})

        response = self.client.post(
            url,
            {
                "action": "add_exception",
                "date": target,
                "work_start": "10:00",
                "work_end": "14:00",
            },
        )
        self.assertRedirects(response, url)

        exception = StationSchedule.objects.get(
            station=self.station,
            date=date(2099, 2, 3),
        )
        self.assertEqual(exception.work_start, time(10, 0))
        self.assertEqual(exception.work_end, time(14, 0))

        response = self.client.post(
            url,
            {"action": "delete_exception", "exception_id": exception.id},
        )
        self.assertRedirects(response, url)
        self.assertFalse(StationSchedule.objects.filter(pk=exception.id).exists())

    def test_operator_can_create_and_delete_slot_block(self):
        self.login_operator()
        url = reverse("station_slot_blocks", kwargs={"station_id": self.station.id})

        response = self.client.post(
            url,
            {
                "action": "add",
                "start": "2099-02-03T10:00",
                "end": "2099-02-03T11:00",
                "reason": "Equipment maintenance",
            },
        )
        self.assertRedirects(response, url)

        block = SlotBlock.objects.get(station=self.station)
        self.assertEqual(block.created_by, self.operator)
        self.assertEqual(block.reason, "Equipment maintenance")

        response = self.client.post(
            url,
            {"action": "delete", "block_id": block.id},
        )
        self.assertRedirects(response, url)
        self.assertFalse(SlotBlock.objects.filter(pk=block.id).exists())

    def test_operator_cannot_manage_schedule_of_other_station(self):
        self.login_operator()
        url = reverse("station_schedule", kwargs={"station_id": self.other_station.id})

        response = self.client.post(
            url,
            {
                "action": "add_exception",
                "date": "2099-02-03",
                "work_start": "10:00",
                "work_end": "14:00",
            },
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )
        self.assertFalse(
            StationSchedule.objects.filter(
                station=self.other_station,
                date=date(2099, 2, 3),
            ).exists()
        )

    def test_operator_cannot_manage_slot_blocks_of_other_station(self):
        self.login_operator()
        url = reverse("station_slot_blocks", kwargs={"station_id": self.other_station.id})

        response = self.client.post(
            url,
            {
                "action": "add",
                "start": "2099-02-03T10:00",
                "end": "2099-02-03T11:00",
                "reason": "attempt",
            },
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )
        self.assertFalse(SlotBlock.objects.filter(station=self.other_station).exists())

    def test_station_csv_contains_only_current_station_appointments(self):
        own = self.create_appointment(self.station, self.client_user, self.car)
        foreign = self.create_appointment(self.other_station, self.other_client, self.other_car, hour=11)

        self.login_operator()
        response = self.client.get(
            reverse("station_appointments_csv", kwargs={"station_id": self.station.id})
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertIn(own.car.plate_number, content)
        self.assertNotIn(foreign.car.plate_number, content)

    def test_operator_cannot_access_clients_of_other_station(self):
        self.create_appointment(self.other_station, self.other_client, self.other_car)
        self.login_operator()

        response = self.client.get(
            reverse("station_clients", kwargs={"station_id": self.other_station.id})
        )

        self.assertRedirects(
            response,
            reverse("station_select"),
            fetch_redirect_response=False,
        )

    def test_station_owner_can_access_clients(self):
        owner = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="test-password",
        )
        StationStaff.objects.create(
            station=self.station,
            user=owner,
            role=StationStaff.ROLE_OWNER,
            is_active=True,
        )
        self.create_appointment(self.station, self.client_user, self.car)

        self.client.login(username="owner@example.com", password="test-password")
        response = self.client.get(
            reverse("station_clients", kwargs={"station_id": self.station.id})
        )

        self.assertEqual(response.status_code, 200)
        clients = list(response.context["clients"])
        self.assertIn(self.client_user, clients)
