from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone


DEFAULT_TIMEZONE = "Europe/Moscow"


def detect_timezone(latitude, longitude):
    """Return an IANA timezone for coordinates, or None when it cannot be determined."""
    if latitude is None or longitude is None:
        return None

    from timezonefinder import TimezoneFinder

    try:
        return TimezoneFinder().timezone_at(lng=float(longitude), lat=float(latitude))
    except (TypeError, ValueError):
        return None


def get_timezone(name=None):
    """Return a ZoneInfo instance with a safe application fallback."""
    timezone_name = name or DEFAULT_TIMEZONE or settings.TIME_ZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def make_station_datetime(station, value_date: date, value_time: time):
    """Build an aware datetime from a station-local date and time."""
    return datetime.combine(
        value_date,
        value_time,
        tzinfo=get_timezone(station.timezone),
    )


def station_localtime(station, value=None):
    """Convert an aware datetime to the station's local timezone."""
    return timezone.localtime(value or timezone.now(), get_timezone(station.timezone))


def station_localdate(station, value=None):
    """Return the station-local calendar date for an aware datetime."""
    return station_localtime(station, value).date()


def station_day_bounds(station, value_date: date):
    """Return the start/end aware datetimes for a station-local calendar day."""
    start = make_station_datetime(station, value_date, time.min)
    return start, start + timedelta(days=1)
