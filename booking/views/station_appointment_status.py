from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from booking.models import Appointment, AppointmentLog
from booking.notifications import notify_client_cancelled
from booking.station_access import require_station_access


@login_required
@require_station_access()
@require_POST
def station_appointment_status(request, station_id, pk, staff=None):
    """Atomically change an appointment status for the current station."""
    station = staff.station
    new_status = request.POST.get("status")

    if new_status not in dict(Appointment.STATUS_CHOICES):
        messages.error(request, "Недопустимый статус")
        return redirect("station_appointments", station_id=station_id)

    if new_status == "AWAITING_RESULT":
        messages.error(
            request,
            "Статус «Требует результата» устанавливается системой автоматически",
        )
        return redirect("station_appointments", station_id=station_id)

    comment = request.POST.get("comment", "").strip()

    try:
        with transaction.atomic():
            appt = get_object_or_404(
                Appointment.objects.select_for_update(),
                pk=pk,
                station=station,
            )
            old_status = appt.status

            if old_status in {"CANCELLED", "DONE", "NO_SHOW"}:
                messages.error(
                    request,
                    "Завершённую, отменённую или пропущенную запись нельзя изменить",
                )
                return redirect("station_appointments", station_id=station_id)

            if new_status == old_status:
                if comment:
                    appt.notes = (
                        (appt.notes + "\n" + comment).strip()
                        if appt.notes
                        else comment
                    )
                    appt.save(update_fields=["notes"])
                    messages.success(request, "Комментарий сохранён, статус не изменён")
                else:
                    messages.info(request, "Статус не изменён")
                return redirect("station_appointments", station_id=station_id)

            appt.status = new_status
            if comment:
                appt.notes = (
                    (appt.notes + "\n" + comment).strip()
                    if appt.notes
                    else comment
                )
            appt.save()

            AppointmentLog.objects.create(
                appointment=appt,
                changed_by=request.user,
                old_status=old_status,
                new_status=new_status,
                comment=comment,
            )

    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("station_appointments", station_id=station_id)

    if new_status == "CANCELLED" and old_status == "BOOKED":
        notify_client_cancelled(appt, cancelled_by_station=True)

    messages.success(request, f"Статус изменён: {appt.get_status_display()}")
    return redirect("station_appointments", station_id=station_id)
