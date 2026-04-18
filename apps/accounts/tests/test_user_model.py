"""Tests for the custom ``accounts.User`` model.

Kept minimal in Phase 2 — real auth flow tests land in Phase 3.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_user_created_with_email_as_login_field() -> None:
    """`USERNAME_FIELD` is email — user is identifiable by email."""
    user = User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="very-secret-pw-1",
    )
    assert user.email == "alice@example.com"
    assert user.check_password("very-secret-pw-1")
    assert User.USERNAME_FIELD == "email"


@pytest.mark.django_db
def test_email_must_be_unique() -> None:
    """Duplicate email raises IntegrityError — not allowed at DB level."""
    User.objects.create_user(
        username="u1", email="dup@example.com", password="x-very-long-1"
    )
    with pytest.raises(IntegrityError):
        User.objects.create_user(
            username="u2", email="dup@example.com", password="x-very-long-2"
        )


@pytest.mark.django_db
def test_str_returns_email() -> None:
    """`__str__` returns email for admin / logs readability."""
    user = User.objects.create_user(
        username="bob", email="bob@example.com", password="pw-long-enough-1"
    )
    assert str(user) == "bob@example.com"


@pytest.mark.django_db
def test_superuser_flags() -> None:
    """`create_superuser` sets staff + superuser flags."""
    admin = User.objects.create_superuser(
        username="admin", email="admin@example.com", password="admin-pw-long-1"
    )
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.is_active is True
