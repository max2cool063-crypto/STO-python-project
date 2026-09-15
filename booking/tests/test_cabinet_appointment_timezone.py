from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.template import Context, Engine
from django.test import SimpleTestCase, override_settings
from django.utils import timezone


@override_settings(USE_TZ=True, TIME_ZONE="Europe/Moscow")
class CabinetAppointmentTimezoneTests(SimpleTestCase):
    def render_appointments(self, start, zones):
        engine = Engine(
            dirs=[str(Path(__file__).resolve().parents[2] / "templates")],
            loaders=[
                ("django.template.loaders.locmem.Loader", {
                    "base.html": "{% block content %}{% endblock %}",
                }),
                "django.template.loaders.filesystem.Loader",
            ],
            libraries={"static": "django.templatetags.static", "tz": "django.templatetags.tz"},
        )
        appointments = [SimpleNamespace(
            station=SimpleNamespace(name=zone, address="", timezone=zone),
            local_start=start.astimezone(ZoneInfo(zone)),
            local_end=(start + timedelta(minutes=30)).astimezone(ZoneInfo(zone)),
            status="DONE", car="Test car", notes="", photos=SimpleNamespace(all=[]),
        ) for zone in zones]
        with timezone.override("Europe/Moscow"):
            return engine.get_template("booking/cabinet/appointments.html").render(
                Context({"appointments": appointments})
            )

    def test_each_station_keeps_its_own_time(self):
        html = self.render_appointments(
            datetime(2026, 9, 14, 4, tzinfo=dt_timezone.utc),
            ["Europe/Samara", "Europe/Moscow"],
        )
        self.assertIn("14.09.2026 · 08:00–08:30", html)
        self.assertIn("14.09.2026 · 07:00–07:30", html)

    def test_station_date_is_preserved_across_midnight(self):
        html = self.render_appointments(
            datetime(2026, 9, 13, 20, 15, tzinfo=dt_timezone.utc),
            ["Europe/Samara"],
        )
        self.assertIn("14.09.2026 · 00:15–00:45", html)
        self.assertNotIn("13.09.2026 · 23:15", html)
