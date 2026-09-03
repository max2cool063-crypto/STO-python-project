from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.utils import timezone
from django.utils.timezone import is_aware
from django.db import transaction

from booking.models import Station, Appointment, Car, AppointmentPhoto, UserProfile
from booking.forms import PhotosUploadForm
from booking.notifications import notify_station_staff_booked, notify_client_booked, create_station_staff_notifications


@login_required
def book_station(request, pk):
    station = get_object_or_404(Station, pk=pk, is_active=True)
    cars = Car.objects.filter(owner=request.user, is_active=True).select_related("model__brand")
    other_stations = Station.objects.filter(is_active=True).exclude(pk=station.pk).order_by("name")

    if request.method == "POST":
        start = parse_datetime(request.POST.get("start"))
        if start and not is_aware(start):
            start = station.make_local_datetime(start.date(), start.time())
        car_id = request.POST.get("car")

        if not start:
            messages.error(request, "Некорректная дата или время")
            return redirect(request.path)
        if start < timezone.now():
            messages.error(request, "Нельзя записаться в прошлое")
            return redirect(request.path)

        car = get_object_or_404(Car, id=car_id, owner=request.user, is_active=True)
        files = request.FILES.getlist("photos")
        if files:
            photo_errors = PhotosUploadForm.validate_photos(files)
            if photo_errors:
                for err in photo_errors:
                    messages.error(request, err)
                return redirect(request.path)

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        try:
            with transaction.atomic():
                station = Station.objects.select_for_update().get(pk=station.pk)
                appointment = Appointment.objects.create(
                    station=station,
                    user=request.user,
                    car=car,
                    start=start,
                    end=start,
                    name=f"{request.user.last_name or ''} {request.user.first_name or ''}".strip() or request.user.username,
                    phone=profile.phone,
                    vin=car.vin,
                )
                for f in files:
                    AppointmentPhoto.objects.create(appointment=appointment, image=f)

                # Внутреннее уведомление создаём только после успешного commit.
                transaction.on_commit(
                    lambda: create_station_staff_notifications(appointment),
                    robust=True,
                )

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
        "today": station.local_date(),
        "other_stations": other_stations,
    })
