"""Minimal smoke tests so CI + pytest wire up correctly in Phase 2.

Real app tests land in their respective phases.
"""
from django.test import Client
from django.urls import reverse


def test_homepage_returns_200() -> None:
    """Landing page renders for anonymous users."""
    client = Client()
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200


def test_admin_redirects_anonymous() -> None:
    """Admin requires auth and redirects to login."""
    client = Client()
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_api_schema_available() -> None:
    """drf-spectacular schema endpoint renders."""
    client = Client()
    response = client.get("/api/v1/schema/")
    assert response.status_code == 200
