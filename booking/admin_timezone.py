from django.contrib import admin

from booking.models import Station
from booking.admin import StationAdmin as BaseStationAdmin


# StationAdmin has explicit fieldsets, so the per-station timezone needs to be
# inserted into the existing admin form without duplicating the large import UI.
class StationTimezoneAdmin(BaseStationAdmin):
    fieldsets = tuple(
        (
            title,
            {**options, "fields": tuple(options.get("fields", ())) + (("timezone",) if title == "Координаты и карта" else ())},
        )
        for title, options in BaseStationAdmin.fieldsets
    )


admin.site.unregister(Station)
admin.site.register(Station, StationTimezoneAdmin)
