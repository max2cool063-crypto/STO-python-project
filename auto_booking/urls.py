from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

# Add the per-station timezone field to the existing Station admin without
# changing the existing RSA import/admin implementation.
import booking.admin_timezone  # noqa: F401
# Apply the production safety layer after the existing admin customizations.
import booking.admin_safety  # noqa: F401
from booking.admin_actions import fill_holidays, import_rsa_stream


def healthz(request):
    """Minimal liveness endpoint for the internal Docker health check."""
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")


urlpatterns = [
    # The container probes this over its internal HTTP socket. SecurityMiddleware
    # exempts only this exact path from HTTPS redirect.
    path("healthz/", healthz, name="healthz"),
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

# In DEBUG mode Django may serve non-protected media for local development.
# Appointment photos have their own authenticated /media/appointments/... route
# in booking.urls and do not rely on this helper in production.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
