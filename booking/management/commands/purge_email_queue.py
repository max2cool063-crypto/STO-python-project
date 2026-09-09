from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from booking.models import EmailOutbox


class Command(BaseCommand):
    help = "Delete sent/cancelled mail payloads older than the retention period."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        if options["days"] < 1:
            raise CommandError("days must be at least 1")
        deleted, _ = EmailOutbox.objects.filter(status__in=["sent", "cancelled"],
            finished_at__lt=timezone.now() - timedelta(days=options["days"])).delete()
        self.stdout.write(f"Email queue rows purged: {deleted}")
