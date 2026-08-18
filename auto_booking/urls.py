from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("booking.urls")),
]

# Media-файлы (в т.ч. фотографии автомобилей) хранятся в MEDIA_ROOT.
# Приложение работает напрямую через Gunicorn без отдельного nginx/media-сервера,
# поэтому media должен быть доступен и при DEBUG=False.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
