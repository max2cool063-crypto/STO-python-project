from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from booking.models import Appointment
from booking.station_access import require_station_access


@login_required
@require_station_access()
def station_appointment_detail(request, station_id, pk, staff=None):
    """Показывает запись только если она относится к станции оператора."""
    station = staff.station
    appointment = get_object_or_404(
        Appointment.objects.select_related("car__model__brand", "user").prefetch_related("photos"),
        pk=pk,
        station=station,
    )

    status_labels = dict(Appointment.STATUS_CHOICES)
    logs = [
        {
            "created_at": log.created_at,
            "changed_by": log.changed_by,
            "old_status": status_labels.get(log.old_status, log.old_status),
            "new_status": status_labels.get(log.new_status, log.new_status),
            "comment": log.comment,
        }
        for log in appointment.logs.select_related("changed_by").order_by("created_at")
    ]

    return render(request, "booking/station/appointment_detail.html", {
        "station": station,
        "staff": staff,
        "appointment": appointment,
        "photos": list(appointment.photos.all()),
        "logs": logs,
        "status_choices": Appointment.STATUS_CHOICES,
    })
