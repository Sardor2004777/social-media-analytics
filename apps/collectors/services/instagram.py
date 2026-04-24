"""Instagram API with Instagram Login — direct IG OAuth, no Facebook Page required.

Meta's newer Instagram API (announced 2024) lets users sign in *directly*
with their Instagram credentials on instagram.com, bypassing the whole
Facebook-Login → Page → IG-Business-account chain. The Instagram account
must still be **Business** or **Creator**, but there's no need to own a
Facebook Page.

Setup (one-time, in Meta Developer dashboard):
    1. Add product "Instagram" to the app.
    2. Under "Instagram → API setup with Instagram business login":
         - Set an Instagram business login redirect URI to
           ``<site>/social/connect/instagram/callback/``
    3. Note the **Instagram App ID** and **Instagram App Secret** under that
       product's settings — these differ from the main Meta App ID/Secret.
       Put them in .env as ``META_APP_ID`` / ``META_APP_SECRET`` (we reuse
       the same env var names for simplicity).

Flow:
    user → instagram.com/oauth/authorize (IG login + consent)
    → redirect back with ``code``
    → POST /oauth/access_token → short-lived user token (1h)
    → GET /access_token?grant_type=ig_exchange_token → long-lived (60 days)
    → GET /me?fields=... → account info
    → persist long-lived token encrypted on ConnectedAccount
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime

# Instagram business login endpoints (different from Facebook Graph API).
AUTH_DIALOG        = "https://www.instagram.com/oauth/authorize"
TOKEN_SHORT_URL    = "https://api.instagram.com/oauth/access_token"
TOKEN_LONG_URL     = "https://graph.instagram.com/access_token"
GRAPH_BASE         = "https://graph.instagram.com"

# Minimal scopes for read-only analytics. Adding ``instagram_business_manage_insights``
# later unlocks views/reach metrics but usually requires app review.
SCOPES = [
    "instagram_business_basic",
]


class InstagramNotConfigured(RuntimeError):
    """Raised when META_APP_ID / META_APP_SECRET are missing."""


class InstagramNoBusinessAccount(RuntimeError):
    """Kept for API compatibility — not raised in the Instagram-Login flow."""


@dataclass
class IGAccountInfo:
    external_id: str
    handle: str
    display_name: str
    avatar_url: str
    follower_count: int
    media_count: int


@dataclass
class IGMediaInfo:
    external_id: str
    caption: str
    url: str
    media_type: str      # IMAGE | VIDEO | CAROUSEL_ALBUM | REELS
    published_at: datetime
    likes: int
    comments_count: int


class InstagramCollector:
    """Instagram Login flow + Graph API v21 data calls."""

    @staticmethod
    def is_configured() -> bool:
        return bool(
            getattr(settings, "META_APP_ID", "")
            and getattr(settings, "META_APP_SECRET", "")
        )

    @classmethod
    def _require_configured(cls) -> None:
        if not cls.is_configured():
            raise InstagramNotConfigured(
                "META_APP_ID / META_APP_SECRET are not set in .env (use the "
                "Instagram App ID + Secret from Meta Developer → Instagram → "
                "API setup with Instagram business login)."
            )

    # ------------------------------------------------------------------ OAuth

    @classmethod
    def build_auth_url(cls, redirect_uri: str, state: str) -> str:
        cls._require_configured()
        params = {
            "client_id":     settings.META_APP_ID,
            "redirect_uri":  redirect_uri,
            "state":         state,
            "scope":         ",".join(SCOPES),
            "response_type": "code",
        }
        return f"{AUTH_DIALOG}?{urlencode(params)}"

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> tuple[str, int]:
        """Swap ``code`` for a short-lived (1h) token, then upgrade to long-
        lived (60d). Returns ``(access_token, expires_in_seconds)``.
        """
        cls._require_configured()
        # Step 1: code → short-lived token (POST form-encoded).
        short = requests.post(
            TOKEN_SHORT_URL,
            data={
                "client_id":     settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "grant_type":    "authorization_code",
                "redirect_uri":  redirect_uri,
                "code":          code,
            },
            timeout=15,
        )
        short.raise_for_status()
        short_json = short.json()
        short_token = short_json["access_token"]

        # Step 2: short → long-lived token.
        long = requests.get(
            TOKEN_LONG_URL,
            params={
                "grant_type":    "ig_exchange_token",
                "client_secret": settings.META_APP_SECRET,
                "access_token":  short_token,
            },
            timeout=15,
        )
        long.raise_for_status()
        data = long.json()
        return data["access_token"], int(data.get("expires_in", 5184000))

    @classmethod
    def refresh_long_lived(cls, long_token: str) -> tuple[str, int]:
        """Refresh a long-lived token before the 60-day expiry. Returns
        ``(new_token, expires_in_seconds)``. Call from a periodic task.
        """
        resp = requests.get(
            f"{GRAPH_BASE}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": long_token},
            timeout=15,
        )
        resp.raise_for_status()
        d = resp.json()
        return d["access_token"], int(d.get("expires_in", 5184000))

    # ------------------------------------------------------------------- Data

    # The Facebook-Login flow used a page token to look up an IG account; the
    # Instagram-Login flow gives us the IG account directly via /me. Keep the
    # signature for backward compat with existing views/tasks, but derive both
    # values from a single /me call.
    @classmethod
    def find_ig_business_account(cls, access_token: str) -> tuple[str, str]:
        """Return ``(ig_user_id, access_token)`` — we already have the token
        tied to the right IG account, so the "search across Pages" step from
        the old Facebook Login flow is a no-op here.
        """
        resp = requests.get(
            f"{GRAPH_BASE}/me",
            params={"fields": "id", "access_token": access_token},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["id"], access_token

    @classmethod
    def fetch_account_info(cls, ig_user_id: str, access_token: str) -> IGAccountInfo:
        resp = requests.get(
            f"{GRAPH_BASE}/{ig_user_id}",
            params={
                "fields":       "id,username,name,account_type,"
                                "profile_picture_url,followers_count,media_count",
                "access_token": access_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        d = resp.json()
        return IGAccountInfo(
            external_id    = d["id"],
            handle         = d.get("username", "") or d["id"],
            display_name   = d.get("name", "") or d.get("username", ""),
            avatar_url     = d.get("profile_picture_url", "") or "",
            follower_count = int(d.get("followers_count", 0) or 0),
            media_count    = int(d.get("media_count", 0) or 0),
        )

    @classmethod
    def fetch_recent_media(
        cls, ig_user_id: str, access_token: str, limit: int = 50
    ) -> list[IGMediaInfo]:
        out: list[IGMediaInfo] = []
        url: str | None = f"{GRAPH_BASE}/{ig_user_id}/media"
        params: dict | None = {
            "fields":       "id,caption,media_type,permalink,timestamp,"
                            "like_count,comments_count",
            "limit":        min(50, limit),
            "access_token": access_token,
        }
        while url and len(out) < limit:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for m in data.get("data", []):
                ts = parse_datetime(m.get("timestamp") or "") or datetime.utcnow()
                out.append(IGMediaInfo(
                    external_id    = m["id"],
                    caption        = (m.get("caption") or "").strip(),
                    url            = m.get("permalink") or "",
                    media_type     = m.get("media_type") or "IMAGE",
                    published_at   = ts,
                    likes          = int(m.get("like_count", 0) or 0),
                    comments_count = int(m.get("comments_count", 0) or 0),
                ))
                if len(out) >= limit:
                    break
            url = (data.get("paging") or {}).get("next")
            params = None
        return out
