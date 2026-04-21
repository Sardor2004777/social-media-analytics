"""Unit tests for the sync_telegram_account Celery task.

The real collector is replaced with an in-memory fake so no Telegram API
calls are made. Exercises: demo-account skip, missing-account path, happy
path + idempotent re-run.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.collectors.services.telegram import ChannelInfo, ChannelMessage
from apps.collectors.tasks import sync_telegram_account
from apps.social.models import ConnectedAccount, Platform, Post

pytestmark = pytest.mark.django_db


# ---------- fixtures & helpers ----------

@pytest.fixture
def user():
    User = get_user_model()
    u = User(username="tg-task@example.com", email="tg-task@example.com")
    u.set_password("x!23QWE123")
    u.save()
    return u


def _make_account(user, *, is_demo: bool = False, handle: str = "durov") -> ConnectedAccount:
    return ConnectedAccount.objects.create(
        user=user,
        platform=Platform.TELEGRAM,
        external_id=f"ext-{handle}",
        handle=handle,
        display_name=handle,
        follower_count=100,
        is_demo=is_demo,
    )


def _fake_messages(n: int = 3) -> list[ChannelMessage]:
    now = timezone.now()
    return [
        ChannelMessage(
            external_id=f"m{i}",
            caption=f"post {i}",
            url=f"https://t.me/durov/{i}",
            published_at=now - timedelta(hours=i),
            views=100 * (i + 1),
            likes=10 * (i + 1),
            comments_count=i,
            shares=i,
        )
        for i in range(n)
    ]


def _patch_collector(
    monkeypatch, info: ChannelInfo, messages: list[ChannelMessage]
) -> None:
    class _FakeCollector:
        async def fetch_channel_info(self, handle: str) -> ChannelInfo:
            return info

        async def fetch_recent_messages(
            self, handle: str, limit: int = 50
        ) -> list[ChannelMessage]:
            return messages

    monkeypatch.setattr(
        "apps.collectors.tasks.TelegramCollector",
        lambda: _FakeCollector(),
    )


# ---------- tests ----------

def test_sync_skips_demo_accounts(user) -> None:
    account = _make_account(user, is_demo=True)
    result = sync_telegram_account.apply(args=[account.id]).get()
    assert result == {"account_id": account.id, "status": "skipped_demo"}
    assert Post.objects.filter(account=account).count() == 0


def test_sync_returns_not_found_for_missing_account() -> None:
    result = sync_telegram_account.apply(args=[99_999]).get()
    assert result == {"account_id": 99_999, "status": "not_found"}


def test_sync_populates_posts_and_metadata(user, monkeypatch) -> None:
    account = _make_account(user)
    info = ChannelInfo(
        external_id="ext-durov-new",
        handle="durov",
        display_name="Pavel Durov",
        follower_count=1_000_000,
    )
    _patch_collector(monkeypatch, info, _fake_messages(3))

    result = sync_telegram_account.apply(args=[account.id]).get()
    assert result["status"] == "ok"
    assert result["created"] == 3
    assert result["updated"] == 0
    assert result["follower_count"] == 1_000_000

    account.refresh_from_db()
    assert account.follower_count == 1_000_000
    assert account.display_name == "Pavel Durov"
    assert account.external_id == "ext-durov-new"

    posts = list(Post.objects.filter(account=account).order_by("external_id"))
    assert len(posts) == 3
    assert {p.external_id for p in posts} == {"m0", "m1", "m2"}
    # first message: views=100, likes=10, comments=0, shares=0
    assert posts[0].engagement_rate == pytest.approx(10 / 100)


def test_sync_is_idempotent(user, monkeypatch) -> None:
    account = _make_account(user)
    info = ChannelInfo(
        external_id="ext-durov-new",
        handle="durov",
        display_name="Pavel Durov",
        follower_count=1_000_000,
    )
    _patch_collector(monkeypatch, info, _fake_messages(3))

    first = sync_telegram_account.apply(args=[account.id]).get()
    second = sync_telegram_account.apply(args=[account.id]).get()

    assert first["created"] == 3 and first["updated"] == 0
    assert second["created"] == 0 and second["updated"] == 3
    assert Post.objects.filter(account=account).count() == 3


def test_sync_respects_post_limit(user, monkeypatch) -> None:
    account = _make_account(user)
    info = ChannelInfo(
        external_id="ext-durov-new",
        handle="durov",
        display_name="Pavel Durov",
        follower_count=1_000_000,
    )

    captured: dict[str, int] = {}

    class _FakeCollector:
        async def fetch_channel_info(self, handle: str) -> ChannelInfo:
            return info

        async def fetch_recent_messages(
            self, handle: str, limit: int = 50
        ) -> list[ChannelMessage]:
            captured["limit"] = limit
            return []

    monkeypatch.setattr(
        "apps.collectors.tasks.TelegramCollector",
        lambda: _FakeCollector(),
    )

    sync_telegram_account.apply(args=[account.id], kwargs={"post_limit": 17}).get()
    assert captured["limit"] == 17
