"""Smoke tests for every authenticated dashboard page.

Each page is rendered with a seeded demo user — the goal is to catch
template-render errors and missing URL reverses before deploy, not to assert
content correctness (that's covered by the model/service test suites).
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.collectors.services.mock_generator import DemoDataGenerator

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    User = get_user_model()
    u = User(username="page-tests@example.com", email="page-tests@example.com")
    u.set_password("x!23QWE123")
    u.save()
    return u


@pytest.fixture
def seeded_user(user):
    DemoDataGenerator(seed=77).seed(
        user, posts_per_platform=4, comments_per_post_range=(2, 3), days_back=30,
    )
    return user


@pytest.fixture
def client_auth(seeded_user) -> Client:
    c = Client()
    c.force_login(seeded_user)
    return c


@pytest.mark.parametrize("name", [
    "dashboard:app",
    "social:accounts",
    "analytics:overview",
    "analytics:sentiment",
    "reports:index",
    "accounts:settings",
])
def test_page_renders_for_seeded_user(client_auth: Client, name: str) -> None:
    url = reverse(name)
    resp = client_auth.get(url)
    assert resp.status_code == 200, f"{name} returned {resp.status_code}"
    assert b"<!DOCTYPE html>" in resp.content


@pytest.mark.parametrize("name", [
    "dashboard:app",
    "social:accounts",
    "analytics:overview",
    "analytics:sentiment",
    "reports:index",
    "accounts:settings",
    "reports:export_xlsx",
    "reports:export_pdf",
])
def test_auth_pages_require_login(name: str) -> None:
    c = Client()
    resp = c.get(reverse(name))
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


@pytest.mark.parametrize("platform", ["instagram", "telegram", "youtube", "x"])
def test_connect_form_renders(client_auth: Client, platform: str) -> None:
    resp = client_auth.get(reverse("social:connect", args=[platform]))
    assert resp.status_code == 200
    assert b"csrfmiddlewaretoken" in resp.content
    assert b"handle" in resp.content


def test_connect_bad_platform_returns_404(client_auth: Client) -> None:
    resp = client_auth.get(reverse("social:connect", args=["myspace"]))
    assert resp.status_code == 404


def test_connect_post_creates_account(client_auth: Client, seeded_user) -> None:
    from apps.social.models import ConnectedAccount
    before = ConnectedAccount.objects.filter(user=seeded_user, platform="instagram").count()
    resp = client_auth.post(
        reverse("social:connect", args=["instagram"]),
        {"handle": "test_connect_handle", "posts": 12},
        follow=False,
    )
    assert resp.status_code == 302
    after = ConnectedAccount.objects.filter(user=seeded_user, platform="instagram").count()
    assert after == before + 1
    assert ConnectedAccount.objects.filter(user=seeded_user, handle="test_connect_handle").exists()


def test_settings_form_post_updates_user(client_auth: Client, seeded_user) -> None:
    resp = client_auth.post(
        reverse("accounts:settings"),
        {"first_name": "Test", "last_name": "User", "email": seeded_user.email},
    )
    assert resp.status_code == 302
    seeded_user.refresh_from_db()
    assert seeded_user.first_name == "Test"


def test_pdf_export_returns_pdf_bytes(client_auth: Client) -> None:
    resp = client_auth.get(reverse("reports:export_pdf"))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_terms_page_anonymous(client_auth: Client) -> None:
    c = Client()
    for name in ["dashboard:terms", "dashboard:privacy"]:
        resp = c.get(reverse(name))
        assert resp.status_code == 200
