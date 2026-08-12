from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from booking.models import Station, Appointment, Car, AppointmentPhoto, UserProfile
from booking.forms import PhotosUploadForm
from booking.notifications import notify_station_staff_booked, notify_client_booked


@login_required
def book_station(request, pk):
    station = get_object_or_404(Station, pk=pk, is_active=True)
    cars = Car.objects.filter(
        owner=request.user, is_active=True
    ).select_related("model__brand")

    if request.method == "POST":
        start = parse_datetime(request.POST.get("start"))
        car_id = request.POST.get("car")

        if not start:
            messages.error(request, "Некорректная дата или время")
            return redirect(request.path)

        if start < timezone.now():
            messages.error(request, "Нельзя записаться в прошлое")
            return redirect(request.path)

        # Защита от IDOR: машина должна принадлежать пользователю
        car = get_object_or_404(Car, id=car_id, owner=request.user, is_active=True)

        # FIX: валидация фото ДО создания записи (раньше запись создавалась
        # сразу и удалялась при ошибке — неатомарно, могли оставаться мусорные записи)
        files = request.FILES.getlist("photos")
        if files:
            photo_errors = PhotosUploadForm.validate_photos(files)
            if photo_errors:
                for err in photo_errors:
                    messages.error(request, err)
                return redirect(request.path)

        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        # FIX: transaction.atomic() + select_for_update() полностью исключают
        # двойное бронирование одного слота при одновременных запросах.
        # select_for_update() ставит блокировку на строку станции — второй запрос
        # ждёт пока первый не закоммитит транзакцию, и только потом проходит clean().
        try:
            with transaction.atomic():
                station = Station.objects.select_for_update().get(pk=station.pk)
                appointment = Appointment.objects.create(
                    station=station,
                    user=request.user,
                    car=car,
                    start=start,
                    end=start,  # placeholder: перезаписывается в Appointment.save()
                    name=(
                        f"{profile.last_name or ''} {profile.first_name or ''}".strip()
                        or request.user.username
                    ),
                    phone=profile.phone,
                    vin=car.vin,
                )
                for f in files:
                    AppointmentPhoto.objects.create(appointment=appointment, image=f)

            # Уведомляем персонал станции и клиента
            notify_station_staff_booked(appointment)
            notify_client_booked(appointment)

        except Exception as e:
            messages.error(request, f"Не удалось создать запись: {e}")
            return redirect(request.path)

        messages.success(request, "Вы успешно записались на ТО")
        return redirect("cabinet_appointments")

    return render(request, "booking/book_station.html", {
        "station": station,
        "cars": cars,
        "today": timezone.now().date(),
    })
