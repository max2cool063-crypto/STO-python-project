"""
Все email-уведомления проекта в одном месте.
Все функции используют fail_silently=True — ошибка отправки
не должна ломать основной бизнес-процесс.
"""
from django.core.mail import send_mail as _send_mail
from django.conf import settings


def _send(subject, body, recipients):
    """Базовая отправка — фильтрует пустые адреса."""
    to = [r for r in recipients if r and "@" in r]
    if not to:
        return
    try:
        _send_mail(subject, body, settings.DEFAULT_FROM_EMAIL or None, to, fail_silently=True)
    except Exception:
        pass


def notify_client_booked(appointment):
    """Клиент записался на ТО — подтверждение."""
    email = appointment.user.email
    if not email:
        return
    _send(
        subject=f"Запись на ТО подтверждена — {appointment.station.name}",
        body=(
            f"Здравствуйте, {appointment.name}!\n\n"
            f"Ваша запись на технический осмотр подтверждена.\n\n"
            f"Станция: {appointment.station.name}\n"
            f"Адрес: {appointment.station.address}\n"
            f"Дата и время: {appointment.start.strftime('%d.%m.%Y в %H:%M')}\n"
            f"Автомобиль: {appointment.car}\n\n"
            f"Если вы не сможете приехать — отмените запись в личном кабинете.\n"
        ),
        recipients=[email],
    )


def notify_client_cancelled(appointment, cancelled_by_station=False):
    """Запись отменена — уведомляем клиента."""
    email = appointment.user.email
    if not email:
        return
    reason = "Запись была отменена сотрудником станции." if cancelled_by_station else "Вы отменили запись."
    _send(
        subject=f"Запись на ТО отменена — {appointment.station.name}",
        body=(
            f"Здравствуйте, {appointment.name}!\n\n{reason}\n\n"
            f"Станция: {appointment.station.name}\n"
            f"Дата и время: {appointment.start.strftime('%d.%m.%Y в %H:%M')}\n"
            f"Автомобиль: {appointment.car}\n\n"
            f"Вы можете записаться на другое время на нашем сайте.\n"
        ),
        recipients=[email],
    )


def notify_client_reminder(appointment):
    """Напоминание клиенту за день до ТО."""
    email = appointment.user.email
    if not email:
        return
    _send(
        subject=f"Напоминание: завтра ТО — {appointment.station.name}",
        body=(
            f"Здравствуйте, {appointment.name}!\n\n"
            f"Напоминаем, что завтра у вас запись на технический осмотр.\n\n"
            f"Станция: {appointment.station.name}\n"
            f"Адрес: {appointment.station.address}\n"
            f"Время: {appointment.start.strftime('%H:%M')}\n"
            f"Автомобиль: {appointment.car}\n\n"
            f"Если вы не сможете приехать — отмените запись в личном кабинете.\n"
        ),
        recipients=[email],
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
    _send(
        subject=f"Новая запись на ТО — {station.name}",
        body=(
            f"Новая запись на {appointment.start.strftime('%d.%m.%Y в %H:%M')}.\n\n"
            f"Клиент: {appointment.name}\n"
            f"Телефон: {appointment.phone or '—'}\n"
            f"Автомобиль: {appointment.car}\n"
            f"VIN: {appointment.vin or '—'}\n"
        ),
        recipients=recipients,
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

    client = appointment.name or appointment.user.get_full_name() or appointment.user.username
    message = (
        f"Клиент: {client}\n"
        f"Автомобиль: {appointment.car}\n"
        f"Дата и время: {appointment.start.strftime('%d.%m.%Y в %H:%M')}"
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
        return 0
    return len(staff_ids)
