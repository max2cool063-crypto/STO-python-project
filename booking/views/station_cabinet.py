import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_POST

from booking.models import (
    Appointment, AppointmentLog, Car, CarModel, SlotBlock,
    Station, StationSchedule, StationStaff, StationWeeklySchedule,
    UserProfile,
)
from booking.station_access import get_user_stations, require_station_access
from booking.notifications import notify_station_staff_booked, notify_client_booked, notify_client_cancelled


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
    now = timezone.now()
    today = now.date()
    since = now - timedelta(days=30)
    appts = Appointment.objects.filter(station=station, start__gte=since)

    stats = {
        "total": appts.count(),
        "done": appts.filter(status="DONE").count(),
        "cancelled": appts.filter(status="CANCELLED").count(),
        "no_show": appts.filter(status="NO_SHOW").count(),
        "today": Appointment.objects.filter(
            station=station, start__date=today, status="BOOKED"
        ).count(),
        "upcoming": Appointment.objects.filter(
            station=station, start__gte=now, status="BOOKED"
        ).count(),
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
        "now": timezone.now(),
    })


@login_required
@require_station_access()
def station_appointment_create(request, station_id, staff=None):
    """Оператор/владелец создаёт запись вручную."""
    station = staff.station

    if request.method == "POST":
        from django.utils.dateparse import parse_datetime
        from django.utils.timezone import make_aware, is_aware
        from django.db import transaction

        car_id = request.POST.get("car_id", "").strip()
        start_s = request.POST.get("start", "")
        client_name = request.POST.get("client_name", "").strip()
        client_phone = request.POST.get("client_phone", "").strip()
        start_raw = parse_datetime(start_s)
        start = make_aware(start_raw) if start_raw and not is_aware(start_raw) else start_raw

        if not start:
            messages.error(request, "Не выбрано время записи")
            return redirect(request.path)

        if not client_name:
            messages.error(request, "Укажите имя клиента")
            return redirect(request.path)

        if start < timezone.now():
            messages.error(request, "Нельзя записать в прошлое")
            return redirect(request.path)

        if not car_id:
            plate = request.POST.get("plate", "").strip().upper()
            model_id = request.POST.get("new_model_id", "").strip()
            email = request.POST.get("new_user_email", "").strip().lower()

            if not plate or not model_id or not email:
                messages.error(request, "Для нового автомобиля укажите госномер, модель и email клиента")
                return redirect(request.path)

            from django.utils.crypto import get_random_string
            from django.core.mail import send_mail as _send_mail
            client_user, user_created = User.objects.get_or_create(
                email=email, defaults={"username": email}
            )
            if user_created:
                pwd = get_random_string(12)
                client_user.set_password(pwd)
                client_user.save()
                try:
                    _send_mail(
                        "Доступ к сервису СТО",
                        f"Для вас создана запись на ТО.\nВход: {email}\nПароль: {pwd}",
                        None, [email], fail_silently=True,
                    )
                except Exception:
                    pass

            car = Car.objects.create(
                owner=client_user,
                model_id=int(model_id),
                plate_number=plate,
            )
        else:
            car = get_object_or_404(Car, id=car_id, is_active=True)

        try:
            with transaction.atomic():
                locked_station = Station.objects.select_for_update().get(pk=station.pk)
                appointment = Appointment.objects.create(
                    station=locked_station,
                    user=car.owner,
                    car=car,
                    start=start,
                    end=start,
                    name=client_name,
                    phone=client_phone or None,
                    vin=car.vin,
                )
        except Exception as e:
            messages.error(request, f"Не удалось создать запись: {e}")
            return redirect(request.path)

        notify_station_staff_booked(appointment)
        notify_client_booked(appointment)
        messages.success(request, "Запись создана")
        return redirect("station_appointments", station_id=station_id)

    return render(request, "booking/station/appointment_create.html", {
        "station": station,
        "staff": staff,
        "today": timezone.now().date(),
    })


@login_required
@require_station_access()
@require_POST
def station_appointment_status(request, station_id, pk, staff=None):
    """Быстрая смена статуса записи."""
    station = staff.station
    appt = get_object_or_404(Appointment, pk=pk, station=station)
    new_status = request.POST.get("status")

    if new_status not in dict(Appointment.STATUS_CHOICES):
        messages.error(request, "Недопустимый статус")
        return redirect("station_appointments", station_id=station_id)

    old_status = appt.status
    comment = request.POST.get("comment", "").strip()
    appt.status = new_status
    if comment:
        appt.notes = (appt.notes + "\n" + comment).strip() if appt.notes else comment
    appt.save()
    AppointmentLog.objects.create(
        appointment=appt,
        changed_by=request.user,
        old_status=old_status,
        new_status=new_status,
        comment=comment,
    )
    if new_status == "CANCELLED" and old_status == "BOOKED":
        notify_client_cancelled(appt, cancelled_by_station=True)
    messages.success(request, f"Статус изменён: {appt.get_status_display()}")
    return redirect("station_appointments", station_id=station_id)


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

    for a in qs:
        writer.writerow([
            a.start.strftime("%d.%m.%Y"), a.start.strftime("%H:%M"), a.end.strftime("%H:%M"),
            a.name, a.phone or "", a.car.plate_number, str(a.car.model), a.vin or "", a.get_status_display(),
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
            for wd in range(7):
                ws = request.POST.get(f"work_start_{wd}", "").strip()
                we = request.POST.get(f"work_end_{wd}", "").strip()
                if ws and we:
                    StationWeeklySchedule.objects.update_or_create(
                        station=station, weekday=wd,
                        defaults={"work_start": ws, "work_end": we},
                    )
                else:
                    StationWeeklySchedule.objects.filter(station=station, weekday=wd).delete()
            messages.success(request, "Недельное расписание сохранено")

        elif action == "add_exception":
            date = request.POST.get("date", "").strip()
            ws = request.POST.get("work_start", "").strip()
            we = request.POST.get("work_end", "").strip()
            if date and ws and we:
                StationSchedule.objects.update_or_create(
                    station=station, date=date,
                    defaults={"work_start": ws, "work_end": we},
                )
                messages.success(request, f"Исключение на {date} сохранено")
            else:
                messages.error(request, "Заполните дату и время")

        elif action == "delete_exception":
            exc_id = request.POST.get("exception_id")
            StationSchedule.objects.filter(pk=exc_id, station=station).delete()
            messages.success(request, "Исключение удалено")

        elif action == "fill_holidays":
            try:
                import holidays as holidays_lib
                from datetime import date as date_type, time
                year = int(request.POST.get("year", date_type.today().year))
                ru_holidays = holidays_lib.Russia(years=year)
                created = skipped = 0
                for hdate, hname in sorted(ru_holidays.items()):
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
            except Exception as e:
                messages.error(request, f"Ошибка: {e}")

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
        "station": station, "staff": staff, "blocks": blocks,
        "now": timezone.now(), "time_choices": TIME_CHOICES,
    })


# ─── Клиенты (только владелец) ────────────────────────────────────────────────

@login_required
@require_station_access(role=StationStaff.ROLE_OWNER)
def station_clients(request, station_id, staff=None):
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
            Q(profile__first_name__icontains=search) |
            Q(profile__last_name__icontains=search) |
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
        "station": station, "staff": staff, "clients": users_qs, "search": search,
    })


# ─── Персонал ─────────────────────────────────────────────────────────────────

@login_required
@require_station_access(role=StationStaff.ROLE_OWNER)
def station_staff(request, station_id, staff=None):
    """Управление сотрудниками станции доступно только владельцу."""
    station = staff.station
    staff_list = (
        StationStaff.objects
        .filter(station=station)
        .select_related("user__profile", "created_by")
        .order_by("role", "-is_active", "created_at")
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_operator":
            login = request.POST.get("login", "").strip()
            password = request.POST.get("password", "").strip()
            email = request.POST.get("email", "").strip().lower()

            if not login:
                messages.error(request, "Укажите логин для оператора")
                return redirect(request.path)

            if len(password) < 8:
                messages.error(request, "Пароль должен быть не менее 8 символов")
                return redirect(request.path)

            if User.objects.filter(username=login).exists():
                messages.error(request, f"Логин «{login}» уже занят, выберите другой")
                return redirect(request.path)

            if email and StationStaff.objects.filter(station=station, user__email=email).exists():
                messages.error(request, "Пользователь с таким email уже является сотрудником станции")
                return redirect(request.path)

            new_user = User.objects.create_user(
                username=login,
                email=email if email else "",
                password=password,
            )

            if email and "@" in email:
                try:
                    send_mail(
                        "Доступ к кабинету станции СТО",
                        f"Вас добавили как оператора станции «{station.name}».\n"
                        f"Логин: {login}\nПароль: {password}\n\n"
                        f"Рекомендуем сменить пароль после первого входа.",
                        None, [email], fail_silently=True,
                    )
                except Exception:
                    pass

            StationStaff.objects.create(
                station=station,
                user=new_user,
                role=StationStaff.ROLE_OPERATOR,
                created_by=request.user,
            )
            messages.success(request, f"Оператор «{login}» создан")

        elif action == "toggle_active":
            member_id = request.POST.get("member_id")
            member = get_object_or_404(StationStaff, pk=member_id, station=station)
            if member.user == request.user:
                messages.error(request, "Нельзя деактивировать себя")
            else:
                member.is_active = not member.is_active
                member.save()
                status_str = "активирован" if member.is_active else "деактивирован"
                messages.success(request, f"Сотрудник {status_str}")

        elif action == "reset_password":
            member_id = request.POST.get("member_id")
            new_password = request.POST.get("new_password", "").strip()
            member = get_object_or_404(StationStaff, pk=member_id, station=station)
            if len(new_password) < 8:
                messages.error(request, "Пароль должен быть не менее 8 символов")
            elif member.user == request.user:
                messages.error(request, "Для смены своего пароля используйте раздел профиля")
            else:
                member.user.set_password(new_password)
                member.user.save()
                messages.success(request, f"Пароль сотрудника «{member.user.username}» изменён")

        return redirect("station_staff", station_id=station_id)

    return render(request, "booking/station/staff.html", {
        "station": station, "staff": staff, "staff_list": staff_list,
    })


# ─── Детальная страница записи ────────────────────────────────────────────────

@login_required
@require_station_access()
def station_appointment_detail(request, station_id, pk, staff=None):
    station = staff.station
    appointment = get_object_or_404(Appointment, pk=pk, station=station)
    logs = appointment.logs.select_related("changed_by").order_by("created_at")
    return render(request, "booking/station/appointment_detail.html", {
        "station": station,
        "staff": staff,
        "appointment": appointment,
        "logs": logs,
    })
