from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from booking.input_validation import safe_parse_date as parse_date
from django.views.decorators.http import require_GET

from booking.models import Brand, CarModel, Station, Car, StationStaff
from booking.station_access import get_staff_record


def brands_api(request):
    brands = Brand.objects.all().order_by("name")
    return JsonResponse(
        [{"id": b.id, "name": b.name} for b in brands],
        safe=False,
    )


def models_api(request, brand_id):
    models = CarModel.objects.filter(brand_id=brand_id).order_by("name")
    return JsonResponse(
        [{"id": m.id, "name": m.name, "vehicle_type": m.vehicle_type} for m in models],
        safe=False,
    )


@require_GET
@login_required
def station_slots_api(request, station_id):
    """Return available station slots for the authenticated user's or station's car."""
    station = get_object_or_404(Station, id=station_id, is_active=True)
    date = parse_date(request.GET.get("date"))
    car_id = request.GET.get("car")
    requested_vehicle_type = (request.GET.get("vehicle_type") or "").strip().upper()

    if not date:
        return JsonResponse({"slots": []})

    vehicle_type = None
    staff = get_staff_record(request.user, station_id)
    has_station_account = StationStaff.objects.filter(user=request.user).exists()
    if has_station_account and not staff:
        # A station identity must never silently fall back to client behavior
        # when it requests slots for an unrelated station.
        return JsonResponse({"error": "forbidden"}, status=403)

    if car_id:
        if staff:
            # A known client car may have many historical appointments at this
            # station. DISTINCT prevents the reverse join from returning the same
            # car once per visit. Owners with any station role are excluded from
            # client booking mode permanently.
            car = get_object_or_404(
                Car.objects.select_related("model").filter(
                    is_active=True,
                    appointments__station_id=station_id,
                    owner__station_roles__isnull=True,
                ).distinct(),
                id=car_id,
            )
        else:
            # Regular clients may request slots only for their own cars.
            car = get_object_or_404(
                Car.objects.select_related("model"),
                id=car_id,
                owner=request.user,
                is_active=True,
            )
        vehicle_type = car.model.vehicle_type
    elif requested_vehicle_type in {"CAR", "TRUCK"} and staff:
        # During station-side creation of a brand-new car there is no car_id yet.
        # The vehicle type is still needed so the preview and available slots use
        # the same duration rule as Appointment.save().
        vehicle_type = requested_vehicle_type

    slots = station.get_available_slots(date, vehicle_type=vehicle_type)
    return JsonResponse({"slots": slots})


@require_GET
@login_required
def car_api(request, car_id):
    if StationStaff.objects.filter(user=request.user).exists():
        return JsonResponse({"error": "forbidden"}, status=403)

    car = get_object_or_404(Car, id=car_id, owner=request.user, is_active=True)
    return JsonResponse({
        "id": car.id,
        "vehicle_type": car.model.vehicle_type,
    })


@require_GET
@login_required
def car_by_plate_api(request):
    """Search active cars by plate among pure clients known to the current station."""
    plate = request.GET.get("plate", "").strip().upper()
    station_id = request.GET.get("station_id", "").strip()

    if not plate or not station_id:
        return JsonResponse({"error": "plate and station_id required"}, status=400)

    staff = get_staff_record(request.user, station_id)
    if not staff:
        return JsonResponse({"error": "forbidden"}, status=403)

    # A station employee must not be able to discover clients of another
    # station. A plate may legitimately occur on several active client cars,
    # so return every matching pure-client record for THIS station.
    cars = list(
        Car.objects
        .select_related("model__brand", "owner__profile")
        .filter(
            plate_number=plate,
            is_active=True,
            appointments__station_id=station_id,
            owner__station_roles__isnull=True,
        )
        .distinct()
        .order_by("owner_id", "id")
    )

    matches = []
    for car in cars:
        profile = getattr(car.owner, "profile", None)
        owner_name = f"{car.owner.last_name} {car.owner.first_name}".strip() or car.owner.username
        matches.append({
            "id": car.id,
            "plate": car.plate_number,
            "vehicle_type": car.model.vehicle_type,
            "brand": car.model.brand.name,
            "model": car.model.name,
            "vin": car.vin or "",
            "owner_name": owner_name,
            "owner_phone": profile.phone if profile else "",
            "owner_email": car.owner.email or "",
        })

    if not matches:
        return JsonResponse({"error": "not found"}, status=404)

    payload = {
        "count": len(matches),
        "ambiguous": len(matches) > 1,
        "matches": matches,
    }
    # Keep compatibility with the station booking form for the overwhelmingly
    # common unambiguous lookup while retaining the richer matches payload.
    if len(matches) == 1:
        payload.update(matches[0])
    return JsonResponse(payload)


@require_GET
def brands_with_models_api(request):
    """Все марки с моделями для формы создания авто оператором."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "auth required"}, status=401)
    if not StationStaff.objects.filter(user=request.user, is_active=True).exists():
        return JsonResponse({"error": "forbidden"}, status=403)

    brands = Brand.objects.prefetch_related(
        Prefetch(
            "models",
            queryset=CarModel.objects.order_by("name"),
            to_attr="ordered_models",
        )
    ).order_by("name")

    result = []
    for brand in brands:
        result.append({
            "id": brand.id,
            "name": brand.name,
            "models": [
                {"id": model.id, "name": model.name, "vehicle_type": model.vehicle_type}
                for model in brand.ordered_models
            ],
        })
    return JsonResponse(result, safe=False)
