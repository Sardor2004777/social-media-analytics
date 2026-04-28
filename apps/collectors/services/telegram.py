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
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.types import (
    Channel,
    Chat,
    InputChannel,
    InputPeerChannel,
    InputPeerChat,
    Message,
)

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
    access_hash: int      # 0 for legacy Chat (not needed), required for Channel
    entity_type: str      # "channel" | "chat"
    handle: str           # may be empty for private channels
    display_name: str
    is_broadcast: bool    # one-way channel (admin posts, others read)
    is_megagroup: bool    # supergroup (chat with members)
    is_owner: bool        # logged-in user created this channel/group
    is_admin: bool        # logged-in user has any admin rights here
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
    media_kind: str   # "photo" | "video" | "document" | "audio" | "poll" | "text"


def _classify_media(msg: Message) -> str:
    """Bucket a Telegram :class:`Message` into an analytics-friendly media kind.

    Order matters: ``msg.video`` and ``msg.photo`` are convenience properties
    that look at ``msg.media`` under the hood, so we check those first; the
    plain ``document`` fallback covers PDFs, archives, etc.
    """
    if getattr(msg, "photo", None):
        return "photo"
    if getattr(msg, "video", None) or getattr(msg, "video_note", None) or getattr(msg, "gif", None):
        return "video"
    if getattr(msg, "voice", None) or getattr(msg, "audio", None):
        return "audio"
    if getattr(msg, "poll", None):
        return "poll"
    if getattr(msg, "document", None):
        return "document"
    return "text"


def _normalise_handle(raw: str) -> str | int:
    """Accept ``@foo``, ``foo``, ``https://t.me/foo``, or a stringified
    channel id and return whatever Telethon's ``get_entity`` can resolve.

    Numeric ids stay as ``int`` so private/no-username channels (looked up
    from the user's own dialogs cache) don't get treated as usernames.
    """
    v = raw.strip().lstrip("@")
    if "/" in v:
        v = v.rsplit("/", 1)[-1]
    # ``-100123…`` style supergroup ids and plain numeric channel ids.
    if v.lstrip("-").isdigit():
        return int(v)
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

    async def fetch_channel_info(
        self,
        username: str,
        *,
        entity_type: str | None = None,
        access_hash: int = 0,
    ) -> ChannelInfo:
        """Resolve a Telegram entity by username, numeric id + access_hash,
        or numeric id (Chat). Pass ``entity_type`` (``"channel"`` or
        ``"chat"``) + ``access_hash`` when reconnecting to a previously
        picked channel — Telethon's StringSession does NOT persist its
        access-hash cache, so we have to feed it back in via InputPeer.
        """
        target = _normalise_handle(username)
        async with self._authed_client() as client:
            entity = await self._resolve_entity(client, target, entity_type, access_hash)
            if isinstance(entity, Channel):
                full = await client(GetFullChannelRequest(entity))
                handle = entity.username or (str(target) if isinstance(target, str) else "")
                return ChannelInfo(
                    external_id=str(entity.id),
                    handle=handle,
                    display_name=entity.title or handle or str(entity.id),
                    follower_count=int(full.full_chat.participants_count or 0),
                )
            if isinstance(entity, Chat):
                # Legacy chat — different RPC, no username, slightly different
                # full-chat schema. participants_count lives directly on full_chat.
                full = await client(GetFullChatRequest(entity.id))
                participants = full.full_chat.participants
                count = (
                    len(participants.participants)
                    if participants and getattr(participants, "participants", None)
                    else int(getattr(entity, "participants_count", 0) or 0)
                )
                return ChannelInfo(
                    external_id=str(entity.id),
                    handle="",
                    display_name=entity.title or str(entity.id),
                    follower_count=count,
                )
            raise ValueError(
                f"{target} Telegram kanali yoki guruhi emas "
                f"(turi: {type(entity).__name__})."
            )

    @staticmethod
    async def _resolve_entity(client, target, entity_type: str | None, access_hash: int):
        """Return a Channel or Chat object for ``target`` using whichever
        resolution path actually has the data Telethon needs:

        * ``entity_type="chat"`` → ``InputPeerChat(int)`` (no hash needed)
        * ``entity_type="channel"`` + ``access_hash`` → ``InputPeerChannel`` so
          the lookup works even though StringSession dropped the entity cache.
        * Fallback (username string, or no hint) → ``client.get_entity(target)``.
        """
        try:
            if entity_type == "chat" and isinstance(target, int):
                return await client.get_entity(InputPeerChat(chat_id=target))
            if entity_type == "channel" and isinstance(target, int) and access_hash:
                return await client.get_entity(
                    InputPeerChannel(channel_id=target, access_hash=access_hash)
                )
            return await client.get_entity(target)
        except ValueError as e:
            raise ValueError(
                f"Telegram bu kanal/guruhni topa olmadi: {target}. "
                f"Akkauntingiz hali a'zo bo'lmagan bo'lishi mumkin."
            ) from e

    async def list_user_dialogs(self) -> tuple[list["UserChannel"], str]:
        """List every channel + group + legacy chat the session-owner is in.

        Returns ``(channels, refreshed_session_string)``. The refreshed
        session contains the access-hash cache that ``iter_dialogs``
        populates — the picker view persists it back so the subsequent
        POST (which calls ``fetch_channel_info`` for the picked entity)
        can resolve private/numeric-id channels without a second fetch.

        Skips DMs and bots — anything else (broadcast channels, supergroups,
        legacy Chat groups that haven't been upgraded) shows up in the picker.
        """
        out: list[UserChannel] = []
        async with self._authed_client() as client:
            async for dialog in client.iter_dialogs(archived=False):
                ent = dialog.entity
                if isinstance(ent, Channel):
                    is_owner = bool(getattr(ent, "creator", False))
                    is_admin = bool(getattr(ent, "admin_rights", None))
                    out.append(UserChannel(
                        external_id    = str(ent.id),
                        access_hash    = int(getattr(ent, "access_hash", 0) or 0),
                        entity_type    = "channel",
                        handle         = ent.username or "",
                        display_name   = ent.title or "",
                        is_broadcast   = bool(getattr(ent, "broadcast", False)),
                        is_megagroup   = bool(getattr(ent, "megagroup", False)),
                        is_owner       = is_owner,
                        is_admin       = is_admin or is_owner,
                        follower_count = int(getattr(ent, "participants_count", 0) or 0),
                    ))
                elif isinstance(ent, Chat):
                    # Legacy small groups (max ~200 members, no @username, no
                    # admin_rights or creator flag on the entity itself).
                    # Telegram doesn't expose ownership cheaply here, so we
                    # mark them as non-admin and let the user pick anyway.
                    if getattr(ent, "deactivated", False):
                        continue
                    out.append(UserChannel(
                        external_id    = str(ent.id),
                        access_hash    = 0,                # not needed for Chat
                        entity_type    = "chat",
                        handle         = "",
                        display_name   = ent.title or "",
                        is_broadcast   = False,
                        is_megagroup   = True,           # treat as a group for filters
                        is_owner       = False,
                        is_admin       = False,
                        follower_count = int(getattr(ent, "participants_count", 0) or 0),
                    ))
                # Users / Bots / unknown — skip.
            refreshed_session = client.session.save()
        # Owned/admin first, then plain subscriptions; broadcast before group;
        # alphabetical within each tier.
        out.sort(key=lambda c: (
            0 if c.is_owner else (1 if c.is_admin else 2),
            not c.is_broadcast,
            c.display_name.lower(),
        ))
        return out, refreshed_session

    async def fetch_recent_messages(
        self,
        username: str,
        limit: int | None = 50,
        *,
        entity_type: str | None = None,
        access_hash: int = 0,
    ) -> list[ChannelMessage]:
        """``limit=None`` paginates through every available post — slow on
        large channels but the only way to seed full history for analytics."""
        target = _normalise_handle(username)
        messages: list[ChannelMessage] = []
        async with self._authed_client() as client:
            entity = await self._resolve_entity(client, target, entity_type, access_hash)
            if not isinstance(entity, (Channel, Chat)):
                raise ValueError(
                    f"{target} Telegram kanali yoki guruhi emas "
                    f"(turi: {type(entity).__name__})."
                )
            # Legacy chats have no username; build a usable URL fallback from id.
            if isinstance(entity, Channel):
                channel_handle = entity.username or (
                    str(target) if isinstance(target, str) else str(entity.id)
                )
            else:
                channel_handle = str(entity.id)
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
                        media_kind=_classify_media(msg),
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
