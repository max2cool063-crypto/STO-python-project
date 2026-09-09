"""
Все email-уведомления проекта в одном месте.
Письма сохраняются в transactional outbox. Отправка выполняется отдельным worker.
"""
import logging

from django.conf import settings
from booking.email_queue import enqueue_mail

logger = logging.getLogger(__name__)


def _send(subject, body, recipients, *, kind, appointment):
    """True means persisted/previously queued, not delivered."""
    return enqueue_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients,
        event_key=f"{kind}:{appointment.pk}:{appointment.notification_revision}",
        kind=kind, appointment=appointment) > 0


def notify_client_booked(appointment):
    """Клиент записался на ТО — подтверждение."""
    email = appointment.user.email
    if not email:
        return
    local_start = appointment.local_start
    _send(
        subject=f"Запись на ТО подтверждена — {appointment.station.name}",
        body=(
            f"Здравствуйте, {appointment.name}!\n\n"
            f"Ваша запись на технический осмотр подтверждена.\n\n"
            f"Станция: {appointment.station.name}\n"
            f"Адрес: {appointment.station.address}\n"
            f"Дата и время: {local_start.strftime('%d.%m.%Y в %H:%M')}\n"
            f"Автомобиль: {appointment.car}\n\n"
            f"Если вы не сможете приехать — отмените запись в личном кабинете.\n"
        ),
        recipients=[email],
        kind="booking", appointment=appointment,
    )


def notify_client_cancelled(appointment, cancelled_by_station=False):
    """Запись отменена — уведомляем клиента."""
    email = appointment.user.email
    if not email:
        return
    local_start = appointment.local_start
    reason = "Запись была отменена сотрудником станции." if cancelled_by_station else "Вы отменили запись."
    _send(
        subject=f"Запись на ТО отменена — {appointment.station.name}",
        body=(
            f"Здравствуйте, {appointment.name}!\n\n{reason}\n\n"
            f"Станция: {appointment.station.name}\n"
            f"Дата и время: {local_start.strftime('%d.%m.%Y в %H:%M')}\n"
            f"Автомобиль: {appointment.car}\n\n"
            f"Вы можете записаться на другое время на нашем сайте.\n"
        ),
        recipients=[email],
        kind="cancellation", appointment=appointment,
    )


def notify_client_reminder(appointment):
    """Напоминание клиенту за день до ТО. True означает сохранение в очереди."""
    email = appointment.user.email
    if not email:
        return False
    local_start = appointment.local_start
    return _send(
        subject=f"Напоминание: завтра ТО — {appointment.station.name}",
        body=(
            f"Здравствуйте, {appointment.name}!\n\n"
            f"Напоминаем, что завтра у вас запись на технический осмотр.\n\n"
            f"Станция: {appointment.station.name}\n"
            f"Адрес: {appointment.station.address}\n"
            f"Время: {local_start.strftime('%H:%M')}\n"
            f"Автомобиль: {appointment.car}\n\n"
            f"Если вы не сможете приехать — отмените запись в личном кабинете.\n"
        ),
        recipients=[email],
        kind="reminder", appointment=appointment,
    )


def notify_station_staff_booked(appointment):
    """Новая запись на станцию — email всем активным сотрудникам с включёнными уведомлениями."""
    from booking.models import StationStaff
    station = appointment.station
    recipients = list(
        StationStaff.objects.filter(
            station=station,
            is_active=True,
            receive_notifications=True,
        )
        .exclude(user__email="")
        .values_list("user__email", flat=True)
    )
    if not recipients:
        return
    local_start = appointment.local_start
    _send(
        subject=f"Новая запись на ТО — {station.name}",
        body=(
            f"Новая запись на {local_start.strftime('%d.%m.%Y в %H:%M')}.\n\n"
            f"Клиент: {appointment.name}\n"
            f"Телефон: {appointment.phone or '—'}\n"
            f"Автомобиль: {appointment.car}\n"
            f"VIN: {appointment.vin or '—'}\n"
        ),
        recipients=recipients,
        kind="staff_booking", appointment=appointment,
    )


def notify_station_staff_cancelled(appointment):
    """Клиент самостоятельно отменил запись — email активным сотрудникам станции."""
    from booking.models import StationStaff

    station = appointment.station
    recipients = list(
        StationStaff.objects.filter(
            station=station,
            is_active=True,
            receive_notifications=True,
        )
        .exclude(user__email="")
        .values_list("user__email", flat=True)
    )
    if not recipients:
        return

    local_start = appointment.local_start
    _send(
        subject=f"Клиент отменил запись — {station.name}",
        body=(
            f"Клиент самостоятельно отменил запись на технический осмотр.\n\n"
            f"Клиент: {appointment.name}\n"
            f"Телефон: {appointment.phone or '—'}\n"
            f"Автомобиль: {appointment.car}\n"
            f"VIN: {appointment.vin or '—'}\n"
            f"Дата и время: {local_start.strftime('%d.%m.%Y в %H:%M')}\n"
        ),
        recipients=recipients,
        kind="staff_cancellation", appointment=appointment,
    )


def create_station_staff_notifications(appointment):
    """Создаёт внутренние уведомления активным сотрудникам станции, у которых они включены."""
    from booking.models import Notification, StationStaff

    station = appointment.station
    staff_ids = list(
        StationStaff.objects.filter(
            station=station,
            is_active=True,
            receive_notifications=True,
        ).values_list("user_id", flat=True)
    )
    if not staff_ids:
        return 0

    local_start = appointment.local_start
    client = appointment.name or appointment.user.get_full_name() or appointment.user.username
    message = (
        f"Клиент: {client}\n"
        f"Автомобиль: {appointment.car}\n"
        f"Дата и время: {local_start.strftime('%d.%m.%Y в %H:%M')}"
    )
    try:
        Notification.objects.bulk_create([
            Notification(
                recipient_id=user_id,
                station=station,
                appointment=appointment,
                notification_type=Notification.TYPE_NEW_APPOINTMENT,
                title="Новая запись",
                message=message,
            )
            for user_id in staff_ids
        ])
    except Exception:
        # Внутреннее уведомление не должно отменять уже созданную запись.
        logger.exception("Failed to create booking notifications: appointment_id=%s", appointment.pk)
        return 0
    return len(staff_ids)


def create_station_staff_cancellation_notifications(appointment):
    """Создаёт внутреннее уведомление владельцу/оператору о самостоятельной отмене клиентом."""
    from booking.models import Notification, StationStaff

    station = appointment.station
    staff_ids = list(
        StationStaff.objects.filter(
            station=station,
            is_active=True,
            receive_notifications=True,
        ).values_list("user_id", flat=True)
    )
    if not staff_ids:
        return 0

    local_start = appointment.local_start
    message = (
        f"Клиент: {appointment.name}\n"
        f"Телефон: {appointment.phone or '—'}\n"
        f"Автомобиль: {appointment.car}\n"
        f"VIN: {appointment.vin or '—'}\n"
        f"Дата и время: {local_start.strftime('%d.%m.%Y в %H:%M')}"
    )
    try:
        Notification.objects.bulk_create([
            Notification(
                recipient_id=user_id,
                station=station,
                appointment=appointment,
                notification_type=Notification.TYPE_APPOINTMENT_CANCELLED,
                title="Клиент отменил запись",
                message=message,
            )
            for user_id in staff_ids
        ])
    except Exception:
        logger.exception("Failed to create cancellation notifications: appointment_id=%s", appointment.pk)
        return 0
    return len(staff_ids)
