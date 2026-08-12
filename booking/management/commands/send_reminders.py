from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from booking.models import Appointment
from booking.notifications import notify_client_reminder


class Command(BaseCommand):
    help = "Отправляет email-напоминания клиентам у которых ТО завтра. Запускать раз в день."

    def handle(self, *args, **options):
        now = timezone.now()
        # Окно: от 23 до 25 часов вперёд — чтобы не дублировать при повторном запуске
        window_start = now + timedelta(hours=23)
        window_end   = now + timedelta(hours=25)

        appointments = Appointment.objects.filter(
            status="BOOKED",
            start__gte=window_start,
            start__lte=window_end,
        ).select_related("user", "car__model__brand", "station")

        sent = 0
        for appt in appointments:
            if appt.user.email:
                notify_client_reminder(appt)
                sent += 1

        self.stdout.write(self.style.SUCCESS(f"Напоминаний отправлено: {sent}"))
