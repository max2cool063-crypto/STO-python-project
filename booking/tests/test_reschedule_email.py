from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from booking.email_queue import process_one
from booking.models import (
    Appointment, AppointmentLog, Brand, Car, CarModel, EmailOutbox,
    Station, StationSchedule, StationStaff,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RescheduleEmailTests(TestCase):
    def setUp(self):
        self.station = Station.objects.create(name="Samara", timezone="Europe/Samara")
        self.day = date(2099, 9, 3)
        StationSchedule.objects.create(station=self.station, date=self.day,
                                       work_start=time(8), work_end=time(18))
        self.customer = User.objects.create_user(username="customer", email="client@example.com")
        self.operator = User.objects.create_user(username="operator")
        self.staff = StationStaff.objects.create(station=self.station, user=self.operator,
                                                 role=StationStaff.ROLE_OPERATOR)
        brand = Brand.objects.create(name="Honda")
        model = CarModel.objects.create(brand=brand, name="Accord")
        car = Car.objects.create(owner=self.customer, model=model,
                                 vehicle_type="CAR", plate_number="A123AA63")
        start = self.station.make_local_datetime(self.day, time(8))
        self.appointment = Appointment.objects.create(station=self.station, user=self.customer,
            car=car, start=start, end=start, name="Client", phone="+79990000000")
        self.url = reverse("station_appointment_edit", args=[self.station.pk, self.appointment.pk])
        self.client.force_login(self.operator)

    def move(self, hour=9, notes=""):
        return self.client.post(self.url, {"start": f"2099-09-03T{hour:02d}:00", "notes": notes})

    def test_operator_move_queues_and_delivers_local_times(self):
        self.assertEqual(self.move().status_code, 302)
        item = EmailOutbox.objects.get(kind="reschedule")
        self.assertEqual(item.recipient, self.customer.email)
        self.assertIn("Было: 03.09.2099 08:00 — 03.09.2099 08:30", item.body)
        self.assertIn("Стало: 03.09.2099 09:00 — 03.09.2099 09:30", item.body)
        self.appointment.refresh_from_db()
        self.assertEqual(item.expected_revision, self.appointment.notification_revision)
        self.assertTrue(process_one())
        item.refresh_from_db()
        self.assertEqual(item.status, "sent")
        self.assertEqual(len(mail.outbox), 1)

    def test_owner_move_also_queues_mail(self):
        owner = User.objects.create_user(username="owner")
        StationStaff.objects.create(station=self.station, user=owner,
                                    role=StationStaff.ROLE_OWNER)
        self.client.force_login(owner)
        self.move()
        self.assertEqual(EmailOutbox.objects.filter(kind="reschedule").count(), 1)

    def test_notes_only_and_repeated_save_do_not_duplicate_mail(self):
        self.move(8, "Only notes")
        self.assertFalse(EmailOutbox.objects.exists())
        self.move(9)
        self.move(9, "More notes")
        self.assertEqual(EmailOutbox.objects.count(), 1)

    def test_duration_change_notifies_client(self):
        car = self.appointment.car
        car.vehicle_type = "TRUCK"
        car.save()
        self.move(8)
        self.assertIn("Стало: 03.09.2099 08:00 — 03.09.2099 09:00",
                      EmailOutbox.objects.get().body)

    def test_invalid_move_does_not_queue_mail(self):
        self.move(23)
        self.assertFalse(EmailOutbox.objects.exists())
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.local_start.hour, 8)

    def test_queue_failure_rolls_back_move_and_log(self):
        with patch("booking.notifications.enqueue_mail", side_effect=RuntimeError("queue unavailable")), \
                self.assertLogs("booking.views.station_appointment_edit", level="ERROR"):
            self.move()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.local_start.hour, 8)
        self.assertFalse(AppointmentLog.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_second_move_suppresses_obsolete_mail(self):
        self.move(9)
        self.move(10)
        self.assertEqual(EmailOutbox.objects.count(), 2)
        process_one()
        process_one()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Стало: 03.09.2099 10:00", mail.outbox[0].body)

    def test_cancelled_appointment_suppresses_queued_move(self):
        self.move()
        Appointment.objects.filter(pk=self.appointment.pk).update(status="CANCELLED")
        process_one()
        self.assertEqual(len(mail.outbox), 0)

    def test_customer_cannot_move_via_station_endpoint(self):
        self.client.force_login(self.customer)
        response = self.move()
        self.assertIn(response.status_code, (302, 403))
        self.assertFalse(EmailOutbox.objects.exists())
