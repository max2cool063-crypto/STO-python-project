import logging
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run scheduled maintenance with observable outcomes for each command."

    def handle(self, *args, **options):
        failed = []
        for name in ("update_appointments", "send_reminders"):
            started = time.monotonic()
            logger.info("Maintenance started: command=%s", name)
            try:
                call_command(name, stdout=self.stdout, stderr=self.stderr)
            except Exception:
                logger.exception("Maintenance failed: command=%s", name)
                failed.append(name)
            else:
                logger.info("Maintenance completed: command=%s duration_seconds=%.3f", name, time.monotonic() - started)
        if failed:
            raise CommandError("Maintenance failed: " + ", ".join(failed))
