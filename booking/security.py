from __future__ import annotations

import ipaddress

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


def _client_ip(request) -> str:
    """Return the client IP, trusting X-Forwarded-For only from configured proxies."""
    remote_addr = request.META.get("REMOTE_ADDR", "unknown").strip()

    if not getattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", False):
        return remote_addr or "unknown"

    trusted_proxies = getattr(settings, "RATE_LIMIT_TRUSTED_PROXIES", ())
    try:
        remote_ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return remote_addr or "unknown"

    if not any(remote_ip in network for network in trusted_proxies):
        return remote_addr or "unknown"

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    for candidate in (part.strip() for part in forwarded.split(",")):
        if candidate:
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                continue

    return remote_addr or "unknown"


class RateLimit:
    """Cache-backed rate limiter for public authentication endpoints."""

    def __init__(self, prefix: str, limit: int, window: int):
        self.prefix = prefix
        self.limit = limit
        self.window = window

    def _key(self, request, identity: str = "") -> str:
        identity = identity.strip().lower()
        return f"sto:ratelimit:{self.prefix}:{_client_ip(request)}:{identity}"

    def allowed(self, request, identity: str = "") -> bool:
        key = self._key(request, identity)
        current = cache.get(key)
        return current is None or int(current) < self.limit

    def hit(self, request, identity: str = "") -> int:
        key = self._key(request, identity)
        try:
            current = cache.incr(key)
        except ValueError:
            cache.add(key, 1, timeout=self.window)
            current = 1
        return int(current)

    def reset(self, request, identity: str = "") -> None:
        cache.delete(self._key(request, identity))

    def retry_response(self):
        response = HttpResponse(
            "Слишком много попыток. Попробуйте позже.",
            status=429,
            content_type="text/plain; charset=utf-8",
        )
        response["Retry-After"] = str(self.window)
        return response


LOGIN_RATE_LIMIT = RateLimit("login", limit=10, window=15 * 60)
REGISTRATION_RATE_LIMIT = RateLimit("registration", limit=5, window=60 * 60)
