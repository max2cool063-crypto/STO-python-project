from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponseTooManyRequests


class RateLimit:
    """Small cache-backed rate limiter for public authentication endpoints.

    The limiter intentionally uses Django's cache abstraction so production can
    use a shared backend (for example Redis) without changing application code.
    """

    def __init__(self, prefix: str, limit: int, window: int):
        self.prefix = prefix
        self.limit = limit
        self.window = window

    def _key(self, request, identity: str = "") -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = forwarded.split(",", 1)[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "unknown")
        identity = identity.strip().lower()
        return f"sto:ratelimit:{self.prefix}:{ip}:{identity}"

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

    def retry_response(self):
        response = HttpResponseTooManyRequests(
            "Слишком много попыток. Попробуйте позже.",
            content_type="text/plain; charset=utf-8",
        )
        response["Retry-After"] = str(self.window)
        return response


LOGIN_RATE_LIMIT = RateLimit("login", limit=10, window=15 * 60)
REGISTRATION_RATE_LIMIT = RateLimit("registration", limit=5, window=60 * 60)
