from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from booking.models import Appointment, Brand, Car, CarModel, Station, StationSchedule


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
)
class AppointmentReminderIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reminder-client@example.com",
            email="reminder-client@example.com",
            password="test-password",
        )
        self.station = Station.objects.create(name="Reminder Station")
        self.brand = Brand.objects.create(name="Reminder Brand")
        self.model = CarModel.objects.create(
            brand=self.brand,
            name="Reminder Model",
            vehicle_type="CAR",
        )
        self.car = Car.objects.create(
            owner=self.user,
            model=self.model,
            plate_number="А111АА77",
        )
        self.start = timezone.make_aware(datetime(2099, 3, 3, 10, 0))
        self.now = self.start - timedelta(hours=24)
        StationSchedule.objects.create(
            station=self.station,
            date=self.start.date(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.appointment = Appointment.objects.create(
            station=self.station,
            user=self.user,
            car=self.car,
            start=self.start,
            end=self.start,
            name="Клиент",
            phone="+79990000000",
        )

    def test_repeated_command_sends_only_one_email(self):
        with patch(
            "booking.management.commands.send_reminders.timezone.now",
            return_value=self.now,
        ):
            call_command("send_reminders")
            call_command("send_reminders")
            call_command("send_reminders")

        self.assertEqual(len(mail.outbox), 1)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.reminder_sent_at, self.now)

    def test_failed_delivery_is_not_marked_and_can_retry(self):
        with patch(
            "booking.management.commands.send_reminders.timezone.now",
            return_value=self.now,
        ), patch(
            "booking.management.commands.send_reminders.notify_client_reminder",
            return_value=False,
        ):
            call_command("send_reminders")

        self.appointment.refresh_from_db()
        self.assertIsNone(self.appointment.reminder_sent_at)
        self.assertEqual(len(mail.outbox), 0)

        with patch(
            "booking.management.commands.send_reminders.timezone.now",
            return_value=self.now,
        ):
            call_command("send_reminders")

        self.appointment.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.appointment.reminder_sent_at, self.now)

    def test_reschedule_clears_previous_reminder_timestamp(self):
        Appointment.objects.filter(pk=self.appointment.pk).update(
            reminder_sent_at=self.now
        )
        self.appointment.refresh_from_db()
        self.assertIsNotNone(self.appointment.reminder_sent_at)

        new_start = self.start + timedelta(days=1)
        StationSchedule.objects.create(
            station=self.station,
            date=new_start.date(),
            work_start=time(9, 0),
            work_end=time(18, 0),
        )
        self.appointment.start = new_start
        self.appointment.end = new_start
        self.appointment.save()

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.start, new_start)
        self.assertIsNone(self.appointment.reminder_sent_at)
