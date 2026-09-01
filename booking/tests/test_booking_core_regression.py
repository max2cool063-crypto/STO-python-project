from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from booking.models import Appointment, Car, Station, StationWeeklySchedule
from booking.tests.test_booking_core import BookingCoreTests


class BookingCoreRegressionTests(BookingCoreTests):
    def test_appointment_save_recalculates_end_for_truck(self):
        target = date(2099, 2, 3)
        self.add_weekday_schedule(target, "09:00", "18:00")
        truck = Car.objects.create(
            owner=self.user,
            model=self.truck_model,
            plate_number="C333CC",
        )
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))

        appointment = Appointment.objects.create(
            user=self.user,
            car=truck,
            station=self.station,
            start=start,
            end=start + timedelta(minutes=1),
            name="Client",
            phone="123",
        )

        self.assertEqual(appointment.end, start + timedelta(hours=1))

    def test_cancelled_appointment_does_not_block_slot(self):
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
            status="CANCELLED",
        )

        slots = self.station.get_available_slots(target, vehicle_type="CAR")
        starts = {slot["start"][11:16] for slot in slots}
        self.assertIn("10:00", starts)
