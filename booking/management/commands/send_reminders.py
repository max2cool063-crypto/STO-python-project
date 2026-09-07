from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from booking.models import Appointment
from booking.notifications import notify_client_reminder


class Command(BaseCommand):
    help = "Отправляет одно email-напоминание примерно за сутки до ТО. Можно запускать каждые 15 минут."

    def handle(self, *args, **options):
        now = timezone.now()
        window_start = now + timedelta(hours=23)
        window_end = now + timedelta(hours=25)

        appointment_ids = list(
            Appointment.objects.filter(
                status="BOOKED",
                reminder_sent_at__isnull=True,
                start__gte=window_start,
                start__lte=window_end,
            ).values_list("pk", flat=True)
        )

        sent = 0
        for appointment_id in appointment_ids:
            # Повторный запуск команды не должен отправлять второе письмо.
            # Блокировка строки также защищает от двух одновременно работающих
            # экземпляров команды.
            with transaction.atomic():
                appt = (
                    Appointment.objects.select_for_update()
                    .select_related("user", "car__model__brand", "station")
                    .filter(
                        pk=appointment_id,
                        status="BOOKED",
                        reminder_sent_at__isnull=True,
                        start__gte=window_start,
                        start__lte=window_end,
                    )
                    .first()
                )
                if not appt or not appt.user.email:
                    continue

                if notify_client_reminder(appt):
                    Appointment.objects.filter(pk=appt.pk).update(
                        reminder_sent_at=timezone.now()
                    )
                    sent += 1

        self.stdout.write(self.style.SUCCESS(f"Напоминаний отправлено: {sent}"))
