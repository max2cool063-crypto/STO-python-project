from io import StringIO
from smtplib import SMTPException
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from booking.email_queue import enqueue_mail, process_one
from booking.models import EmailOutbox


class DeliveryLoggingTests(TestCase):
    def setUp(self):
        enqueue_mail("private subject", "private body", None, ["private@example.com"])

    def test_smtp_failure_is_logged_without_message_or_recipient(self):
        with patch("booking.email_queue.EmailMessage.send", side_effect=SMTPException("private@example.com")), self.assertLogs("booking.email_queue", level="ERROR") as captured:
            process_one()
        self.assertIn("SMTPException", " ".join(captured.output))
        self.assertNotIn("private", " ".join(captured.output))

    def test_zero_delivery_is_logged(self):
        with patch("booking.email_queue.EmailMessage.send", return_value=0), self.assertLogs("booking.email_queue", level="ERROR"):
            process_one()
        self.assertEqual(EmailOutbox.objects.get().status, "pending")

    def test_successful_retry_is_possible_after_smtp_failure(self):
        with patch("booking.email_queue.EmailMessage.send", side_effect=[SMTPException(), 1]), self.assertLogs("booking.email_queue", level="ERROR"):
            process_one()
            EmailOutbox.objects.update(available_at=timezone.now())
            process_one()
        self.assertEqual(EmailOutbox.objects.get().status, "sent")


class MaintenanceLoggingTests(SimpleTestCase):
    def test_failure_is_logged_other_job_runs_and_exit_is_unsuccessful(self):
        with patch("booking.management.commands.run_maintenance.call_command", side_effect=[RuntimeError("unavailable"), None]) as invoke, self.assertLogs("booking.management.commands.run_maintenance", level="INFO") as captured:
            with self.assertRaises(CommandError):
                call_command("run_maintenance", stdout=StringIO())
        self.assertEqual([call.args[0] for call in invoke.call_args_list], ["update_appointments", "send_reminders"])
        self.assertIn("Maintenance failed: command=update_appointments", " ".join(captured.output))
        self.assertIn("Maintenance completed: command=send_reminders", " ".join(captured.output))

    def test_successful_jobs_are_logged(self):
        with patch("booking.management.commands.run_maintenance.call_command"), self.assertLogs("booking.management.commands.run_maintenance", level="INFO") as captured:
            call_command("run_maintenance", stdout=StringIO())
        self.assertEqual(sum("Maintenance completed" in line for line in captured.output), 2)
