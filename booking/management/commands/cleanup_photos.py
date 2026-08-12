from django.core.management.base import BaseCommand
from django.conf import settings
from booking.models import AppointmentPhoto
import os

class Command(BaseCommand):
    help = "Удаляет файлы фото у которых нет записи в БД"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать что будет удалено, не удалять",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        media_dir = settings.MEDIA_ROOT / "appointments"

        if not media_dir.exists():
            self.stdout.write("Папка appointments/ не найдена")
            return

        # Все файлы которые есть в БД
        known = set(
            AppointmentPhoto.objects
            .values_list("image", flat=True)
        )

        removed = 0
        for filename in media_dir.iterdir():
            relative = f"appointments/{filename.name}"
            if relative not in known:
                if dry_run:
                    self.stdout.write(f"Будет удалён: {filename.name}")
                else:
                    filename.unlink()
                    self.stdout.write(f"Удалён: {filename.name}")
                removed += 1

        self.stdout.write(
            self.style.SUCCESS(f"Итого: {removed} файлов")
        )