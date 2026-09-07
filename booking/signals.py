from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from booking.models import Appointment, Station, StationStaff


@receiver(post_save, sender=Station)
def deactivate_rsa_imported_station(sender, instance, created, **kwargs):
    """Stations created from the RSA registry must be reviewed before booking."""
    if created and instance.rsa_id and instance.is_active:
        sender.objects.filter(pk=instance.pk).update(is_active=False)


@receiver(pre_save, sender=StationStaff)
def validate_station_staff_assignment(sender, instance, **kwargs):
    """Keep station staff identities permanent and roles unambiguous."""
    if not instance.user_id or not instance.station_id:
        return

    if instance.pk:
        current = (
            sender.objects.filter(pk=instance.pk)
            .values("user_id", "station_id", "role")
            .first()
        )
        if current:
            errors = {}
            if current["user_id"] != instance.user_id:
                errors["user"] = "Нельзя изменить учётную запись существующего сотрудника"
            if current["station_id"] != instance.station_id:
                errors["station"] = "Нельзя перенести существующего сотрудника на другую станцию"
            if current["role"] != instance.role:
                errors["role"] = "Роль существующего сотрудника нельзя изменять"
            if errors:
                raise ValidationError(errors)

    other_roles = sender.objects.filter(user_id=instance.user_id).exclude(pk=instance.pk)

    if instance.role == StationStaff.ROLE_OPERATOR:
        if other_roles.exists():
            raise ValidationError(
                {"user": "Учётная запись оператора навсегда привязана только к одной станции"}
            )
    elif instance.role == StationStaff.ROLE_OWNER:
        if other_roles.filter(role=StationStaff.ROLE_OPERATOR).exists():
            raise ValidationError(
                {"user": "Учётная запись оператора не может использоваться как учётная запись владельца"}
            )


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
