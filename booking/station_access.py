"""
Вспомогательные функции проверки доступа к кабинету станции.
Использовать во всех views /station/.
"""
from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from booking.models import StationStaff, Station


def get_staff_record(user, station_id):
    """
    Возвращает активную запись StationStaff для пользователя и станции,
    или None если нет доступа.
    """
    return StationStaff.objects.filter(
        user=user,
        station_id=station_id,
        is_active=True,
    ).select_related("station").first()


def get_user_stations(user):
    """
    Возвращает QuerySet станций к которым у пользователя есть доступ (активный).
    """
    return Station.objects.filter(
        staff__user=user,
        staff__is_active=True,
    ).distinct()


def require_station_access(role=None):
    """
    Декоратор для views с аргументом station_id.
    role=None — любая роль (владелец или оператор)
    role='OWNER' — только владелец
    role='OPERATOR' — только оператор

    Прокидывает staff_record в kwargs чтобы не делать повторный запрос в view.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, station_id, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")

            staff = get_staff_record(request.user, station_id)
            if not staff:
                messages.error(request, "У вас нет доступа к этой станции")
                return redirect("station_select")

            if role == StationStaff.ROLE_OWNER and staff.role != StationStaff.ROLE_OWNER:
                messages.error(request, "Это действие доступно только владельцу станции")
                return redirect("station_dashboard", station_id=station_id)

            kwargs["staff"] = staff
            return view_func(request, station_id, *args, **kwargs)
        return wrapper
    return decorator
