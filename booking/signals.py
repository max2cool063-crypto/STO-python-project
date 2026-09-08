from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from booking.models import Appointment, Station, StationStaff
from booking.station_staff_policy import (
    validate_station_staff_assignment as validate_station_staff_policy,
    validate_system_admin_account,
)


@receiver(post_save, sender=Station)
def deactivate_rsa_imported_station(sender, instance, created, **kwargs):
    """Stations created from the RSA registry must be reviewed before booking."""
    if created and instance.rsa_id and instance.is_active:
        sender.objects.filter(pk=instance.pk).update(is_active=False)


@receiver(pre_save, sender=StationStaff)
def validate_station_staff_assignment(sender, instance, **kwargs):
    """Keep station staff identities permanent and roles unambiguous."""
    validate_station_staff_policy(instance)


@receiver(pre_save, sender=User)
def validate_user_account_type(sender, instance, **kwargs):
    """Keep Django system administrators separate from station staff identities."""
    validate_system_admin_account(instance)


@receiver(pre_save, sender=Appointment)
def validate_appointment_status_transition(sender, instance, **kwargs):
    """Enforce the appointment workflow and protect terminal statuses."""
    if not instance.pk:
        return

    old_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )
    if old_status is None or old_status == instance.status:
        return

    allowed = {
        "BOOKED": {"AWAITING_RESULT", "CANCELLED", "DONE", "NO_SHOW"},
        "AWAITING_RESULT": {"DONE", "NO_SHOW"},
        "CANCELLED": set(),
        "DONE": set(),
        "NO_SHOW": set(),
    }
    if instance.status not in allowed.get(old_status, set()):
        raise ValidationError(
            f"Недопустимый переход статуса: {old_status} → {instance.status}"
        )
