from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from booking.forms import CarForm
from booking.models import Car

from booking.station_access import require_station_access


@login_required
@require_station_access()
def station_clients(request, station_id, staff=None):
    """Список чистых клиентских учётных записей станции для владельца и оператора."""
    station = staff.station
    search = request.GET.get("q", "").strip()

    users_qs = (
        User.objects
        .filter(
            appointments__station=station,
            station_roles__isnull=True,
        )
        .distinct()
        .select_related("profile")
    )

    if search:
        users_qs = users_qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(profile__phone__icontains=search) |
            Q(email__icontains=search)
        )

    users_qs = users_qs.annotate(
        visit_count=Count(
            "appointments",
            filter=Q(appointments__station=station, appointments__status="DONE")
        )
    ).order_by("-visit_count")
    users_qs = users_qs.prefetch_related(Prefetch(
        "car_set", queryset=station_cars(station.pk), to_attr="station_cars",
    ))

    return render(request, "booking/station/clients.html", {
        "station": station,
        "staff": staff,
        "clients": users_qs,
        "search": search,
    })


def station_cars(station_id):
    return Car.objects.filter(
        is_active=True, appointments__station_id=station_id,
        owner__station_roles__isnull=True,
    ).select_related("model__brand").distinct()


@login_required
@require_station_access()
def station_car_edit(request, station_id, pk, staff=None):
    car = get_object_or_404(station_cars(station_id), pk=pk)
    wants_json = request.headers.get("Accept") == "application/json"
    form = CarForm(request.POST if request.method == "POST" else None, instance=car)
    if request.method == "POST" and form.is_valid():
        # Save only editable fields; never reassign the owner or model from POST.
        car = form.save(commit=False)
        car.save(update_fields=["plate_number", "vin", "vehicle_type"])
        if wants_json:
            return JsonResponse({"saved": True})
        messages.success(request, "Автомобиль сохранён. Время существующих записей не изменено.")
        return redirect("station_clients", station_id=station_id)
    if wants_json:
        if request.method == "POST":
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        return JsonResponse({"plate_number": car.plate_number, "vin": car.vin or "", "vehicle_type": car.vehicle_type})
    return render(request, "booking/station/car_edit.html", {
        "station": staff.station, "staff": staff, "car": car, "form": form,
    })
