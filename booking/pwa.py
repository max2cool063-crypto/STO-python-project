"""Public PWA resources: never include account or booking data."""
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.http import require_safe


@require_safe
def manifest(request):
    response = JsonResponse({
        "id": "/", "name": "Технический Осмотр — онлайн запись",
        "short_name": "ТО Онлайн", "lang": "ru", "start_url": "/",
        "scope": "/", "display": "standalone", "background_color": "#f5f7fb",
        "theme_color": "#155eef",
        "description": "Запись на техосмотр и управление записями станции.",
        "icons": [
            {"src": static(f"booking/pwa/icon-{size}.png"), "sizes": f"{size}x{size}",
             "type": "image/png", "purpose": "any maskable"}
            for size in (192, 512)
        ],
    }, content_type="application/manifest+json")
    response["Cache-Control"] = "no-cache"
    return response


@require_safe
def service_worker(request):
    response = render(request, "pwa/service-worker.js", content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


@require_safe
def offline(request):
    response = render(request, "pwa/offline.html")
    response["Cache-Control"] = "no-cache"
    return response
