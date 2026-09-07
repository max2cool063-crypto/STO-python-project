from datetime import date, time

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, Station, StationWeeklySchedule


class AppointmentStatusTransitionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="status-test@example.com",
            password="test-password",
        )
        self.brand = Brand.objects.create(name="Status Test")
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
        self.station = Station.objects.create(name="Status Station")
        target = date(2099, 2, 3)
        StationWeeklySchedule.objects.create(
            station=self.station,
            weekday=target.weekday(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        start = timezone.make_aware(timezone.datetime(2099, 2, 3, 10, 0))
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.user,
            car=self.car,
            start=start,
            end=start + timezone.timedelta(minutes=30),
            name="Client",
            phone="+79991234567",
        )

    def set_status(self, status):
        self.appointment.status = status
        self.appointment.save()

    def test_booked_can_transition_to_terminal_statuses(self):
        for status in ("CANCELLED", "DONE", "NO_SHOW"):
            with self.subTest(status=status):
                self.appointment.status = "BOOKED"
                self.appointment.save()
                self.set_status(status)
                self.appointment.refresh_from_db()
                self.assertEqual(self.appointment.status, status)

    def test_terminal_status_cannot_be_changed_to_another_status(self):
        for initial in ("CANCELLED", "DONE", "NO_SHOW"):
            for target in ("BOOKED", "CANCELLED", "DONE", "NO_SHOW"):
                if target == initial:
                    continue
                with self.subTest(initial=initial, target=target):
                    self.appointment.status = "BOOKED"
                    self.appointment.save()
                    self.appointment.status = initial
                    self.appointment.save()
                    self.appointment.status = target
                    with self.assertRaisesMessage(
                        ValidationError,
                        f"Недопустимый переход статуса: {initial} → {target}",
                    ):
                        self.appointment.save()

    def test_creating_appointment_with_explicit_booked_status_is_unchanged(self):
        self.assertEqual(self.appointment.status, "BOOKED")
