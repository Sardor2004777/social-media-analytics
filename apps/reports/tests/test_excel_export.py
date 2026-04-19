"""Tests for Excel export service + view."""
from __future__ import annotations

import io
import zipfile

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.collectors.services.mock_generator import DemoDataGenerator
from apps.reports.services.excel import build_workbook

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded_user():
    User = get_user_model()
    u = User(username="export-test@example.com", email="export-test@example.com")
    u.set_password("x!23QWE123")
    u.save()
    DemoDataGenerator(seed=11).seed(
        u, posts_per_platform=3, comments_per_post_range=(2, 3), days_back=30,
    )
    return u


def test_workbook_is_valid_xlsx_bytes(seeded_user) -> None:
    data = build_workbook(seeded_user)
    assert isinstance(data, bytes)
    assert data[:4] == b"PK\x03\x04"          # XLSX = zip file
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        # The five logical sheets round-trip to sheet?.xml entries
        names = z.namelist()
        assert any("xl/workbook.xml" in n for n in names)
        assert sum(1 for n in names if n.startswith("xl/worksheets/sheet")) >= 5


def test_export_view_requires_login() -> None:
    c = Client()
    url = reverse("reports:export_xlsx")
    resp = c.get(url)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


def test_export_view_returns_xlsx(seeded_user) -> None:
    c = Client()
    c.force_login(seeded_user)
    resp = c.get(reverse("reports:export_xlsx"))
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/vnd.openxmlformats-officedocument")
    assert "attachment;" in resp["Content-Disposition"]
    assert resp.content[:4] == b"PK\x03\x04"
