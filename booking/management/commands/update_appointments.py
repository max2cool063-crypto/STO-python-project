from django.core.management.base import BaseCommand
from django.utils import timezone
from booking.models import Appointment


class Command(BaseCommand):
    help = "Автоматически переводит прошедшие записи в статус DONE. Запускать через cron каждые 15 минут."

    def handle(self, *args, **options):
        count = Appointment.objects.filter(
            status="BOOKED",
            end__lt=timezone.now(),
        ).update(status="DONE")

        self.stdout.write(self.style.SUCCESS(f"Обновлено записей: {count}"))
