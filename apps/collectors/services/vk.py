"""VKontakte (VK) collector — OAuth 2.0 + wall.get for personal accounts.

VK is the easiest "real" social network to integrate after Telegram + YouTube:
plain OAuth 2.0 (no PKCE, no app review for read scopes), free, and works
on personal accounts in Uzbekistan + the wider CIS region.

Setup (one-time, in VK developer console):
    1. https://vk.com/editapp?act=create — create a "Standalone" or "Website" app.
    2. Authorized redirect URI:
         https://<your-host>/social/connect/vk/callback/
    3. Note the app's "ID" (= client_id) and "Secret key" (= client_secret).
    4. Put them in .env as ``VK_CLIENT_ID`` / ``VK_CLIENT_SECRET``.

Flow:
    user → oauth.vk.com/authorize → vk login + consent
    → redirect back with ``code``
    → GET oauth.vk.com/access_token → ``(access_token, user_id, expires_in)``
    → GET api.vk.com/method/users.get → profile + counters
    → GET api.vk.com/method/wall.get → posts on user's wall
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlencode

import requests
from django.conf import settings

API_VERSION = "5.131"            # pinned — VK preserves backwards compat per major
AUTH_DIALOG = "https://oauth.vk.com/authorize"
TOKEN_URL   = "https://oauth.vk.com/access_token"
API_BASE    = "https://api.vk.com/method"

# wall — read posts. offline — non-expiring token. Both are auto-approved
# (no app review) for "Standalone" / "Website" apps.
SCOPES = ["wall", "offline"]


class VKNotConfigured(RuntimeError):
    """Raised when VK_CLIENT_ID / VK_CLIENT_SECRET are missing."""


class VKAPIError(RuntimeError):
    """VK returned ``{"error": {...}}`` instead of a success payload."""


@dataclass
class VKAccountInfo:
    external_id: str        # VK numeric user id, as string
    handle: str             # screen_name (e.g. "id12345" or vanity slug)
    display_name: str
    avatar_url: str
    follower_count: int     # counters.followers
    posts_count: int        # counters.user_videos / posts not exposed; we use len(wall) later


@dataclass
class VKPost:
    external_id: str        # "{owner_id}_{post_id}" — VK's canonical id
    caption: str
    url: str
    published_at: datetime
    views: int
    likes: int
    comments_count: int
    shares: int
    media_kind: str         # "photo" | "video" | "link" | "audio" | "text"


class VKCollector:
    """Plain ``requests`` wrapper around the VK API v5.131."""

    @staticmethod
    def is_configured() -> bool:
        return bool(
            getattr(settings, "VK_CLIENT_ID", "")
            and getattr(settings, "VK_CLIENT_SECRET", "")
        )

    @classmethod
    def _require_configured(cls) -> None:
        if not cls.is_configured():
            raise VKNotConfigured(
                "VK_CLIENT_ID / VK_CLIENT_SECRET .env'ga yozilmagan."
            )

    # ------------------------------------------------------------------ OAuth

    @classmethod
    def build_auth_url(cls, redirect_uri: str, state: str) -> str:
        cls._require_configured()
        params = {
            "client_id":     settings.VK_CLIENT_ID,
            "redirect_uri":  redirect_uri,
            "scope":         ",".join(SCOPES),
            "response_type": "code",
            "v":             API_VERSION,
            "state":         state,
            "display":       "page",
        }
        return f"{AUTH_DIALOG}?{urlencode(params)}"

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> tuple[str, str, int]:
        """Swap ``code`` for ``(access_token, user_id, expires_in)``.

        With the ``offline`` scope ``expires_in`` is ``0`` (token never
        expires until the user revokes it).
        """
        cls._require_configured()
        resp = requests.get(
            TOKEN_URL,
            params={
                "client_id":     settings.VK_CLIENT_ID,
                "client_secret": settings.VK_CLIENT_SECRET,
                "redirect_uri":  redirect_uri,
                "code":          code,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise VKAPIError(
                f"VK token exchange failed: {data.get('error_description') or data['error']}"
            )
        return data["access_token"], str(data["user_id"]), int(data.get("expires_in", 0) or 0)

    # ------------------------------------------------------------------- Data

    @classmethod
    def _api(cls, method: str, access_token: str, **params) -> dict:
        full = {**params, "access_token": access_token, "v": API_VERSION}
        resp = requests.get(f"{API_BASE}/{method}", params=full, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise VKAPIError(
                f"VK {method} failed [{err.get('error_code')}]: "
                f"{err.get('error_msg', 'unknown')}"
            )
        return data["response"]

    @classmethod
    def fetch_account_info(cls, user_id: str, access_token: str) -> VKAccountInfo:
        items = cls._api(
            "users.get",
            access_token=access_token,
            user_ids=user_id,
            fields="photo_200,screen_name,counters,first_name,last_name",
        )
        if not items:
            raise VKAPIError(f"VK user {user_id} not found")
        u = items[0]
        counters = u.get("counters") or {}
        full_name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
        return VKAccountInfo(
            external_id    = str(u["id"]),
            handle         = u.get("screen_name") or f"id{u['id']}",
            display_name   = full_name or u.get("screen_name") or f"id{u['id']}",
            avatar_url     = u.get("photo_200", "") or "",
            follower_count = int(counters.get("followers", 0) or 0),
            posts_count    = 0,   # filled later by wall.get total
        )

    @classmethod
    def fetch_recent_posts(
        cls, owner_id: str, access_token: str, limit: int = 50
    ) -> list[VKPost]:
        """Return up to ``limit`` posts from the user's wall (newest first).

        VK paginates 100 per request; we batch to fill ``limit``. Stops
        early when VK indicates we've walked past the end.
        """
        out: list[VKPost] = []
        offset = 0
        page_size = min(100, max(1, limit))

        while len(out) < limit:
            data = cls._api(
                "wall.get",
                access_token=access_token,
                owner_id=owner_id,
                count=min(page_size, limit - len(out)),
                offset=offset,
                extended=0,
            )
            items = data.get("items", [])
            if not items:
                break
            for it in items:
                pid = it.get("id")
                if pid is None:
                    continue
                ts = int(it.get("date") or 0)
                published_at = datetime.fromtimestamp(ts, tz=dt_timezone.utc) if ts else datetime.now(dt_timezone.utc)
                out.append(VKPost(
                    external_id    = f"{owner_id}_{pid}",
                    caption        = (it.get("text") or "").strip(),
                    url            = f"https://vk.com/wall{owner_id}_{pid}",
                    published_at   = published_at,
                    views          = int((it.get("views") or {}).get("count", 0) or 0),
                    likes          = int((it.get("likes") or {}).get("count", 0) or 0),
                    comments_count = int((it.get("comments") or {}).get("count", 0) or 0),
                    shares         = int((it.get("reposts") or {}).get("count", 0) or 0),
                    media_kind     = _classify_attachments(it.get("attachments") or []),
                ))
                if len(out) >= limit:
                    break
            total = int(data.get("count") or 0)
            offset += len(items)
            if offset >= total:
                break
        return out


def _classify_attachments(atts: list[dict]) -> str:
    """Pick the first analytics-meaningful attachment kind, or ``"text"``."""
    if not atts:
        return "text"
    # VK lists attachments in order; the first one is usually the "primary"
    # asset — match our cross-platform PostType buckets.
    primary = (atts[0] or {}).get("type", "")
    if primary == "photo":
        return "photo"
    if primary == "video":
        return "video"
    if primary == "audio":
        return "audio"
    if primary == "link":
        return "link"
    if primary == "doc":
        return "document"
    return "text"
