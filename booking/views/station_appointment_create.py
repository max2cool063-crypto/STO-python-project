import logging
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware

from booking.forms import PhotosUploadForm
from booking.models import Appointment, AppointmentPhoto, Car, CarModel, Station
from booking.notifications import notify_client_booked, notify_station_staff_booked
from booking.station_access import require_station_access
from booking.views.auth import send_password_setup_email

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_or_create_client(email):
    """Find a client by email. Returns (user, created)."""
    email = (email or "").strip().lower()
    if email:
        user = User.objects.filter(username=email).first()
        if user:
            return user, False
        user = User.objects.filter(email__iexact=email).order_by("id").first()
        if user:
            return user, False

    username = f"client_{uuid.uuid4().hex[:12]}"
    user = User.objects.create_user(username=username, email=email)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user, True


@login_required
@require_station_access()
def station_appointment_create(request, station_id, staff=None):
    """Оператор/владелец создаёт запись вручную."""
    station = staff.station

    if request.method == "POST":
        car_id = request.POST.get("car_id", "").strip()
        start_s = request.POST.get("start", "")
        client_name = request.POST.get("client_name", "").strip()
        client_phone = request.POST.get("client_phone", "").strip()
        email = request.POST.get("new_user_email", "").strip().lower()
        files = request.FILES.getlist("photos")

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

        photo_errors = PhotosUploadForm.validate_photos(files)
        if photo_errors:
            for error in photo_errors:
                messages.error(request, error)
            return redirect(request.path)

        user_created = False
        client_user = None
        try:
            with transaction.atomic():
                if not car_id:
                    plate = request.POST.get("plate", "").strip().upper()
                    model_id = request.POST.get("new_model_id", "").strip()
                    vin = request.POST.get("vin", "").strip().upper() or None

                    if not plate or not model_id:
                        raise ValidationError(
                            "Для нового автомобиля укажите госномер и модель автомобиля"
                        )
                    if vin and len(vin) > 32:
                        raise ValidationError("VIN не должен превышать 32 символа")

                    try:
                        model = CarModel.objects.get(pk=int(model_id))
                    except (ValueError, CarModel.DoesNotExist):
                        raise ValidationError("Выбрана некорректная модель автомобиля")

                    client_user, user_created = _get_or_create_client(email)
                    car = Car.objects.create(
                        owner=client_user,
                        model=model,
                        plate_number=plate,
                        vin=vin,
                    )
                else:
                    car = get_object_or_404(
                        Car.objects.select_related("model", "owner"),
                        id=car_id,
                        is_active=True,
                    )

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

                for uploaded in files:
                    AppointmentPhoto.objects.create(
                        appointment=appointment,
                        image=uploaded,
                    )

        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect(request.path)
        except Exception:
            logger.exception(
                "Failed to create station appointment: station=%s user=%s",
                station.pk,
                request.user.pk,
            )
            messages.error(request, "Не удалось создать запись. Проверьте данные и попробуйте ещё раз.")
            return redirect(request.path)

        if user_created and client_user and client_user.email:
            try:
                send_password_setup_email(request, client_user)
            except Exception:
                logger.exception("Failed to send password setup email to %s", client_user.email)

        notify_station_staff_booked(appointment)
        notify_client_booked(appointment)
        messages.success(request, "Запись создана")
        return redirect("station_appointments", station_id=station_id)

    return render(request, "booking/station/appointment_create.html", {
        "station": station,
        "staff": staff,
        "today": timezone.now().date(),
    })
