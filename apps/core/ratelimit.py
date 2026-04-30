"""Lightweight per-user / per-IP rate limiting using Django's cache.

Avoids the django-ratelimit dependency — the project's cache backend
(LocMem in dev, Redis in prod) already gives us atomic ``incr`` semantics.

Usage:

    from apps.core.ratelimit import rate_limit

    @rate_limit(key="chat", rate="10/h")
    def analytics_chat(request):
        ...

    # Or per-IP for anonymous endpoints:
    @rate_limit(key="share_create", rate="5/m", scope="ip")

Returns HTTP 429 with a plain JSON body when the limit is exceeded.
Uses a fixed window (not sliding) — simple, adequate for abuse prevention.
"""
from __future__ import annotations

import functools
import hashlib
import time
from typing import Callable

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import gettext as _


_PERIODS = {
    "s":   1,
    "m":   60,
    "h":   60 * 60,
    "d":   60 * 60 * 24,
}


def _parse_rate(rate: str) -> tuple[int, int]:
    """Parse '10/m' → (10, 60)."""
    count_str, period_str = rate.split("/")
    count = int(count_str)
    if period_str not in _PERIODS:
        raise ValueError(f"Unknown rate period: {period_str!r}. Use s|m|h|d.")
    return count, _PERIODS[period_str]


def _client_ip(request: HttpRequest) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _identity(request: HttpRequest, scope: str) -> str:
    if scope == "user" and request.user.is_authenticated:
        return f"u:{request.user.id}"
    ip = _client_ip(request)
    return "ip:" + hashlib.sha1(ip.encode()).hexdigest()[:12]


def rate_limit(
    *,
    key: str,
    rate: str,
    scope: str = "user",
    methods: tuple[str, ...] = ("POST",),
) -> Callable:
    """Decorator factory. See module docstring for usage."""
    count, period = _parse_rate(rate)

    def decorator(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if request.method not in methods:
                return view(request, *args, **kwargs)

            ident = _identity(request, scope)
            window = int(time.time()) // period
            cache_key = f"rl:{key}:{ident}:{window}"

            try:
                current = cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, timeout=period)
                current = 1

            if current > count:
                retry_after = period - (int(time.time()) % period)
                resp = JsonResponse(
                    {
                        "error": _("Juda ko'p so'rov. Biroz kuting va qayta urinib ko'ring."),
                        "retry_after_seconds": retry_after,
                    },
                    status=429,
                )
                resp["Retry-After"] = str(retry_after)
                resp["X-RateLimit-Limit"] = str(count)
                resp["X-RateLimit-Remaining"] = "0"
                return resp

            return view(request, *args, **kwargs)

        return wrapper

    return decorator