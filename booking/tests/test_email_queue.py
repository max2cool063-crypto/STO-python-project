from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from threading import Event
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.management import call_command
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.email_queue import MAX_ATTEMPTS, _claim, _finish, enqueue_mail, process_one
from booking.models import Appointment, Brand, Car, CarModel, EmailOutbox, Station, StationSchedule, StationStaff
from booking.notifications import notify_client_reminder


class EmailQueueTests(TestCase):
    def enqueue(self, **kwargs):
        enqueue_mail("Subject", "Private body", None, ["client@example.com"], **kwargs)
        return EmailOutbox.objects.latest("created_at")

    def test_producer_does_not_send_and_deduplicates_per_recipient(self):
        with patch("booking.email_queue.EmailMessage.send") as send:
            for _ in range(2):
                enqueue_mail("Subject", "Body", None, ["a@example.com", "b@example.com"], event_key="event")
        self.assertEqual(EmailOutbox.objects.count(), 2)
        send.assert_not_called()

    def test_outbox_is_rolled_back_with_business_transaction(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.enqueue()
                raise RuntimeError("rollback")
        self.assertFalse(EmailOutbox.objects.exists())

    def test_retry_is_delayed_and_has_a_stable_message_id(self):
        row = self.enqueue()
        ids = []
        def smtp(message, **kwargs):
            ids.append(message.extra_headers["Message-ID"])
            if len(ids) == 1:
                raise ConnectionError("private SMTP error")
            return 1
        with patch("booking.email_queue.EmailMessage.send", autospec=True, side_effect=smtp):
            with self.assertLogs("booking.email_queue", level="ERROR"):
                self.assertTrue(process_one())
            self.assertFalse(process_one())
            row.refresh_from_db()
            self.assertGreater(row.available_at, timezone.now())
            self.assertEqual(row.last_error, "ConnectionError")
            EmailOutbox.objects.filter(pk=row.pk).update(available_at=timezone.now())
            self.assertTrue(process_one())
        row.refresh_from_db()
        self.assertEqual(row.status, "sent")
        self.assertEqual(row.attempts, 2)
        self.assertEqual(ids[0], ids[1])

    def test_repeated_failure_reaches_terminal_state(self):
        row = self.enqueue()
        with patch("booking.email_queue.EmailMessage.send", side_effect=ConnectionError()), self.assertLogs("booking.email_queue", level="ERROR"):
            for _ in range(MAX_ATTEMPTS):
                EmailOutbox.objects.filter(pk=row.pk).update(available_at=timezone.now())
                self.assertTrue(process_one())
        self.assertFalse(process_one())
        row.refresh_from_db()
        self.assertEqual(row.status, "failed")
        self.assertEqual(row.attempts, MAX_ATTEMPTS)

    def test_abandoned_lease_can_be_reclaimed_but_old_worker_cannot_acknowledge(self):
        row = self.enqueue()
        abandoned = _claim()
        self.assertFalse(process_one())
        EmailOutbox.objects.filter(pk=row.pk).update(locked_until=timezone.now() - timedelta(seconds=1))
        with patch("booking.email_queue.EmailMessage.send", return_value=1):
            self.assertTrue(process_one())
        with self.assertLogs("booking.email_queue", level="WARNING"):
            _finish(abandoned, "pending", "old-worker")
        row.refresh_from_db()
        self.assertEqual(row.status, "sent")
        self.assertEqual(row.attempts, 2)

    def test_abandoned_last_attempt_does_not_stay_processing_forever(self):
        row = self.enqueue()
        EmailOutbox.objects.filter(pk=row.pk).update(status="processing", attempts=MAX_ATTEMPTS, locked_until=timezone.now())
        with self.assertLogs("booking.email_queue", level="ERROR"):
            process_one()
        row.refresh_from_db()
        self.assertEqual(row.status, "failed")

    def test_used_password_link_is_cancelled_without_sending(self):
        user = User.objects.create_user(username="queue-password", email="client@example.com")
        row = self.enqueue(kind="password", user=user, auth_token=default_token_generator.make_token(user))
        user.set_password("New-password-123!")
        user.save(update_fields=["password"])
        with patch("booking.email_queue.EmailMessage.send") as send:
            process_one()
        row.refresh_from_db()
        self.assertEqual(row.status, "cancelled")
        self.assertEqual(row.last_error, "PasswordLinkInvalid")
        send.assert_not_called()

    def test_expired_message_is_not_sent(self):
        row = self.enqueue(expires_at=timezone.now() - timedelta(seconds=1))
        with patch("booking.email_queue.EmailMessage.send") as send:
            process_one()
        row.refresh_from_db()
        self.assertEqual(row.status, "cancelled")
        send.assert_not_called()

    def test_purge_keeps_pending_and_failed_jobs(self):
        for status in ("pending", "sent", "failed", "cancelled"):
            row = self.enqueue()
            EmailOutbox.objects.filter(pk=row.pk).update(status=status, finished_at=timezone.now() - timedelta(days=31))
        call_command("purge_email_queue")
        self.assertEqual(set(EmailOutbox.objects.values_list("status", flat=True)), {"pending", "failed"})


class AppointmentEmailQueueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="queue-client", email="client@example.com")
        self.owner = User.objects.create_user(username="queue-owner", email="owner@example.com")
        self.station = Station.objects.create(name="Queue station")
        StationStaff.objects.create(station=self.station, user=self.owner, role="OWNER")
        model = CarModel.objects.create(brand=Brand.objects.create(name="Queue brand"), name="Car", vehicle_type="CAR")
        self.car = Car.objects.create(owner=self.user, model=model, plate_number="А123АА77")
        self.start = timezone.make_aware(datetime(2099, 3, 3, 10))
        StationSchedule.objects.create(station=self.station, date=self.start.date(), work_start=time(9), work_end=time(18))

    def appointment(self):
        return Appointment.objects.create(station=self.station, user=self.user, car=self.car, start=self.start, end=self.start, name="Client")

    def test_booking_and_already_queued_staff_mail_roll_back_when_second_enqueue_fails(self):
        self.client.force_login(self.user)
        with patch("booking.views.booking.notify_client_booked", side_effect=RuntimeError("queue unavailable")), self.assertLogs("booking.views.booking", level="ERROR"):
            response = self.client.post(reverse("book_station", kwargs={"pk": self.station.pk}), {"car": self.car.pk, "start": self.start.isoformat()})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Appointment.objects.exists())
        self.assertFalse(EmailOutbox.objects.exists())

    def test_cancelled_appointment_drops_pending_reminder(self):
        appt = self.appointment()
        notify_client_reminder(appt)
        appt.status = "CANCELLED"
        appt.save()
        with patch("booking.email_queue.EmailMessage.send") as send:
            process_one()
        self.assertEqual(EmailOutbox.objects.get().status, "cancelled")
        send.assert_not_called()

    def test_return_to_original_time_does_not_reuse_old_reminder(self):
        appt = self.appointment()
        notify_client_reminder(appt)
        for start in (self.start + timedelta(hours=1), self.start):
            appt.start = start
            appt.save()
            notify_client_reminder(appt)
        self.assertEqual(EmailOutbox.objects.count(), 3)
        call_command("process_email_queue")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailOutbox.objects.filter(status="cancelled").count(), 2)
        appt.refresh_from_db()
        self.assertIsNotNone(appt.reminder_sent_at)

    def test_registration_persists_password_link_without_contacting_smtp(self):
        with patch("booking.email_queue.EmailMessage.send") as send:
            response = self.client.post(reverse("register"), {"email": "queued-registration@example.com"}, REMOTE_ADDR="192.0.2.91")
        self.assertEqual(response.status_code, 302)
        row = EmailOutbox.objects.get(kind="password")
        self.assertIn("accounts/set-password/", row.body)
        self.assertFalse(row.user.has_usable_password())
        send.assert_not_called()
        call_command("process_email_queue")
        self.assertEqual(len(mail.outbox), 1)


@skipUnless(connection.vendor == "postgresql", "Requires independent PostgreSQL transactions")
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailWorkerConcurrencyTests(TransactionTestCase):
    def test_two_workers_do_not_send_the_same_active_lease_and_smtp_is_outside_transaction(self):
        enqueue_mail("Subject", "Body", None, ["client@example.com"])
        entered, release = Event(), Event()
        def smtp(message, **kwargs):
            self.assertFalse(connection.in_atomic_block)
            entered.set()
            if not release.wait(10):
                raise TimeoutError("test did not release SMTP")
            return 1
        def worker():
            try:
                return process_one()
            finally:
                connections.close_all()
        with patch("booking.email_queue.EmailMessage.send", autospec=True, side_effect=smtp) as send, ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            try:
                self.assertTrue(entered.wait(10))
                self.assertFalse(process_one())
            finally:
                release.set()
            self.assertTrue(future.result(timeout=15))
        self.assertEqual(send.call_count, 1)
        self.assertEqual(EmailOutbox.objects.get().status, "sent")
