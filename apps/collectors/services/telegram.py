"""Telegram public-channel collector (MTProto via Telethon).

Real-mode pipeline: reads channel metadata + recent messages using a
server-side Telegram user session configured once via ``TELEGRAM_API_ID``,
``TELEGRAM_API_HASH``, and ``TELEGRAM_SESSION_STRING``. No per-user OAuth
flow — the user connects a public channel by its ``@username``.

Coroutines are async; call them from sync code (views, Celery tasks) via
``run_sync``. The per-request lifecycle (``async with self._authed_client()``)
avoids lingering connections in Celery prefork workers.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Awaitable, TypeVar

from django.conf import settings

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel, Message

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TelegramNotConfigured(RuntimeError):
    """Raised when TELEGRAM_API_ID / HASH / SESSION_STRING are not all set,
    or when the session is no longer authorised."""


def run_sync(coro: Awaitable[T]) -> T:
    """Execute a coroutine from synchronous code.

    Always creates a fresh event loop — safe inside Celery prefork workers
    and Django sync views where no loop is running.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@dataclass(frozen=True)
class ChannelInfo:
    external_id: str
    handle: str
    display_name: str
    follower_count: int


@dataclass(frozen=True)
class ChannelMessage:
    external_id: str
    caption: str
    url: str
    published_at: datetime
    views: int
    likes: int
    comments_count: int
    shares: int


def _normalise_handle(raw: str) -> str:
    """Accept ``@foo``, ``foo``, or ``https://t.me/foo`` and return ``foo``."""
    v = raw.strip().lstrip("@")
    if "/" in v:
        v = v.rsplit("/", 1)[-1]
    return v


class TelegramCollector:
    """MTProto public-channel reader backed by a server-side user session."""

    def __init__(self) -> None:
        api_id = settings.TELEGRAM_API_ID
        api_hash = settings.TELEGRAM_API_HASH
        session = settings.TELEGRAM_SESSION_STRING
        if not (api_id and api_hash and session):
            raise TelegramNotConfigured(
                "Telegram real mode is not configured — set TELEGRAM_API_ID, "
                "TELEGRAM_API_HASH, and TELEGRAM_SESSION_STRING in .env "
                "(see docs/TELEGRAM_SETUP.md)."
            )
        self._api_id = int(api_id)
        self._api_hash = str(api_hash)
        self._session = str(session)

    @classmethod
    def is_configured(cls) -> bool:
        return bool(
            settings.TELEGRAM_API_ID
            and settings.TELEGRAM_API_HASH
            and settings.TELEGRAM_SESSION_STRING
        )

    def _client(self) -> TelegramClient:
        return TelegramClient(StringSession(self._session), self._api_id, self._api_hash)

    @asynccontextmanager
    async def _authed_client(self) -> AsyncIterator[TelegramClient]:
        client = self._client()
        await client.connect()
        try:
            if not await client.is_user_authorized():
                raise TelegramNotConfigured(
                    "Telegram session not authorised — regenerate "
                    "TELEGRAM_SESSION_STRING (see docs/TELEGRAM_SETUP.md)."
                )
            yield client
        finally:
            await client.disconnect()

    async def fetch_channel_info(self, username: str) -> ChannelInfo:
        username = _normalise_handle(username)
        async with self._authed_client() as client:
            entity = await client.get_entity(username)
            if not isinstance(entity, Channel):
                raise ValueError(
                    f"@{username} Telegram kanali emas "
                    f"(turi: {type(entity).__name__})."
                )
            full = await client(GetFullChannelRequest(entity))
            return ChannelInfo(
                external_id=str(entity.id),
                handle=entity.username or username,
                display_name=entity.title or username,
                follower_count=int(full.full_chat.participants_count or 0),
            )

    async def fetch_recent_messages(
        self, username: str, limit: int | None = 50
    ) -> list[ChannelMessage]:
        """``limit=None`` paginates through every available post — slow on
        large channels but the only way to seed full history for analytics."""
        username = _normalise_handle(username)
        messages: list[ChannelMessage] = []
        async with self._authed_client() as client:
            entity = await client.get_entity(username)
            if not isinstance(entity, Channel):
                raise ValueError(
                    f"@{username} Telegram kanali emas "
                    f"(turi: {type(entity).__name__})."
                )
            channel_handle = entity.username or username
            async for msg in client.iter_messages(entity, limit=limit):
                if not isinstance(msg, Message):
                    continue
                text = (msg.message or "").strip()
                if not text and not msg.media:
                    continue
                likes = 0
                if msg.reactions and getattr(msg.reactions, "results", None):
                    likes = sum(int(r.count) for r in msg.reactions.results)
                replies = (
                    int(getattr(msg.replies, "replies", 0) or 0)
                    if msg.replies
                    else 0
                )
                messages.append(
                    ChannelMessage(
                        external_id=str(msg.id),
                        caption=text,
                        url=f"https://t.me/{channel_handle}/{msg.id}",
                        published_at=msg.date,
                        views=int(msg.views or 0),
                        likes=likes,
                        comments_count=replies,
                        shares=int(msg.forwards or 0),
                    )
                )
        return messages
