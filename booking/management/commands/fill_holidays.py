from django.core.management.base import BaseCommand
from booking.models import Station, StationSchedule
import holidays
from datetime import time

class Command(BaseCommand):
    help = "Заполняет исключения для российских праздников"

    def add_arguments(self, parser):
        parser.add_argument("year", type=int)

    def handle(self, *args, **options):
        year = options["year"]
        ru_holidays = holidays.Russia(years=year)
        stations = Station.objects.all()
        created = 0
        for station in stations:
            for date, name in ru_holidays.items():
                obj, was_created = StationSchedule.objects.get_or_create(
                    station=station,
                    date=date,
                    defaults={"work_start": time(0, 0), "work_end": time(0, 0)}
                )
                if was_created:
                    created += 1
                    self.stdout.write(f"  {date} — {name}")
        self.stdout.write(self.style.SUCCESS(f"Создано {created} исключений"))