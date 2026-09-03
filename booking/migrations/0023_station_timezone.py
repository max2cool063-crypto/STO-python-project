from django.conf import settings
from django.db import migrations, models


def populate_station_timezones(apps, schema_editor):
    Station = apps.get_model("booking", "Station")
    try:
        from timezonefinder import TimezoneFinder
    except ImportError:
        TimezoneFinder = None

    finder = TimezoneFinder() if TimezoneFinder else None
    fallback = getattr(settings, "TIME_ZONE", "Europe/Moscow")

    for station in Station.objects.all().iterator():
        timezone_name = None
        if finder and station.latitude is not None and station.longitude is not None:
            try:
                timezone_name = finder.timezone_at(
                    lng=float(station.longitude),
                    lat=float(station.latitude),
                )
            except (TypeError, ValueError):
                timezone_name = None

        station.timezone = timezone_name or fallback
        station.save(update_fields=["timezone"])


def reverse_station_timezones(apps, schema_editor):
    Station = apps.get_model("booking", "Station")
    Station.objects.all().update(timezone="")


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0022_stationstaff_receive_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="station",
            name="timezone",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
                verbose_name="Часовой пояс",
            ),
        ),
        migrations.RunPython(populate_station_timezones, reverse_station_timezones),
    ]
