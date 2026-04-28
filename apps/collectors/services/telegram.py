"""Telegram MTProto collector + per-user phone-login auth flow.

Two surfaces here:

1. :class:`TelegramCollector` — reads channel metadata + messages. Defaults
   to the platform-wide server session (``TELEGRAM_SESSION_STRING``); can
   also be instantiated with a per-user session string so each connected
   account fetches data through that user's own Telegram identity.

2. :class:`TelegramPhoneAuth` — multi-step phone+SMS login that returns a
   user-bound session string. Powers the "Connect Telegram" UI: user enters
   phone → SMS code → optional 2FA password → channel picker.

Both call into Telethon's async API. Run coroutines from sync Django views
or Celery tasks via :func:`run_sync` (creates a fresh event loop each call).
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
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
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
class UserChannel:
    """A channel/group from the logged-in user's dialogs list."""
    external_id: str
    handle: str           # may be empty for private channels
    display_name: str
    is_broadcast: bool    # one-way channel (admin posts, others read)
    is_megagroup: bool    # supergroup (chat with members)
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
    """MTProto reader. Uses a per-user session when given, otherwise falls
    back to the platform-wide server session from settings."""

    def __init__(self, session_string: str | None = None) -> None:
        api_id = settings.TELEGRAM_API_ID
        api_hash = settings.TELEGRAM_API_HASH
        # Caller-supplied session (per-user) takes precedence over the
        # server-wide one; the server session stays as a fallback so the
        # public-channel "type @username" path still works for users who
        # haven't logged in with their phone.
        session = session_string or settings.TELEGRAM_SESSION_STRING
        if not (api_id and api_hash and session):
            raise TelegramNotConfigured(
                "Telegram real mode is not configured — set TELEGRAM_API_ID "
                "and TELEGRAM_API_HASH in .env, then either log a user in via "
                "the phone flow or set TELEGRAM_SESSION_STRING for the "
                "platform-wide server session."
            )
        self._api_id = int(api_id)
        self._api_hash = str(api_hash)
        self._session = str(session)

    @classmethod
    def is_configured(cls) -> bool:
        """Real-mode is reachable as long as we can run the phone auth flow
        (API ID + Hash) — even without a session, the user can log in to
        bootstrap one. ``TELEGRAM_SESSION_STRING`` only matters for the
        legacy "type @username" flow without per-user login.
        """
        return bool(settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH)

    @classmethod
    def has_server_session(cls) -> bool:
        """True iff the platform-wide fallback session is configured."""
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

    async def list_user_dialogs(self) -> list["UserChannel"]:
        """List every channel/group the *session-owner* user belongs to.

        Used by the per-user phone-login flow's channel picker. Skips DMs
        and bots — only broadcast channels and supergroups (megagroups) are
        analytically meaningful.
        """
        out: list[UserChannel] = []
        async with self._authed_client() as client:
            async for dialog in client.iter_dialogs(archived=False):
                ent = dialog.entity
                if not isinstance(ent, Channel):
                    continue  # users + small groups skipped
                out.append(UserChannel(
                    external_id    = str(ent.id),
                    handle         = ent.username or "",
                    display_name   = ent.title or "",
                    is_broadcast   = bool(getattr(ent, "broadcast", False)),
                    is_megagroup   = bool(getattr(ent, "megagroup", False)),
                    follower_count = int(getattr(ent, "participants_count", 0) or 0),
                ))
        # Broadcast channels first (more analytics-worthy), then megagroups.
        out.sort(key=lambda c: (not c.is_broadcast, c.display_name.lower()))
        return out

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


# ============================================================================
# Phone login flow — produces a per-user session string for TelegramCollector.
# ============================================================================


class TelegramPhoneAuthError(RuntimeError):
    """Translates Telethon's phone-login exceptions into user-readable strings."""


@dataclass(frozen=True)
class CodeSent:
    """Returned by :meth:`TelegramPhoneAuth.send_code`. Persist the session
    string + phone_code_hash on the Django session and reuse on the code-
    verify step."""
    session_string: str
    phone_code_hash: str


@dataclass(frozen=True)
class SignedIn:
    """Returned when the user is fully logged in — either after the first
    code-verify or after a successful 2FA password submit."""
    session_string: str


class TelegramPhoneAuth:
    """Drives the phone-number → SMS-code → optional-2FA login flow.

    Each step instantiates a fresh client (loading the prior session string
    if any) to keep state across HTTP requests. Telethon stores the phone
    code hash on the SentCode object — we surface it explicitly so the
    Django view can stash it in the user's session between steps.
    """

    @staticmethod
    def _require_app_creds() -> tuple[int, str]:
        api_id = settings.TELEGRAM_API_ID
        api_hash = settings.TELEGRAM_API_HASH
        if not (api_id and api_hash):
            raise TelegramNotConfigured(
                "TELEGRAM_API_ID / TELEGRAM_API_HASH .env'ga yozilmagan."
            )
        return int(api_id), str(api_hash)

    @classmethod
    async def send_code(cls, phone: str) -> CodeSent:
        """Ask Telegram to SMS a login code. Returns the in-progress session
        string + ``phone_code_hash`` — both are needed to verify the code.
        """
        api_id, api_hash = cls._require_app_creds()
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        try:
            try:
                sent = await client.send_code_request(phone)
            except PhoneNumberInvalidError as e:
                raise TelegramPhoneAuthError(
                    "Telefon raqami noto'g'ri formatda — +998... ko'rinishida kiriting."
                ) from e
            session_string = client.session.save()
            return CodeSent(session_string=session_string, phone_code_hash=sent.phone_code_hash)
        finally:
            await client.disconnect()

    @classmethod
    async def verify_code(
        cls, session_string: str, phone: str, code: str, phone_code_hash: str
    ) -> SignedIn | None:
        """Submit the SMS code. Returns:

        * :class:`SignedIn` if the account has no 2FA — login is complete.
        * ``None`` if 2FA is enabled — caller must collect the password
          and call :meth:`verify_password` with the (still-valid) session
          string we re-saved here.
        """
        api_id, api_hash = cls._require_app_creds()
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        await client.connect()
        try:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                # Save partial session state — view will redirect to password form.
                # Re-save first so the password step picks up the same connection state.
                cls._refresh_session_after_partial(client)
                return None
            except PhoneCodeInvalidError as e:
                raise TelegramPhoneAuthError("Kod noto'g'ri.") from e
            except PhoneCodeExpiredError as e:
                raise TelegramPhoneAuthError(
                    "Kod muddati tugadi — qaytadan urining."
                ) from e
            return SignedIn(session_string=client.session.save())
        finally:
            await client.disconnect()

    @classmethod
    async def verify_password(cls, session_string: str, password: str) -> SignedIn:
        """Submit the 2FA password after a code that triggered SessionPasswordNeededError."""
        api_id, api_hash = cls._require_app_creds()
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        await client.connect()
        try:
            try:
                await client.sign_in(password=password)
            except Exception as e:
                raise TelegramPhoneAuthError(f"2FA paroli noto'g'ri: {e}") from e
            return SignedIn(session_string=client.session.save())
        finally:
            await client.disconnect()

    @staticmethod
    def _refresh_session_after_partial(client: TelegramClient) -> None:
        """No-op anchor for the SessionPasswordNeededError path — Telethon's
        StringSession is implicitly updated by ``client.session`` access on
        the calling side, so we just leave a hook for future bookkeeping
        (e.g. storing dc_id / auth_key edits)."""
        return None
