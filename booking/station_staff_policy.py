from django.core.exceptions import ValidationError

from booking.models import StationStaff


SYSTEM_ADMIN_STAFF_MESSAGE = (
    "Системный администратор не может одновременно быть сотрудником станции"
)


def validate_station_staff_assignment(instance):
    """Validate immutable station identities and role/account separation."""
    if not instance.user_id or not instance.station_id:
        return

    if getattr(instance.user, "is_superuser", False):
        raise ValidationError({"user": SYSTEM_ADMIN_STAFF_MESSAGE})

    if instance.pk:
        current = (
            StationStaff.objects.filter(pk=instance.pk)
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

    other_roles = StationStaff.objects.filter(user_id=instance.user_id).exclude(pk=instance.pk)

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


def validate_system_admin_account(user):
    """Prevent an existing station identity from being promoted to system admin."""
    if (
        getattr(user, "pk", None)
        and getattr(user, "is_superuser", False)
        and StationStaff.objects.filter(user_id=user.pk).exists()
    ):
        raise ValidationError({"is_superuser": SYSTEM_ADMIN_STAFF_MESSAGE})
