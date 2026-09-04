from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Add the per-station timezone field to the existing Station admin without
# changing the existing RSA import/admin implementation.
import booking.admin_timezone  # noqa: F401

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("booking.urls")),
]

# Media-файлы (в т.ч. фотографии автомобилей) хранятся в MEDIA_ROOT.
# Приложение работает напрямую через Gunicorn без отдельного nginx/media-сервера,
# поэтому media должен быть доступен и при DEBUG=False.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
