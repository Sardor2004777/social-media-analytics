"""Tests for ``core.TimestampedModel``.

Uses a concrete throwaway subclass declared in-process — we don't want a
permanent migration just for a test.
"""
from __future__ import annotations

import pytest
from django.utils import timezone

from apps.core.models import TimestampedModel


def test_timestamped_is_abstract() -> None:
    """`TimestampedModel` itself cannot be instantiated into a table."""
    assert TimestampedModel._meta.abstract is True


def test_timestamped_has_expected_fields() -> None:
    """Both timestamp fields exist with the expected behaviour flags."""
    fields = {f.name: f for f in TimestampedModel._meta.get_fields()}
    assert "created_at" in fields
    assert "updated_at" in fields
    assert fields["created_at"].auto_now_add is True
    assert fields["updated_at"].auto_now is True


def test_timezone_is_tashkent() -> None:
    """Project-wide TZ must stay Asia/Tashkent — a regression guard."""
    assert str(timezone.get_current_timezone()) == "Asia/Tashkent"
