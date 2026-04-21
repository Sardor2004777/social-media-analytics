"""Unit tests for the Telegram MTProto collector (no network).

Covers pure helpers + configuration gates. The async fetch methods are thin
wrappers around the Telethon client API and are best covered by integration
tests (marked separately), not mocked here.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from django.test import override_settings

from apps.collectors.services.telegram import (
    ChannelInfo,
    ChannelMessage,
    TelegramCollector,
    TelegramNotConfigured,
    _normalise_handle,
    run_sync,
)


# ---------- _normalise_handle ----------

@pytest.mark.parametrize("raw,expected", [
    ("foo", "foo"),
    ("@foo", "foo"),
    ("  @foo  ", "foo"),
    ("https://t.me/foo", "foo"),
    ("t.me/foo", "foo"),
    ("@foo_bar", "foo_bar"),
])
def test_normalise_handle(raw: str, expected: str) -> None:
    assert _normalise_handle(raw) == expected


# ---------- is_configured ----------

@override_settings(
    TELEGRAM_API_ID="123",
    TELEGRAM_API_HASH="hash",
    TELEGRAM_SESSION_STRING="sess",
)
def test_is_configured_true_when_all_set() -> None:
    assert TelegramCollector.is_configured() is True


@override_settings(TELEGRAM_API_ID="", TELEGRAM_API_HASH="", TELEGRAM_SESSION_STRING="")
def test_is_configured_false_when_empty() -> None:
    assert TelegramCollector.is_configured() is False


@override_settings(
    TELEGRAM_API_ID="123",
    TELEGRAM_API_HASH="hash",
    TELEGRAM_SESSION_STRING="",
)
def test_is_configured_false_when_session_missing() -> None:
    assert TelegramCollector.is_configured() is False


# ---------- Constructor ----------

@override_settings(TELEGRAM_API_ID="", TELEGRAM_API_HASH="", TELEGRAM_SESSION_STRING="")
def test_init_raises_when_not_configured() -> None:
    with pytest.raises(TelegramNotConfigured):
        TelegramCollector()


@override_settings(
    TELEGRAM_API_ID="123456",
    TELEGRAM_API_HASH="abcdef0123456789",
    TELEGRAM_SESSION_STRING="1BVt-stub-session-string",
)
def test_init_succeeds_when_configured() -> None:
    c = TelegramCollector()
    assert c._api_id == 123456
    assert c._api_hash == "abcdef0123456789"


# ---------- run_sync ----------

def test_run_sync_executes_coroutine() -> None:
    async def _hello() -> str:
        return "hello"

    assert run_sync(_hello()) == "hello"


def test_run_sync_propagates_exceptions() -> None:
    async def _boom() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_sync(_boom())


# ---------- Dataclass shape ----------

def test_channel_info_is_frozen() -> None:
    info = ChannelInfo(external_id="1", handle="foo", display_name="Foo", follower_count=10)
    with pytest.raises((AttributeError, TypeError)):
        info.handle = "bar"  # type: ignore[misc]


def test_channel_message_is_frozen() -> None:
    m = ChannelMessage(
        external_id="1",
        caption="x",
        url="https://t.me/foo/1",
        published_at=datetime.now(timezone.utc),
        views=1,
        likes=1,
        comments_count=0,
        shares=0,
    )
    with pytest.raises((AttributeError, TypeError)):
        m.caption = "y"  # type: ignore[misc]
