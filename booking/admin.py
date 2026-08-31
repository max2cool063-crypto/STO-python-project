from django.contrib import admin
from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.shortcuts import redirect, render
from django.contrib import messages
from django.urls import path
from django.http import StreamingHttpResponse
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from datetime import time, date as date_type
import json
import time as time_mod
from .models import (
    Brand, CarModel, Car, UserProfile,
    Station, StationWeeklySchedule, StationSchedule,
    Appointment, AppointmentPhoto,
    StationStaff,
)
from .forms import WeeklyScheduleInlineForm, ScheduleInlineForm

admin.site.site_header = "СТО — Панель управления"
admin.site.site_title = "СТО"
admin.site.index_title = "Управление системой"


class StationWeeklyScheduleInline(admin.TabularInline):
    model = StationWeeklySchedule
    form = WeeklyScheduleInlineForm
    extra = 1
    min_num = 1
    verbose_name = "день"
    verbose_name_plural = "График работы по дням недели"


class StationScheduleInline(admin.TabularInline):
    model = StationSchedule
    form = ScheduleInlineForm
    extra = 0
    verbose_name = "исключение"
    verbose_name_plural = "Исключения на конкретные даты"


class AppointmentPhotoInline(admin.TabularInline):
    model = AppointmentPhoto
    extra = 0
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" height="80" style="border-radius:8px" />')
        return "—"
    image_preview.short_description = "Фото"


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("rsa_id", "name", "address", "phone", "is_active", "fill_holidays_button")
    list_editable = ("is_active",)
    search_fields = ("rsa_id", "name", "address")
    list_filter = ("is_active",)
    fieldsets = (
        ("Основная информация", {"fields": ("name", "rsa_id", "address", "phone", "email", "is_active")}),
        ("Координаты и карта", {"fields": ("latitude", "longitude", "map_preview")}),
        ("Настройки записи", {"fields": ("slot_duration",)}),
        ("Праздники", {"fields": ("fill_holidays_link",)}),
    )
    readonly_fields = ("map_preview", "fill_holidays_link")
    inlines = (StationWeeklyScheduleInline, StationScheduleInline)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/fill-holidays/', self.admin_site.admin_view(self.fill_holidays_view), name='station_fill_holidays'),
            path('import-rsa/', self.admin_site.admin_view(self.import_rsa_view), name='station_import_rsa'),
            path('import-rsa-stream/', self.admin_site.admin_view(self.import_rsa_stream), name='station_import_rsa_stream'),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_rsa_url'] = '/admin/booking/station/import-rsa/'
        return super().changelist_view(request, extra_context=extra_context)

    def import_rsa_view(self, request):
        return render(request, "admin/import_rsa.html", {"query": ""})

    def import_rsa_stream(self, request):
        from bs4 import BeautifulSoup
        import requests as req
        address = request.GET.get("address", "").strip()
        max_pages = min(int(request.GET.get("pages", 3)), 20)
        BASE = "https://oto-register.autoins.ru"
        HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        def event_stream():
            created = skipped = errors = 0
            for page in range(1, max_pages + 1):
                yield f"data: {json.dumps({'type': 'progress', 'page': page, 'total_pages': max_pages})}\n\n"
                try:
                    r = req.get(f"{BASE}/search/pto/{page}", params={"otoId": "", "shortName": "", "address": address, "areasOfAccreditation": ""}, headers=HEADERS, timeout=(5, 10))
                    from bs4 import BeautifulSoup as BS
                    soup = BS(r.text, "html.parser")
                    rows = soup.select("tr.table_row")
                    if not rows:
                        yield f"data: {json.dumps({'type': 'log', 'message': f'📄 Страница {page}: записей нет, остановка'})}\n\n"
                        break
                    yield f"data: {json.dumps({'type': 'log', 'message': f'📄 Страница {page}: найдено {len(rows)} строк'})}\n\n"
                    for i, row in enumerate(rows, 1):
                        status_div = row.select_one(".status")
                        if status_div and "ok" not in status_div.get("class", []):
                            continue
                        tds = row.select("td")
                        if len(tds) < 2:
                            continue
                        rid = tds[1].text.strip()
                        if not rid:
                            continue
                        try:
                            request_id = row.get("data-request-id")
                            if not request_id:
                                errors += 1
                                continue
                            dr = req.get(f"{BASE}/modals/pto/{request_id}", headers=HEADERS, timeout=(5, 8))
                            ds = BS(dr.text, "html.parser")
                            detail = {}
                            for div in ds.select(".leftPanel div"):
                                h4 = div.select_one("h4")
                                p = div.select_one("p") or div.select_one("a")
                                if h4 and p:
                                    k = h4.text.strip(); v = p.text.strip()
                                    if "Полное наименование" in k: detail["name"] = v
                                    elif k == "Адрес": detail["address"] = v
                                    elif "Телефон" in k: detail["phone"] = v
                                    elif "mail" in k.lower(): detail["email"] = v
                            if "name" not in detail or "address" not in detail:
                                errors += 1
                                continue
                            tds_modal = ds.select(".popupTable td")
                            if len(tds_modal) >= 2:
                                try:
                                    detail["lat"] = float(tds_modal[0].text.strip().replace(",", ".")); detail["lng"] = float(tds_modal[1].text.strip().replace(",", "."))
                                except ValueError:
                                    detail["lat"] = detail["lng"] = None
                            station_name = " ".join(detail["name"].split())
                            station_address = " ".join(detail["address"].split())
                            station = Station.objects.filter(rsa_id=rid).first()
                            if station:
                                Station.objects.filter(pk=station.pk).update(name=station_name, address=station_address, latitude=detail.get("lat"), longitude=detail.get("lng"), phone=detail.get("phone", ""), email=detail.get("email", ""))
                                was_created = False
                            else:
                                Station.objects.create(name=station_name, address=station_address, rsa_id=rid, latitude=detail.get("lat"), longitude=detail.get("lng"), phone=detail.get("phone", ""), email=detail.get("email", ""))
                                was_created = True
                            created += int(was_created); skipped += int(not was_created)
                            time_mod.sleep(0.3)
                        except Exception:
                            errors += 1
                except Exception:
                    break
            yield f"data: {json.dumps({'type': 'done', 'message': f'Готово! Создано: {created}, Обновлено: {skipped}, Ошибок: {errors}'})}\n\n"
        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"; response["X-Accel-Buffering"] = "no"
        return response

    def fill_holidays_view(self, request, pk):
        try:
            import holidays as holidays_lib
        except ImportError:
            messages.error(request, "Библиотека holidays не установлена.")
            return redirect(f"/admin/booking/station/{pk}/change/")
        station = Station.objects.get(pk=pk)
        year = date_type.today().year
        ru_holidays = holidays_lib.Russia(years=year)
        created = skipped = 0
        for hdate, hname in sorted(ru_holidays.items()):
            _, was_created = StationSchedule.objects.get_or_create(station=station, date=hdate, defaults={"work_start": time(0, 0), "work_end": time(0, 0)})
            created += int(was_created); skipped += int(not was_created)
        if created: messages.success(request, f"✅ Добавлено {created} праздничных дней на {year} год")
        if skipped: messages.info(request, f"ℹ️ Пропущено {skipped} дней (уже существуют)")
        return redirect(f"/admin/booking/station/{pk}/change/")

    def fill_holidays_button(self, obj):
        if obj.pk:
            return format_html('<a class="button" href="/admin/booking/station/{}/fill-holidays/" style="background:#417690;color:white;padding:4px 10px;border-radius:4px;text-decoration:none;font-size:12px">🗓 Праздники {}</a>', obj.pk, date_type.today().year)
        return "—"
    fill_holidays_button.short_description = "Праздники"

    def fill_holidays_link(self, obj):
        if obj.pk:
            return format_html('<a class="button" href="/admin/booking/station/{}/fill-holidays/" style="background:#417690;color:white;padding:8px 16px;border-radius:4px;text-decoration:none"> Заполнить праздники {} года</a><p style="color:#666;margin-top:8px;font-size:12px">Добавит все российские праздники как выходные в таблицу исключений</p>', obj.pk, date_type.today().year)
        return "Сохраните станцию сначала"
    fill_holidays_link.short_description = "Автозаполнение праздников"

    def map_preview(self, obj=None):
        return mark_safe('<div id="map" style="width:100%; height:400px;"></div>')
    map_preview.short_description = "Карта станции"

    class Media:
        js = (f"https://api-maps.yandex.ru/2.1/?lang=ru_RU&apikey={settings.YANDEX_MAPS_API_KEY}", "booking/js/admin_station_map.js")
        css = {"all": ("booking/css/admin.css",)}


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("station", "start", "end", "client_name", "client_phone", "car", "get_type", "user", "status")
    list_editable = ("status",)
    list_filter = ("station", "car__model__vehicle_type", "status")
    search_fields = ("name", "phone", "vin")
    ordering = ("start",)
    inlines = [AppointmentPhotoInline]
    date_hierarchy = "start"

    @admin.display(description="Клиент")
    def client_name(self, obj):
        full_name = " ".join(filter(None, [obj.user.last_name, obj.user.first_name]))
        return full_name or obj.name

    @admin.display(description="Телефон")
    def client_phone(self, obj):
        profile = getattr(obj.user, "profile", None)
        return profile.phone if profile and profile.phone else "—"

    @admin.display(description="Тип ТС")
    def get_type(self, obj):
        return obj.car.model.get_vehicle_type_display()


class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "last_name", "first_name", "email", "is_staff", "is_active")
    list_display_links = ("username",)
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("username", "last_name", "first_name", "email", "phone")
    search_fields = ("user__username", "user__email", "user__last_name", "user__first_name", "phone")

    @admin.display(description="Логин", ordering="user__username")
    def username(self, obj):
        return obj.user.username

    @admin.display(description="Фамилия", ordering="user__last_name")
    def last_name(self, obj):
        return obj.user.last_name

    @admin.display(description="Имя", ordering="user__first_name")
    def first_name(self, obj):
        return obj.user.first_name

    @admin.display(description="Почта", ordering="user__email")
    def email(self, obj):
        return obj.user.email

    @admin.display(description="Телефон")
    def phone(self, obj):
        return obj.phone


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ("owner", "model", "plate_number", "get_vehicle_type", "is_active")
    list_editable = ("is_active",)
    search_fields = ("model__name", "plate_number", "vin")
    list_filter = ("model__brand", "model__vehicle_type", "is_active")

    def get_vehicle_type(self, obj):
        return obj.model.get_vehicle_type_display()
    get_vehicle_type.short_description = "Тип ТС"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "vehicle_type")
    list_filter = ("brand", "vehicle_type")
    search_fields = ("name",)
    ordering = ("brand", "name")


@admin.register(StationStaff)
class StationStaffAdmin(admin.ModelAdmin):
    list_display = ("station", "user", "role", "is_active", "created_by", "created_at")
    list_filter = ("role", "is_active", "station")
    list_editable = ("role", "is_active")
    search_fields = ("user__email", "user__username", "station__name")
    autocomplete_fields = ("user", "station")
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
