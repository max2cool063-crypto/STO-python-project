import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware

from booking.forms import PhotosUploadForm
from booking.models import Appointment, AppointmentLog, AppointmentPhoto
from booking.station_access import require_station_access

logger = logging.getLogger(__name__)


@login_required
@require_station_access()
def station_appointment_edit(request, station_id, pk, staff=None):
    """Редактирование данных записи сотрудником только своей станции."""
    station = staff.station
    appointment = get_object_or_404(
        Appointment.objects.select_related("car__model__brand", "user"),
        pk=pk,
        station=station,
    )

    if request.method == "POST":
        name = request.POST.get("client_name", "").strip()
        phone = request.POST.get("client_phone", "").strip()
        start_raw = parse_datetime(request.POST.get("start", ""))
        start = (
            station.make_local_datetime(start_raw.date(), start_raw.time())
            if start_raw and not is_aware(start_raw)
            else start_raw
        )
        notes = request.POST.get("notes", "").strip()
        files = request.FILES.getlist("photos")

        if not name:
            messages.error(request, "Укажите имя клиента")
            return redirect(request.path)
        if not start:
            messages.error(request, "Укажите дату и время")
            return redirect(request.path)
        if appointment.start <= timezone.now() and start != appointment.start:
            messages.error(request, "Прошедшую запись нельзя переносить")
            return redirect(request.path)
        if start < timezone.now():
            messages.error(request, "Нельзя перенести запись в прошлое")
            return redirect(request.path)

        photo_errors = PhotosUploadForm.validate_photos(files)
        if photo_errors:
            for error in photo_errors:
                messages.error(request, error)
            return redirect(request.path)

        old_start = appointment.start
        try:
            with transaction.atomic():
                appointment.name = name
                appointment.phone = phone or None
                appointment.start = start
                appointment.end = start
                appointment.notes = notes
                appointment.save()
                for uploaded in files:
                    AppointmentPhoto.objects.create(
                        appointment=appointment,
                        image=uploaded,
                    )

                if old_start != appointment.start:
                    AppointmentLog.objects.create(
                        appointment=appointment,
                        changed_by=request.user,
                        old_status=appointment.status,
                        new_status=appointment.status,
                        comment=(
                            f"Перенесено с {appointment.station.local_now().astimezone(old_start.tzinfo):%d.%m.%Y %H:%M} "
                            f"на {appointment.local_start:%d.%m.%Y %H:%M}"
                        ),
                    )

        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect(request.path)
        except Exception:
            logger.exception("Failed to edit appointment %s", appointment.pk)
            messages.error(request, "Не удалось сохранить изменения. Проверьте дату и время.")
            return redirect(request.path)

        messages.success(request, "Изменения записи сохранены")
        return redirect("station_appointment_detail", station_id=station_id, pk=appointment.pk)

    return render(request, "booking/station/appointment_edit.html", {
        "station": station,
        "staff": staff,
        "appointment": appointment,
        "now": station.local_now(),
    })
