from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

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

    if not date:
        return JsonResponse({"slots": []})

    vehicle_type = None
    if car_id:
        staff = get_staff_record(request.user, station_id)
        if staff:
            # Station operators work with client cars belonging to this station.
            # Do not expose cars known only to another station.
            car = get_object_or_404(
                Car.objects.select_related("model"),
                id=car_id,
                is_active=True,
                appointments__station_id=station_id,
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

    slots = station.get_available_slots(date, vehicle_type=vehicle_type)
    return JsonResponse({"slots": slots})


@require_GET
@login_required
def car_api(request, car_id):
    car = get_object_or_404(Car, id=car_id, owner=request.user, is_active=True)
    return JsonResponse({
        "id": car.id,
        "vehicle_type": car.model.vehicle_type,
    })


@require_GET
@login_required
def car_by_plate_api(request):
    """Search active cars by plate among clients known to the current station."""
    plate = request.GET.get("plate", "").strip().upper()
    station_id = request.GET.get("station_id", "").strip()

    if not plate or not station_id:
        return JsonResponse({"error": "plate and station_id required"}, status=400)

    staff = get_staff_record(request.user, station_id)
    if not staff:
        return JsonResponse({"error": "forbidden"}, status=403)

    # A station employee must not be able to discover clients of another
    # station. At the same time, a plate may legitimately occur on several
    # active cars (for example after a change of owner). Therefore we search
    # all active cars known to THIS station and return every matching record.
    cars = list(
        Car.objects
        .select_related("model__brand", "owner__profile")
        .filter(
            plate_number=plate,
            is_active=True,
            appointments__station_id=station_id,
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

    # Keep one stable response shape for both one and many results.
    return JsonResponse({
        "count": len(matches),
        "ambiguous": len(matches) > 1,
        "matches": matches,
    })


@require_GET
def brands_with_models_api(request):
    """Все марки с моделями для формы создания авто оператором."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "auth required"}, status=401)
    if not StationStaff.objects.filter(user=request.user, is_active=True).exists():
        return JsonResponse({"error": "forbidden"}, status=403)

    result = []
    for brand in Brand.objects.prefetch_related("models").order_by("name"):
        result.append({
            "id": brand.id,
            "name": brand.name,
            "models": [
                {"id": m.id, "name": m.name, "vehicle_type": m.vehicle_type}
                for m in brand.models.order_by("name")
            ]
        })
    return JsonResponse(result, safe=False)
