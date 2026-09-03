from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from booking.models import Appointment, SlotBlock
from booking.station_access import require_station_access


@login_required
@require_station_access()
def station_day_calendar(request, station_id, staff=None):
    """Операционный календарь станции на один день."""
    station = staff.station
    today = timezone.localdate()
    raw_date = request.GET.get("date", "").strip()
    try:
        selected_date = timezone.datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else today
    except ValueError:
        selected_date = today

    work_start, work_end = station.get_working_hours(selected_date)
    appointments = list(
        Appointment.objects.filter(station=station, start__date=selected_date)
        .exclude(status="CANCELLED")
        .select_related("car__model__brand")
        .order_by("start")
    )
    blocks = list(
        SlotBlock.objects.filter(station=station, start__date=selected_date).order_by("start")
    )

    slots = []
    if work_start and work_end and work_start < work_end:
        start = timezone.make_aware(timezone.datetime.combine(selected_date, work_start))
        finish = timezone.make_aware(timezone.datetime.combine(selected_date, work_end))
        step = timedelta(minutes=station.slot_duration)
        cursor = start
        now = timezone.now()
        while cursor + step <= finish:
            slot_end = cursor + step
            appointment = next((a for a in appointments if a.start < slot_end and a.end > cursor), None)
            block = next((b for b in blocks if b.start < slot_end and b.end > cursor), None)
            if appointment:
                state = "appointment"
            elif block:
                state = "blocked"
            elif cursor <= now:
                state = "past"
            else:
                state = "free"
            slots.append({"start": cursor, "end": slot_end, "state": state, "appointment": appointment, "block": block})
            cursor += step

    # The booking logic keeps each base slot occupied, but the UI should show
    # one card per appointment. This is especially important for trucks, which
    # occupy two consecutive base slots.
    calendar_slots = []
    rendered_appointment_ids = set()
    for slot in slots:
        appointment = slot["appointment"]
        if appointment:
            if appointment.pk in rendered_appointment_ids:
                continue
            rendered_appointment_ids.add(appointment.pk)
            calendar_slots.append({
                **slot,
                "start": appointment.start,
                "end": appointment.end,
            })
        else:
            calendar_slots.append(slot)

    summary = {
        "appointments": len({slot["appointment"].pk for slot in slots if slot["appointment"]}),
        "free": sum(1 for slot in slots if slot["state"] == "free"),
        "blocked": sum(1 for slot in slots if slot["state"] == "blocked"),
        "past": sum(1 for slot in slots if slot["state"] == "past"),
        "total": len(slots),
    }
    summary["occupied"] = sum(1 for slot in slots if slot["state"] == "appointment")

    return render(request, "booking/station/day_calendar.html", {
        "station": station,
        "staff": staff,
        "selected_date": selected_date,
        "previous_date": selected_date - timedelta(days=1),
        "next_date": selected_date + timedelta(days=1),
        "today": today,
        "work_start": work_start,
        "work_end": work_end,
        "slots": slots,
        "calendar_slots": calendar_slots,
        "summary": summary,
    })
