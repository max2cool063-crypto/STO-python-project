from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from booking.models import Station


def station_list(request):
    stations = Station.objects.filter(is_active=True).prefetch_related("weekly_schedules", "schedules")
    return render(request, "booking/station_list.html", {"stations": stations})


def stations_json(request):
    stations = Station.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False
    )
    return JsonResponse(
        [
            {
                "id": s.id,
                "name": s.name,
                "lat": s.latitude,
                "lng": s.longitude,
                "address": s.address,
            }
            for s in stations
        ],
        safe=False,
    )
