from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from booking.models import (
    Appointment,
    AppointmentLog,
    Brand,
    Car,
    CarModel,
    Station,
    StationSchedule,
)


class UpdateAppointmentsAuditTests(TestCase):
    def setUp(self):
        self.now = timezone.make_aware(datetime(2099, 3, 4, 12, 0))
        self.user = User.objects.create_user(username="auto-result-client")
        self.station = Station.objects.create(name="Auto Result Station")
        self.brand = Brand.objects.create(name="Auto Result Brand")
        self.model = CarModel.objects.create(
            brand=self.brand,
            name="Auto Result Model",
            vehicle_type="CAR",
        )
        self.car = Car.objects.create(
            owner=self.user,
            model=self.model,
            plate_number="А123АА77",
        )
        self.start = self.now - timedelta(hours=2)
        StationSchedule.objects.create(
            station=self.station,
            date=self.start.date(),
            work_start=time(0, 0),
            work_end=time(23, 59),
        )
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.user,
            car=self.car,
            start=self.start,
            end=self.start,
            name="Клиент",
        )
        self.assertLess(self.appointment.end, self.now)

    def run_command(self):
        with patch(
            "booking.management.commands.update_appointments.timezone.now",
            return_value=self.now,
        ):
            call_command("update_appointments")

    def test_expired_booked_appointment_waits_for_operator_result_with_system_log(self):
        self.run_command()

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "AWAITING_RESULT")

        log = AppointmentLog.objects.get(appointment=self.appointment)
        self.assertIsNone(log.changed_by)
        self.assertEqual(log.old_status, "BOOKED")
        self.assertEqual(log.new_status, "AWAITING_RESULT")
        self.assertEqual(
            log.comment,
            "Время записи завершилось — требуется результат визита",
        )

    def test_repeated_command_does_not_duplicate_awaiting_result_log(self):
        self.run_command()
        self.run_command()

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "AWAITING_RESULT")
        self.assertEqual(
            AppointmentLog.objects.filter(appointment=self.appointment).count(),
            1,
        )

    def test_expired_terminal_appointment_is_not_changed(self):
        self.appointment.status = "CANCELLED"
        self.appointment.save(update_fields=["status"])

        self.run_command()

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "CANCELLED")
        self.assertFalse(
            AppointmentLog.objects.filter(appointment=self.appointment).exists()
        )
