from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import render

from booking.models import Appointment, StationStaff
from booking.station_access import require_station_access


@login_required
@require_station_access()
def station_clients(request, station_id, staff=None):
    """Список клиентов станции доступен владельцу и оператору."""
    station = staff.station
    search = request.GET.get("q", "").strip()

    users_qs = (
        User.objects
        .filter(appointments__station=station)
        .distinct()
        .select_related("profile")
        .prefetch_related("appointments")
    )

    if search:
        users_qs = users_qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(profile__phone__icontains=search) |
            Q(email__icontains=search)
        )

    users_qs = users_qs.annotate(
        visit_count=Count(
            "appointments",
            filter=Q(appointments__station=station, appointments__status="DONE")
        )
    ).order_by("-visit_count")

    return render(request, "booking/station/clients.html", {
        "station": station,
        "staff": staff,
        "clients": users_qs,
        "search": search,
    })
