from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

from booking.models import Brand, CarModel, Station, Car


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
    """Return available station slots for the authenticated user's car."""
    station = get_object_or_404(Station, id=station_id, is_active=True)
    date = parse_date(request.GET.get("date"))
    car_id = request.GET.get("car")

    if not date:
        return JsonResponse({"slots": []})

    vehicle_type = None
    if car_id:
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
    """Поиск автомобиля по госномеру для операторов станций."""
    plate = request.GET.get("plate", "").strip().upper()
    if not plate:
        return JsonResponse({"error": "plate required"}, status=400)

    from booking.models import StationStaff
    if not StationStaff.objects.filter(user=request.user, is_active=True).exists():
        return JsonResponse({"error": "forbidden"}, status=403)

    try:
        car = Car.objects.select_related("model__brand", "owner__profile").get(
            plate_number=plate, is_active=True
        )
    except Car.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    profile = getattr(car.owner, "profile", None)
    owner_name = ""
    if profile and (profile.last_name or profile.first_name):
        owner_name = f"{profile.last_name} {profile.first_name}".strip()
    else:
        owner_name = car.owner.username

    return JsonResponse({
        "id":           car.id,
        "vehicle_type": car.model.vehicle_type,
        "brand":        car.model.brand.name,
        "model":        car.model.name,
        "vin":          car.vin or "",
        "owner_name":   owner_name,
        "owner_phone":  profile.phone if profile else "",
    })


@require_GET
def brands_with_models_api(request):
    """Все марки с моделями для формы создания авто оператором."""
    from booking.models import StationStaff
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
