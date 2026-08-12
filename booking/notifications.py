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


# ─── Клиентские уведомления ───────────────────────────────────────────────────

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
    if cancelled_by_station:
        reason = "Запись была отменена сотрудником станции."
    else:
        reason = "Вы отменили запись."
    _send(
        subject=f"Запись на ТО отменена — {appointment.station.name}",
        body=(
            f"Здравствуйте, {appointment.name}!\n\n"
            f"{reason}\n\n"
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


# ─── Уведомления персоналу станции ───────────────────────────────────────────

def notify_station_staff_booked(appointment):
    """
    Новая запись на станцию — уведомляем всех активных сотрудников.
    Вызывается из views/booking.py и views/station_cabinet.py.
    """
    from booking.models import StationStaff
    station = appointment.station
    recipients = list(
        StationStaff.objects
        .filter(station=station, is_active=True)
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
