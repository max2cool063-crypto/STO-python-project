"""Validation shared by views that do not use a bound Django form."""
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date, parse_datetime, parse_time


def validate_user_fields(**values):
    user = get_user_model()(**values)
    for name, value in values.items():
        user._meta.get_field(name).clean(value, user)


def _parse(parser, value):
    try:
        return parser(value or "")
    except (TypeError, ValueError, OverflowError):
        return None


def safe_parse_datetime(value):
    return _parse(parse_datetime, value)


def safe_parse_date(value):
    return _parse(parse_date, value)


def safe_parse_time(value):
    return _parse(parse_time, value)
