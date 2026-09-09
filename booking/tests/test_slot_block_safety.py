from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import (
    Appointment,
    Brand,
    Car,
    CarModel,
    SlotBlock,
    Station,
    StationStaff,
    StationWeeklySchedule,
)


class StationSlotBlockSafetyTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="slot-block-operator",
            password="Strong-operator-123!",
        )
        self.client_user = User.objects.create_user(
            username="slot-block-client",
            password="Strong-client-123!",
        )
        self.station = Station.objects.create(
            name="Slot Block Safety Station",
            timezone="Europe/Moscow",
        )
        StationStaff.objects.create(
            station=self.station,
            user=self.operator,
            role=StationStaff.ROLE_OPERATOR,
        )
        brand = Brand.objects.create(name="Slot Block Safety Brand")
        model = CarModel.objects.create(
            brand=brand,
            name="Slot Block Safety Model",
            vehicle_type="CAR",
        )
        self.car = Car.objects.create(
            owner=self.client_user,
            model=model,
            plate_number="А111АА77",
        )
        self.target_date = date(2099, 7, 6)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=self.target_date.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.start = self.station.make_local_datetime(self.target_date, time(10, 0))
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.client_user,
            car=self.car,
            start=self.start,
            end=self.start + timedelta(minutes=30),
            name="Клиент",
        )
        self.client.login(
            username="slot-block-operator",
            password="Strong-operator-123!",
        )
        self.url = reverse(
            "station_slot_blocks",
            kwargs={"station_id": self.station.pk},
        )

    def _post_block(self, start_time, end_time):
        return self.client.post(
            self.url,
            {
                "action": "add",
                "start": f"{self.target_date.isoformat()}T{start_time}",
                "end": f"{self.target_date.isoformat()}T{end_time}",
                "reason": "Технические работы",
            },
        )

    def test_cannot_create_block_over_existing_non_cancelled_appointment(self):
        response = self._post_block("10:00", "10:30")

        self.assertRedirects(response, self.url)
        self.assertFalse(SlotBlock.objects.filter(station=self.station).exists())

    def test_can_create_block_for_free_interval(self):
        response = self._post_block("11:00", "11:30")

        self.assertRedirects(response, self.url)
        block = SlotBlock.objects.get(station=self.station)
        self.assertEqual(block.start, self.station.make_local_datetime(self.target_date, time(11, 0)))
        self.assertEqual(block.end, self.station.make_local_datetime(self.target_date, time(11, 30)))
        self.assertEqual(block.created_by, self.operator)

    def test_cancelled_appointment_does_not_prevent_blocking_its_old_interval(self):
        Appointment.objects.filter(pk=self.appointment.pk).update(status="CANCELLED")

        response = self._post_block("10:00", "10:30")

        self.assertRedirects(response, self.url)
        self.assertTrue(SlotBlock.objects.filter(station=self.station).exists())
