from __future__ import annotations

import ipaddress

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


def _client_ip(request) -> str:
    """Return the client IP, trusting X-Forwarded-For only from configured proxies.

    Walk the forwarding chain from the application backwards. This prevents a
    client-supplied leftmost X-Forwarded-For value from bypassing rate limits
    when a trusted reverse proxy appends the real client address.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "unknown").strip()

    if not getattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", False):
        return remote_addr or "unknown"

    trusted_proxies = getattr(settings, "RATE_LIMIT_TRUSTED_PROXIES", ())
    try:
        remote_ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return remote_addr or "unknown"

    def is_trusted(address):
        return any(address in network for network in trusted_proxies)

    # Never trust forwarding headers from a directly connected, untrusted hop.
    if not is_trusted(remote_ip):
        return str(remote_ip)

    forwarded_ips = []
    for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(","):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            forwarded_ips.append(ipaddress.ip_address(candidate))
        except ValueError:
            continue

    if not forwarded_ips:
        return str(remote_ip)

    # X-Forwarded-For is ordered client -> proxy1 -> proxy2. Starting from the
    # right drops only configured trusted proxy hops. The first untrusted hop is
    # the effective client address, even if a spoofed value exists farther left.
    for candidate in reversed(forwarded_ips):
        if not is_trusted(candidate):
            return str(candidate)

    # An all-trusted chain is unusual (for example an internal client), but the
    # farthest hop is the best available client address in that case.
    return str(forwarded_ips[0])


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
        # add() is atomic for Redis and LocMemCache. If the key expires between
        # add() and incr(), LocMemCache raises ValueError while Redis can recreate
        # it without a TTL. Handle both cases and always refresh the expiry after
        # incrementing so no rate-limit key can accidentally become permanent.
        if cache.add(key, 1, timeout=self.window):
            return 1
        try:
            current = int(cache.incr(key))
        except ValueError:
            if cache.add(key, 1, timeout=self.window):
                return 1
            current = int(cache.incr(key))
        cache.touch(key, self.window)
        return current

    def retry_response(self):
        response = HttpResponse(
            "Слишком много попыток. Попробуйте позже.",
            status=429,
            content_type="text/plain; charset=utf-8",
        )
        response["Retry-After"] = str(self.window)
        return response


# Limit repeated guessing of one identity, and also cap aggregate failed login
# attempts from one client address so rotating through many usernames cannot
# bypass the per-identity limiter. The IP-wide ceiling is deliberately higher to
# avoid penalizing normal users behind shared NAT/proxy addresses.
LOGIN_RATE_LIMIT = RateLimit("login", limit=10, window=15 * 60)
LOGIN_IP_RATE_LIMIT = RateLimit("login-ip", limit=50, window=15 * 60)
REGISTRATION_RATE_LIMIT = RateLimit("registration", limit=5, window=60 * 60)
