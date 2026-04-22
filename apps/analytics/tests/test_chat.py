"""Unit tests for the AI chat service (no network — no API calls made)."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.analytics.services.chat import (
    ChatNotConfigured,
    _build_user_context,
    ask,
    is_configured,
)
from apps.social.models import ConnectedAccount, Platform

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    User = get_user_model()
    u = User(username="chat-user@example.com", email="chat-user@example.com")
    u.set_password("x!23QWE123")
    u.save()
    return u


# ---------- is_configured ----------

@override_settings(OPENAI_API_KEY="")
def test_is_configured_false_without_key() -> None:
    assert is_configured() is False


@override_settings(OPENAI_API_KEY="sk-test-abc123")
def test_is_configured_true_with_key() -> None:
    assert is_configured() is True


# ---------- _build_user_context ----------

def test_build_context_empty_accounts(user) -> None:
    ctx = _build_user_context(user)
    assert "no connected accounts" in ctx.lower()


def test_build_context_includes_account_handle(user) -> None:
    ConnectedAccount.objects.create(
        user=user,
        platform=Platform.TELEGRAM,
        external_id="ext-chat-1",
        handle="durov",
        display_name="Pavel Durov",
        follower_count=1_000_000,
    )
    ctx = _build_user_context(user)
    assert "@durov" in ctx
    assert "1,000,000" in ctx
    assert "Telegram" in ctx


def test_build_context_multiple_accounts(user) -> None:
    for i, plat in enumerate(
        [Platform.TELEGRAM, Platform.INSTAGRAM, Platform.YOUTUBE]
    ):
        ConnectedAccount.objects.create(
            user=user,
            platform=plat,
            external_id=f"ext-chat-{i}",
            handle=f"acct{i}",
            follower_count=(i + 1) * 1000,
        )
    ctx = _build_user_context(user)
    for i in range(3):
        assert f"@acct{i}" in ctx
    assert "Telegram" in ctx
    assert "Instagram" in ctx
    assert "YouTube" in ctx


# ---------- ask error paths ----------

@override_settings(OPENAI_API_KEY="")
def test_ask_raises_without_key(user) -> None:
    with pytest.raises(ChatNotConfigured, match="OPENAI_API_KEY"):
        ask(user, "anything")
