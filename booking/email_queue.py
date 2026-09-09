"""Transactional email outbox with bounded retries and expiring worker leases."""
import hashlib
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from booking.models import Appointment, EmailOutbox, StationStaff

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 8
LEASE_SECONDS = 300


def enqueue_mail(subject, message, from_email, recipient_list, *, event_key=None,
                 kind="generic", appointment=None, user=None, auth_token="",
                 expires_at=None, fail_silently=False):
    """Return accepted recipient count, NOT SMTP deliveries. DB errors propagate.

    Call inside the business transaction to make the event and its mail atomic.
    Separate rows per recipient prevent resending to everyone on partial failure.
    """
    recipients = list(dict.fromkeys(r for r in recipient_list if r and "@" in r))
    event_key = event_key or str(uuid.uuid4())
    with transaction.atomic():
        for recipient in recipients:
            key = hashlib.sha256(f"{event_key}\0{recipient.lower()}".encode()).hexdigest()
            EmailOutbox.objects.get_or_create(
                deduplication_key=key,
                defaults={
                    "subject": subject, "body": message,
                    "sender": from_email or settings.DEFAULT_FROM_EMAIL or "",
                    "recipient": recipient, "kind": kind,
                    "appointment": appointment,
                    "expected_start": appointment.start if appointment else None,
                    "expected_revision": appointment.notification_revision if appointment else 0,
                    "user": user, "auth_token": auth_token, "expires_at": expires_at,
                },
            )
    return len(recipients)


def _claim():
    now = timezone.now()
    with transaction.atomic():
        item = (EmailOutbox.objects.select_for_update(skip_locked=True)
                .filter(Q(status="pending", available_at__lte=now) |
                        Q(status="processing", locked_until__lte=now))
                .order_by("available_at", "created_at", "pk").first())
        if item is None:
            return None
        if item.attempts >= MAX_ATTEMPTS:
            item.status = "failed"
            item.finished_at = now
            item.locked_until = None
            item.lock_token = None
            item.last_error = "WorkerLeaseExpired"
            item.save()
            logger.error("Email attempts exhausted after worker loss: id=%s", item.pk)
            return item
        item.status = "processing"
        item.attempts += 1
        item.lock_token = uuid.uuid4()
        item.locked_until = now + timedelta(seconds=LEASE_SECONDS)
        item.save(update_fields=["status", "attempts", "lock_token", "locked_until"])
        return item


def _stale_reason(item):
    now = timezone.now()
    if item.expires_at and item.expires_at <= now:
        return "Expired"
    if item.kind in {"password", "welcome"}:
        user = item.user
        if not user or not user.is_active or user.email.lower() != item.recipient.lower():
            return "AccountChanged"
        if item.kind == "password" and not default_token_generator.check_token(user, item.auth_token):
            return "PasswordLinkInvalid"
        if item.kind == "welcome" and not StationStaff.objects.filter(user=user, is_active=True).exists():
            return "StaffDeactivated"
    if item.kind in {"booking", "cancellation", "reminder", "staff_booking", "staff_cancellation"}:
        appt = item.appointment
        if not appt:
            return "AppointmentDeleted"
        cancelling = item.kind in {"cancellation", "staff_cancellation"}
        if cancelling:
            if appt.status != "CANCELLED":
                return "AppointmentChanged"
        elif (appt.status != "BOOKED" or appt.start != item.expected_start or
              appt.notification_revision != item.expected_revision or appt.start <= now):
            return "AppointmentChanged"
        if item.kind.startswith("staff_"):
            if not StationStaff.objects.filter(station_id=appt.station_id, is_active=True,
                    receive_notifications=True, user__is_active=True,
                    user__email__iexact=item.recipient).exists():
                return "StaffRecipientChanged"
        elif not appt.user.is_active or appt.user.email.lower() != item.recipient.lower():
            return "ClientRecipientChanged"
    return ""


def _finish(item, status, error=""):
    now = timezone.now()
    with transaction.atomic():
        # A worker that has lost its lease cannot overwrite a newer attempt.
        changed = EmailOutbox.objects.filter(pk=item.pk, status="processing", lock_token=item.lock_token).update(
            status=status, last_error=error, lock_token=None, locked_until=None,
            finished_at=None if status == "pending" else now,
            available_at=now + timedelta(seconds=min(30 * 2 ** (item.attempts - 1), 3600)),
        )
        if changed and status == "sent" and item.kind == "reminder":
            Appointment.objects.filter(pk=item.appointment_id, status="BOOKED", start=item.expected_start,
                notification_revision=item.expected_revision).update(reminder_sent_at=now)
    if changed:
        logger.info("Email outcome: id=%s kind=%s status=%s attempt=%s", item.pk, item.kind, status, item.attempts)
    else:
        logger.warning("Email worker lost lease before acknowledgement: id=%s", item.pk)


def process_one():
    item = _claim()
    if item is None:
        return False
    if item.status == "failed":
        return True
    try:
        reason = _stale_reason(item)
        if reason:
            _finish(item, "cancelled", reason)
            return True
        # No database locks or transaction remain open during SMTP I/O.
        sent = EmailMessage(item.subject, item.body, item.sender, [item.recipient],
            headers={"Message-ID": f"<sto-outbox-{item.pk}@sto.local>"}).send(fail_silently=False)
        if not sent:
            raise RuntimeError("MailBackendAcceptedNoMessage")
    except Exception as exc:
        # Never persist SMTP text: it can contain addresses or message fragments.
        logger.error("Email delivery failed: id=%s error=%s attempt=%s", item.pk, type(exc).__name__, item.attempts)
        _finish(item, "failed" if item.attempts >= MAX_ATTEMPTS else "pending", type(exc).__name__)
    else:
        _finish(item, "sent")
    return True
