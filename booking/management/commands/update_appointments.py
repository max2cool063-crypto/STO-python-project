from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from booking.models import Appointment, AppointmentLog


class Command(BaseCommand):
    help = (
        "Переводит прошедшие BOOKED-записи в AWAITING_RESULT, чтобы оператор "
        "явно зафиксировал DONE или NO_SHOW. Запускать через cron каждые 15 минут."
    )

    def handle(self, *args, **options):
        now = timezone.now()
        count = 0

        with transaction.atomic():
            appointments = (
                Appointment.objects.select_for_update()
                .filter(status="BOOKED", end__lt=now)
                .order_by("pk")
            )

            for appointment in appointments:
                appointment.status = "AWAITING_RESULT"
                appointment.save(update_fields=["status"])
                AppointmentLog.objects.create(
                    appointment=appointment,
                    changed_by=None,
                    old_status="BOOKED",
                    new_status="AWAITING_RESULT",
                    comment="Время записи завершилось — требуется результат визита",
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Ожидают результата: {count}"))
