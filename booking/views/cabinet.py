import io
import mimetypes
import urllib.parse
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from booking.forms import CarForm, ProfileForm
from booking.models import UserProfile, Car, Brand, Appointment, AppointmentPhoto, StationStaff
from booking.notifications import notify_client_cancelled


@login_required
def cabinet_dashboard(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль сохранён")
            return redirect("cabinet")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "booking/cabinet/dashboard.html", {"profile": profile, "form": form})


@login_required
def cabinet_cars(request):
    cars = Car.objects.filter(owner=request.user, is_active=True).select_related("model__brand")
    brands = Brand.objects.all().order_by("name")
    if request.method == "POST":
        model_id = request.POST.get("model")
        plate = request.POST.get("plate", "").strip()
        vin = request.POST.get("vin", "").strip() or None
        if not model_id or not plate:
            messages.error(request, "Выберите модель и укажите госномер")
            return redirect("cabinet_cars")
        if len(plate) > 20:
            messages.error(request, "Госномер слишком длинный")
            return redirect("cabinet_cars")
        try:
            Car.objects.create(owner=request.user, model_id=int(model_id), plate_number=plate, vin=vin)
        except Exception:
            messages.error(request, "Не удалось добавить автомобиль")
            return redirect("cabinet_cars")
        messages.success(request, "Автомобиль добавлен")
        return redirect("cabinet_cars")
    return render(request, "booking/cabinet/cars.html", {"cars": cars, "brands": brands})


@login_required
def cabinet_appointments(request):
    appointments = (Appointment.objects.filter(user=request.user).select_related("station", "car__model__brand").prefetch_related("photos").order_by("-start"))
    return render(request, "booking/cabinet/appointments.html", {"appointments": appointments, "now": timezone.now()})


@login_required
def cabinet_car_edit(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    if request.method == "POST":
        form = CarForm(request.POST, instance=car)
        if form.is_valid():
            form.save()
            messages.success(request, "Изменения сохранены")
            return redirect("cabinet_cars")
    else:
        form = CarForm(instance=car)
    return render(request, "booking/cabinet/car_edit.html", {"form": form, "car": car})


@login_required
@require_POST
def cabinet_car_delete(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    car.is_active = False
    car.save()
    messages.success(request, "Автомобиль удалён")
    return redirect("cabinet_cars")


@login_required
@require_POST
def cabinet_cancel_appointment(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, user=request.user)
    if appt.start <= timezone.now():
        messages.error(request, "Нельзя отменить уже прошедшее ТО")
        return redirect("cabinet_appointments")
    if appt.status != "BOOKED":
        messages.error(request, "Запись уже отменена или завершена")
        return redirect("cabinet_appointments")
    appt.status = "CANCELLED"
    appt.save()
    notify_client_cancelled(appt, cancelled_by_station=False)
    messages.success(request, "Запись отменена")
    return redirect("cabinet_appointments")


@login_required
def appointment_photos_zip(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, user=request.user)
    photos = list(appointment.photos.all())
    if not photos:
        messages.error(request, "У этой записи нет фото")
        return redirect("cabinet_appointments")
    def generate_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for photo in photos:
                filename = photo.image.name.split("/")[-1]
                with photo.image.open("rb") as img_file:
                    zf.writestr(filename, img_file.read())
        buf.seek(0)
        yield buf.read()
    response = StreamingHttpResponse(generate_zip(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="appointment_{pk}_photos.zip"'
    return response


@login_required
def protected_media(request, path):
    """Serve appointment photos only to the owner, station staff, or Django staff."""
    raw_path = urllib.parse.unquote((path or "").lstrip("/"))
    candidates = [raw_path]
    for prefix in ("media/", "/media/"):
        if raw_path.startswith(prefix):
            candidates.append(raw_path[len(prefix):])
    if raw_path.startswith("appointments/"):
        candidates.append(raw_path.removeprefix("appointments/"))
    else:
        candidates.append(f"appointments/{raw_path}")
    candidates = list(dict.fromkeys(candidates))

    photo = AppointmentPhoto.objects.select_related("appointment__station").filter(image__in=candidates).first()
    if not photo:
        raise Http404("AppointmentPhoto not found")

    is_owner = photo.appointment.user_id == request.user.id
    is_django_staff = request.user.is_staff
    is_station_staff = StationStaff.objects.filter(user=request.user, station=photo.appointment.station, is_active=True).exists()
    if not (is_owner or is_django_staff or is_station_staff):
        raise Http404

    try:
        file_handle = photo.image.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404
    content_type = mimetypes.guess_type(photo.image.name)[0] or "application/octet-stream"
    return FileResponse(file_handle, content_type=content_type, as_attachment=False)


@login_required
def change_password(request):
    from django.contrib.auth import update_session_auth_hash
    if request.method == "POST":
        current = request.POST.get("current_password", "")
        new_pwd = request.POST.get("new_password", "").strip()
        confirm = request.POST.get("confirm_password", "").strip()
        if not request.user.check_password(current):
            messages.error(request, "Неверный текущий пароль")
            return redirect("change_password")
        if len(new_pwd) < 8:
            messages.error(request, "Новый пароль должен быть не менее 8 символов")
            return redirect("change_password")
        if new_pwd != confirm:
            messages.error(request, "Пароли не совпадают")
            return redirect("change_password")
        request.user.set_password(new_pwd)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, "Пароль успешно изменён")
        return redirect("cabinet")
    return render(request, "booking/cabinet/change_password.html")
