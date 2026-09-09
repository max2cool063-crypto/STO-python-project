from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, SlotBlock, Station, StationWeeklySchedule


class SlotBlockBookingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="blocked-booking@example.com",
            password="test-password",
        )
        self.brand = Brand.objects.create(name="Block Test")
        self.model = CarModel.objects.create(
            brand=self.brand,
            name="Passenger",
            vehicle_type="CAR",
        )
        self.car = Car.objects.create(
            owner=self.user,
            model=self.model,
            plate_number="A111AA",
        )
        self.station = Station.objects.create(name="Blocked Station")
        self.target_date = date(2099, 5, 5)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=self.target_date.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )

    def test_appointment_rejects_time_overlapping_slot_block(self):
        start = timezone.make_aware(timezone.datetime(2099, 5, 5, 10, 0))
        SlotBlock.objects.create(
            station=self.station,
            start=start,
            end=start + timedelta(minutes=30),
            reason="Maintenance",
            created_by=self.user,
        )

        appointment = Appointment(
            station=self.station,
            user=self.user,
            car=self.car,
            start=start,
            end=start + timedelta(minutes=30),
            name="Client",
        )

        with self.assertRaisesMessage(ValidationError, "Выбранное время заблокировано станцией"):
            appointment.save()
