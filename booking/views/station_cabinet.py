import csv
import logging
from datetime import date as date_type, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date, parse_time

from booking.models import Appointment, SlotBlock, StationSchedule, StationWeeklySchedule
from booking.station_access import get_user_stations, require_station_access

logger = logging.getLogger(__name__)


# ─── Выбор станции ────────────────────────────────────────────────────────────

@login_required
def station_select(request):
    """Если у пользователя одна станция — сразу редиректим на дашборд."""
    stations = get_user_stations(request.user)
    if not stations.exists():
        messages.error(request, "У вас нет доступа ни к одной станции")
        return redirect("home")
    if stations.count() == 1:
        return redirect("station_dashboard", station_id=stations.first().pk)

    import json
    stations_list = list(stations.values("id", "name", "address", "latitude", "longitude"))
    return render(request, "booking/station/select.html", {
        "stations": stations,
        "stations_json": json.dumps(stations_list, ensure_ascii=False),
    })


# ─── Дашборд ──────────────────────────────────────────────────────────────────

@login_required
@require_station_access()
def station_dashboard(request, station_id, staff=None):
    station = staff.station
    now = station.local_now()
    today = now.date()
    since = now - timedelta(days=30)
    appts = Appointment.objects.filter(station=station, start__gte=since)

    period_stats = appts.aggregate(
        total=Count("id"),
        done=Count("id", filter=Q(status="DONE")),
        cancelled=Count("id", filter=Q(status="CANCELLED")),
        no_show=Count("id", filter=Q(status="NO_SHOW")),
    )
    today_count = Appointment.objects.filter(
        station=station, start__date=today, status="BOOKED"
    ).count()
    upcoming_count = Appointment.objects.filter(
        station=station, start__gte=now, status="BOOKED"
    ).count()

    stats = {
        "total": period_stats["total"],
        "done": period_stats["done"],
        "cancelled": period_stats["cancelled"],
        "no_show": period_stats["no_show"],
        "today": today_count,
        "upcoming": upcoming_count,
    }

    upcoming = (
        Appointment.objects
        .filter(station=station, start__gte=now, status="BOOKED")
        .select_related("car__model__brand", "user__profile")
        .order_by("start")[:5]
    )

    return render(request, "booking/station/dashboard.html", {
        "station": station,
        "staff": staff,
        "stats": stats,
        "upcoming": upcoming,
        "now": now,
    })


# ─── Записи ───────────────────────────────────────────────────────────────────

@login_required
@require_station_access()
def station_appointments(request, station_id, staff=None):
    station = staff.station
    qs = (
        Appointment.objects
        .filter(station=station)
        .select_related("car__model__brand", "user__profile")
        .prefetch_related("photos")
        .order_by("-start")
    )

    status_filter = request.GET.get("status", "")
    date_filter = request.GET.get("date", "")
    search = request.GET.get("q", "").strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if date_filter:
        qs = qs.filter(start__date=date_filter)
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(phone__icontains=search) |
            Q(vin__icontains=search) |
            Q(car__plate_number__icontains=search)
        )

    return render(request, "booking/station/appointments.html", {
        "station": station,
        "staff": staff,
        "appointments": qs,
        "status_filter": status_filter,
        "date_filter": date_filter,
        "search": search,
        "status_choices": Appointment.STATUS_CHOICES,
        "now": station.local_now(),
    })


# ─── Экспорт CSV ──────────────────────────────────────────────────────────────

@login_required
@require_station_access()
def station_appointments_csv(request, station_id, staff=None):
    station = staff.station
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")

    qs = (
        Appointment.objects
        .filter(station=station)
        .select_related("car__model__brand", "user")
        .order_by("start")
    )
    if date_from:
        qs = qs.filter(start__date__gte=date_from)
    if date_to:
        qs = qs.filter(start__date__lte=date_to)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="appointments_{station.pk}.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(["Дата", "Время начала", "Время конца", "Клиент", "Телефон", "Госномер", "Марка/модель", "VIN", "Статус"])

    for appointment in qs:
        local_start = appointment.local_start
        local_end = appointment.local_end
        writer.writerow([
            local_start.strftime("%d.%m.%Y"),
            local_start.strftime("%H:%M"),
            local_end.strftime("%H:%M"),
            appointment.name,
            appointment.phone or "",
            appointment.car.plate_number,
            str(appointment.car.model),
            appointment.vin or "",
            appointment.get_status_display(),
        ])

    return response


# ─── Расписание ───────────────────────────────────────────────────────────────

@login_required
@require_station_access()
def station_schedule(request, station_id, staff=None):
    station = staff.station
    weekly = station.weekly_schedules.order_by("weekday")
    schedules = station.schedules.order_by("date")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save_weekly":
            weekly_values = []
            invalid = False
            for wd in range(7):
                ws_raw = request.POST.get(f"work_start_{wd}", "").strip()
                we_raw = request.POST.get(f"work_end_{wd}", "").strip()
                if not ws_raw and not we_raw:
                    weekly_values.append((wd, None, None))
                    continue
                if not ws_raw or not we_raw:
                    invalid = True
                    break
                ws = parse_time(ws_raw)
                we = parse_time(we_raw)
                if ws is None or we is None or ws >= we:
                    invalid = True
                    break
                weekly_values.append((wd, ws, we))

            if invalid:
                messages.error(request, "Проверьте недельный график: начало должно быть раньше окончания")
            else:
                # Validate the complete form before mutating any weekday so a
                # malformed later row cannot leave a partially saved schedule.
                with transaction.atomic():
                    for wd, ws, we in weekly_values:
                        if ws is None:
                            StationWeeklySchedule.objects.filter(
                                station=station, weekday=wd
                            ).delete()
                        else:
                            StationWeeklySchedule.objects.update_or_create(
                                station=station,
                                weekday=wd,
                                defaults={"work_start": ws, "work_end": we},
                            )
                messages.success(request, "Недельное расписание сохранено")

        elif action == "add_exception":
            schedule_date = parse_date(request.POST.get("date", "").strip())
            ws = parse_time(request.POST.get("work_start", "").strip())
            we = parse_time(request.POST.get("work_end", "").strip())
            if schedule_date is None or ws is None or we is None:
                messages.error(request, "Заполните корректные дату и время")
            elif ws > we:
                messages.error(request, "Начало работы не может быть позже окончания")
            else:
                # Equal times deliberately mean a day off and are used for
                # holidays as well as manually created exceptions.
                StationSchedule.objects.update_or_create(
                    station=station,
                    date=schedule_date,
                    defaults={"work_start": ws, "work_end": we},
                )
                messages.success(request, f"Исключение на {schedule_date.isoformat()} сохранено")

        elif action == "delete_exception":
            exc_id = request.POST.get("exception_id")
            StationSchedule.objects.filter(pk=exc_id, station=station).delete()
            messages.success(request, "Исключение удалено")

        elif action == "fill_holidays":
            try:
                import holidays as holidays_lib

                current_year = date_type.today().year
                year = int(request.POST.get("year", current_year))
                if year < current_year - 1 or year > current_year + 3:
                    raise ValueError("holiday year outside allowed UI range")

                ru_holidays = holidays_lib.Russia(years=year)
                created = skipped = 0
                for hdate, _hname in sorted(ru_holidays.items()):
                    _, was_created = StationSchedule.objects.get_or_create(
                        station=station, date=hdate,
                        defaults={"work_start": time(0, 0), "work_end": time(0, 0)}
                    )
                    if was_created:
                        created += 1
                    else:
                        skipped += 1
                if created:
                    messages.success(request, f"Добавлено {created} праздников на {year} год")
                if skipped:
                    messages.info(request, f"Пропущено {skipped} (уже существуют)")
            except (TypeError, ValueError):
                messages.error(request, "Выберите допустимый год для загрузки праздников")
            except Exception:
                logger.exception("Failed to fill holidays for station %s", station.pk)
                messages.error(request, "Не удалось заполнить праздники. Попробуйте позже.")

        return redirect("station_schedule", station_id=station_id)

    TIME_CHOICES = [("00:00", "00:00")] + [
        (f"{h:02d}:{m:02d}", f"{h:02d}:{m:02d}")
        for h in range(0, 24) for m in (0, 30)
        if not (h == 0 and m == 0)
    ]

    weekly_map = {ws.weekday: ws for ws in weekly}
    weekday_rows = []
    for wd_num, wd_name in StationWeeklySchedule.WEEKDAYS:
        ws_obj = weekly_map.get(wd_num)
        weekday_rows.append({
            "num": wd_num,
            "name": wd_name,
            "work_start": ws_obj.work_start.strftime("%H:%M") if ws_obj else "",
            "work_end": ws_obj.work_end.strftime("%H:%M") if ws_obj else "",
        })

    return render(request, "booking/station/schedule.html", {
        "station": station, "staff": staff, "weekday_rows": weekday_rows,
        "schedules": schedules, "time_choices": TIME_CHOICES,
    })


# ─── Блокировки слотов ────────────────────────────────────────────────────────

@login_required
@require_station_access()
def station_slot_blocks(request, station_id, staff=None):
    station = staff.station
    blocks = station.slot_blocks.select_related("created_by").order_by("-start")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            from django.utils.dateparse import parse_datetime
            from django.utils.timezone import make_aware, is_aware
            start_raw = parse_datetime(request.POST.get("start", ""))
            end_raw = parse_datetime(request.POST.get("end", ""))
            reason = request.POST.get("reason", "").strip()

            if not start_raw or not end_raw:
                messages.error(request, "Укажите время начала и конца блокировки")
            else:
                start = make_aware(start_raw) if not is_aware(start_raw) else start_raw
                end = make_aware(end_raw) if not is_aware(end_raw) else end_raw
                if start >= end:
                    messages.error(request, "Конец блокировки должен быть позже начала")
                else:
                    SlotBlock.objects.create(
                        station=station, start=start, end=end,
                        reason=reason, created_by=request.user,
                    )
                    messages.success(request, "Слот заблокирован")

        elif action == "delete":
            block_id = request.POST.get("block_id")
            SlotBlock.objects.filter(pk=block_id, station=station).delete()
            messages.success(request, "Блокировка снята")

        return redirect("station_slot_blocks", station_id=station_id)

    TIME_CHOICES = [
        (f"{h:02d}:{m:02d}", f"{h:02d}:{m:02d}")
        for h in range(0, 24) for m in (0, 30)
    ]
    return render(request, "booking/station/slot_blocks.html", {
        "station": station,
        "staff": staff,
        "blocks": blocks,
        "now": station.local_now(),
        "time_choices": TIME_CHOICES,
    })
