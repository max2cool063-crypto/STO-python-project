from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from booking.models import StationStaff


DEACTIVATED_STAFF_MESSAGE = "Доступ учётной записи сотрудника деактивирован"
STAFF_ONLY_MESSAGE = "Учётная запись сотрудника предназначена только для кабинета станции"
STATION_ONLY_MESSAGE = "Этот раздел доступен только сотрудникам станции"


def get_station_account_state(user):
    """Return (has_staff_history, has_active_role) for an authenticated user."""
    if not getattr(user, "is_authenticated", False):
        return False, False

    states = list(
        StationStaff.objects.filter(user_id=user.pk)
        .values_list("is_active", flat=True)
    )
    return bool(states), any(states)


def require_active_station_account(view_func):
    """Allow account-level station pages only to staff with an active role."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        has_staff_history, has_active_role = get_station_account_state(request.user)
        if not has_staff_history:
            messages.error(request, STATION_ONLY_MESSAGE)
            return redirect("cabinet")
        if not has_active_role:
            logout(request)
            messages.error(request, DEACTIVATED_STAFF_MESSAGE)
            return redirect("login")

        return view_func(request, *args, **kwargs)

    return wrapper
