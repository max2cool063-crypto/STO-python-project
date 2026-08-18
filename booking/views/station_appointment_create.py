import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware

from booking.models import Car, CarModel, Station, Appointment
from booking.notifications import notify_station_staff_booked, notify_client_booked
from booking.station_access import require_station_access
from booking.views.auth import send_password_setup_email

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_or_create_client(email):
    """Find a client deterministically; email is not unique in Django's User model."""
    user = User.objects.filter(username=email).first()
    if user:
        return user, False

    user = User.objects.filter(email__iexact=email).order_by("id").first()
    if user:
        return user, False

    user = User.objects.create_user(username=email, email=email)
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

        user_created = False
        client_user = None
        try:
            with transaction.atomic():
                if not car_id:
                    plate = request.POST.get("plate", "").strip().upper()
                    model_id = request.POST.get("new_model_id", "").strip()
                    email = request.POST.get("new_user_email", "").strip().lower()

                    if not plate or not model_id or not email:
                        raise ValidationError(
                            "Для нового автомобиля укажите госномер, модель и email клиента"
                        )

                    try:
                        model = CarModel.objects.get(pk=int(model_id))
                    except (ValueError, CarModel.DoesNotExist):
                        raise ValidationError("Выбрана некорректная модель автомобиля")

                    client_user, user_created = _get_or_create_client(email)
                    car = Car.objects.create(
                        owner=client_user,
                        model=model,
                        plate_number=plate,
                    )
                else:
                    # Доступ к этой операции уже ограничен активным сотрудником станции.
                    # Автомобиль может ещё не иметь истории посещений этой станции.
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
