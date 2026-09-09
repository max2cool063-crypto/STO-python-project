from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import Station


def _station_admin():
    return admin.site._registry[Station]


def _can_change_station(request):
    return request.user.has_perm("booking.change_station")


def fill_holidays(request, pk):
    if not _can_change_station(request):
        return HttpResponse("Forbidden", status=403)

    station = get_object_or_404(Station, pk=pk)
    if request.method == "GET":
        from datetime import date as date_type
        return render(
            request,
            "admin/fill_holidays_confirm.html",
            {
                "station": station,
                "year": date_type.today().year,
                "action_url": reverse("admin:station_fill_holidays", args=[station.pk]),
            },
        )
    if request.method != "POST":
        return HttpResponse("Method Not Allowed", status=405)
    return _station_admin().fill_holidays_view(request, pk)


def import_rsa_stream(request):
    if not _can_change_station(request):
        return HttpResponse("Forbidden", status=403)

    if request.method != "POST":
        return HttpResponse("Method Not Allowed", status=405)

    try:
        pages = int(request.POST.get("pages", 3))
    except (TypeError, ValueError):
        return HttpResponse("Некорректное количество страниц.", status=400)

    if not 1 <= pages <= 128:
        return HttpResponse("Количество страниц должно быть от 1 до 128.", status=400)

    # The existing importer reads these parameters from request.GET. Keep its
    # implementation unchanged while exposing the state-changing endpoint as POST.
    request.GET = request.POST.copy()
    return _station_admin().import_rsa_stream(request)
