from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Add the per-station timezone field to the existing Station admin without
# changing the existing RSA import/admin implementation.
import booking.admin_timezone  # noqa: F401
from booking.admin_actions import fill_holidays, import_rsa_stream

urlpatterns = [
    # These exact routes must precede admin.site.urls so the state-changing
    # station actions are exposed through POST-only wrappers with CSRF protection.
    path(
        "admin/booking/station/<int:pk>/fill-holidays/",
        admin.site.admin_view(fill_holidays),
        name="station_fill_holidays",
    ),
    path(
        "admin/booking/station/import-rsa-stream/",
        admin.site.admin_view(import_rsa_stream),
        name="station_import_rsa_stream",
    ),
    path("admin/", admin.site.urls),
    path("", include("booking.urls")),
]

# Media-файлы (в т.ч. фотографии автомобилей) хранятся в MEDIA_ROOT.
# Приложение работает напрямую через Gunicorn без отдельного nginx/media-сервера,
# поэтому media должен быть доступен и при DEBUG=False.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
