"""Instagram Graph API collector — OAuth + account/media fetching.

Instagram is accessed via Meta's *Graph API* (not the deprecated Basic
Display API). The account being analysed must be a **Business / Creator
account linked to a Facebook Page** — personal accounts cannot grant the
needed scopes. End-user flow:

    User → "Connect Instagram"
    → redirects to facebook.com/dialog/oauth with page scopes
    → user picks a Facebook Page
    → callback exchanges code → short-lived token
    → exchange short → long-lived (60-day) token
    → list /me/accounts, pick the first Page whose
      instagram_business_account is set
    → persist IG user-id + long-lived token encrypted on ConnectedAccount

Requires ``META_APP_ID`` + ``META_APP_SECRET`` in .env. The redirect URI
must match what's registered in the Meta App dashboard — we compute it
from the Django request so localhost and production hosts both work.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime

# Meta bumps its Graph API version ~every quarter; older versions keep
# working for a year+. Pin here to get predictable field behaviour.
API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
OAUTH_DIALOG = f"https://www.facebook.com/{API_VERSION}/dialog/oauth"

# Minimum scopes for read-only analytics. ``business_management`` and
# ``pages_read_engagement`` require app review for production but they also
# reject outright in dev mode on fresh apps, so we only request what the app
# has by default: basic IG account reads + the Page list that surfaces the
# instagram_business_account link.
SCOPES = [
    "instagram_basic",
    "pages_show_list",
]


class InstagramNotConfigured(RuntimeError):
    """Raised when META_APP_ID / META_APP_SECRET are missing."""


class InstagramNoBusinessAccount(RuntimeError):
    """Raised when the user's FB Pages don't expose an IG Business account."""


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
    """Thin requests-based wrapper around Meta Graph API v21.0."""

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
                "META_APP_ID / META_APP_SECRET are not set in .env"
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
        return f"{OAUTH_DIALOG}?{urlencode(params)}"

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> tuple[str, int]:
        """Swap ``code`` for a short-lived user token, then upgrade it to the
        60-day long-lived token. Returns ``(access_token, expires_in_seconds)``.
        """
        cls._require_configured()
        short = requests.get(
            f"{BASE_URL}/oauth/access_token",
            params={
                "client_id":     settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "redirect_uri":  redirect_uri,
                "code":          code,
            },
            timeout=15,
        )
        short.raise_for_status()
        short_token = short.json()["access_token"]

        long = requests.get(
            f"{BASE_URL}/oauth/access_token",
            params={
                "grant_type":        "fb_exchange_token",
                "client_id":         settings.META_APP_ID,
                "client_secret":     settings.META_APP_SECRET,
                "fb_exchange_token": short_token,
            },
            timeout=15,
        )
        long.raise_for_status()
        data = long.json()
        return data["access_token"], int(data.get("expires_in", 5184000))

    # ------------------------------------------------------------------- Data

    @classmethod
    def find_ig_business_account(cls, access_token: str) -> tuple[str, str]:
        """Walk the user's Facebook Pages and return ``(ig_user_id, page_token)``
        of the first Page that has a linked Instagram Business account.

        We use the *Page* access token (not the user token) for downstream
        IG calls — that's what Meta requires once you've selected a page.
        """
        resp = requests.get(
            f"{BASE_URL}/me/accounts",
            params={
                "fields":       "id,name,access_token,instagram_business_account",
                "access_token": access_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        pages = resp.json().get("data", [])
        for p in pages:
            ig = p.get("instagram_business_account")
            if ig and ig.get("id"):
                return ig["id"], p["access_token"]
        raise InstagramNoBusinessAccount(
            "Facebook Page'larda Instagram Business akkaunti topilmadi. "
            "IG akkauntingizni Business rejimga o'tkazing va Facebook Page'ga "
            "bog'lang."
        )

    @classmethod
    def fetch_account_info(cls, ig_user_id: str, page_token: str) -> IGAccountInfo:
        resp = requests.get(
            f"{BASE_URL}/{ig_user_id}",
            params={
                "fields":       "id,username,name,profile_picture_url,"
                                "followers_count,media_count",
                "access_token": page_token,
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
        cls, ig_user_id: str, page_token: str, limit: int = 50
    ) -> list[IGMediaInfo]:
        out: list[IGMediaInfo] = []
        url: str | None = f"{BASE_URL}/{ig_user_id}/media"
        params: dict | None = {
            "fields":       "id,caption,media_type,permalink,timestamp,"
                            "like_count,comments_count",
            "limit":        min(50, limit),
            "access_token": page_token,
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
            # Subsequent page URLs from Meta embed query params already.
            params = None
        return out
