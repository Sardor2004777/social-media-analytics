"""Tests for :mod:`apps.core.ratelimit`.

Uses a direct view function instead of the real chat endpoint so these stay
fast and don't depend on the Anthropic SDK being installed.
"""
from __future__ import annotations

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.ratelimit import rate_limit


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@rate_limit(key="t_view", rate="3/h", scope="ip", methods=("POST",))
def sample_view(request):
    return HttpResponse("ok")


def test_allows_requests_within_limit():
    factory = RequestFactory()
    for _ in range(3):
        resp = sample_view(factory.post("/"))
        assert resp.status_code == 200


def test_blocks_after_limit_exceeded():
    factory = RequestFactory()
    for _ in range(3):
        sample_view(factory.post("/"))
    resp = sample_view(factory.post("/"))
    assert resp.status_code == 429
    assert "Retry-After" in resp
    assert resp["X-RateLimit-Remaining"] == "0"


def test_unthrottled_methods_pass_through():
    """Only POST is throttled in our test decorator — GET should always pass."""
    factory = RequestFactory()
    # Fill the POST bucket
    for _ in range(3):
        sample_view(factory.post("/"))
    # GET keeps flowing
    resp = sample_view(factory.get("/"))
    assert resp.status_code == 200


def test_different_ips_get_separate_buckets():
    factory = RequestFactory()
    req_a = factory.post("/")
    req_a.META["REMOTE_ADDR"] = "1.2.3.4"
    req_b = factory.post("/")
    req_b.META["REMOTE_ADDR"] = "5.6.7.8"

    for _ in range(3):
        assert sample_view(req_a).status_code == 200
    # Client A is now at the limit; client B still has a full budget
    assert sample_view(req_a).status_code == 429
    assert sample_view(req_b).status_code == 200
