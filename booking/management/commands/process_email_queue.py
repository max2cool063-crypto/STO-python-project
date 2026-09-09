import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from booking.email_queue import process_one

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deliver queued email; --loop polls continuously every five seconds."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, **options):
        if options["batch_size"] < 1:
            raise CommandError("batch-size must be positive")
        while True:
            try:
                processed = 0
                while processed < options["batch_size"] and process_one():
                    processed += 1
                if processed or not options["loop"]:
                    self.stdout.write(f"Email queue items processed: {processed}")
            except Exception:
                logger.exception("Email queue batch failed")
                if not options["loop"]:
                    raise CommandError("Email queue batch failed; inspect application logs")
            if not options["loop"]:
                return
            close_old_connections()
            time.sleep(5)
