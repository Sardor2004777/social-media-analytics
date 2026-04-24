"""YouTube Data API v3 collector — OAuth 2.0 flow + channel/video fetching.

Uses the user's own Google OAuth tokens (``youtube.readonly`` scope). The
token flow is intentionally small: we build the consent URL, swap the code
for tokens, and hand those tokens to ``google-api-python-client`` when
calling the Data API. Tokens live encrypted on
:class:`apps.social.models.ConnectedAccount` (see ``EncryptedTextField``).

Requires ``YOUTUBE_OAUTH_CLIENT_ID`` + ``YOUTUBE_OAUTH_SECRET`` in .env —
credentials come from the same Google Cloud project as the allauth login
flow; just enable "YouTube Data API v3" in the API library.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.utils.dateparse import parse_datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

AUTH_URI  = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"


class YouTubeNotConfigured(RuntimeError):
    """Raised when YOUTUBE_OAUTH_CLIENT_ID/SECRET are missing."""


@dataclass
class ChannelInfo:
    external_id: str
    handle: str
    display_name: str
    avatar_url: str
    follower_count: int
    video_count: int


@dataclass
class VideoInfo:
    external_id: str
    caption: str
    url: str
    published_at: datetime
    views: int
    likes: int
    comments_count: int


class YouTubeCollector:
    """Thin wrapper around google-api-python-client for YouTube Data API v3."""

    @staticmethod
    def is_configured() -> bool:
        return bool(
            getattr(settings, "YOUTUBE_OAUTH_CLIENT_ID", "")
            and getattr(settings, "YOUTUBE_OAUTH_SECRET", "")
        )

    @classmethod
    def _client_config(cls) -> dict:
        if not cls.is_configured():
            raise YouTubeNotConfigured(
                "YOUTUBE_OAUTH_CLIENT_ID / YOUTUBE_OAUTH_SECRET are not set in .env"
            )
        return {
            "web": {
                "client_id":     settings.YOUTUBE_OAUTH_CLIENT_ID,
                "client_secret": settings.YOUTUBE_OAUTH_SECRET,
                "auth_uri":      AUTH_URI,
                "token_uri":     TOKEN_URI,
            }
        }

    # ------------------------------------------------------------------ OAuth

    @classmethod
    def build_auth_url(cls, redirect_uri: str, state: str) -> tuple[str, str]:
        """Return ``(auth_url, code_verifier)``.

        Google's OAuth endpoint enforces PKCE — ``google-auth-oauthlib`` >=1.3
        auto-generates a ``code_verifier`` and sends its challenge with the
        authorization request. The verifier must be round-tripped on callback,
        so callers must persist it (e.g. in the Django session) between the
        two requests and pass it back into :meth:`exchange_code`.
        """
        flow = Flow.from_client_config(
            cls._client_config(),
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )
        url, _ = flow.authorization_url(
            access_type="offline",          # returns a refresh_token
            include_granted_scopes="true",
            prompt="consent",               # force refresh_token even on re-auth
            state=state,
        )
        return url, flow.code_verifier or ""

    @classmethod
    def exchange_code(
        cls, code: str, redirect_uri: str, code_verifier: str = ""
    ) -> Credentials:
        """Swap an authorization code for ``Credentials`` (access + refresh).

        Pass the same ``code_verifier`` that was stashed during
        :meth:`build_auth_url`, otherwise Google returns ``invalid_grant:
        Missing code verifier``.
        """
        flow = Flow.from_client_config(
            cls._client_config(),
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )
        if code_verifier:
            flow.code_verifier = code_verifier
        flow.fetch_token(code=code)
        return flow.credentials

    @classmethod
    def _credentials(cls, access_token: str, refresh_token: str = "") -> Credentials:
        return Credentials(
            token=access_token,
            refresh_token=refresh_token or None,
            token_uri=TOKEN_URI,
            client_id=settings.YOUTUBE_OAUTH_CLIENT_ID,
            client_secret=settings.YOUTUBE_OAUTH_SECRET,
            scopes=SCOPES,
        )

    @classmethod
    def _service(cls, access_token: str, refresh_token: str = ""):
        creds = cls._credentials(access_token, refresh_token)
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    # ----------------------------------------------------------------- Fetch

    @classmethod
    def fetch_mine_channel(
        cls, access_token: str, refresh_token: str = ""
    ) -> ChannelInfo:
        """Return the YouTube channel belonging to the authenticated user.

        Raises ``RuntimeError`` if the Google account has no YouTube channel
        (rare but possible — user must create one at youtube.com first).
        """
        yt = cls._service(access_token, refresh_token)
        resp = yt.channels().list(part="id,snippet,statistics", mine=True).execute()
        items = resp.get("items") or []
        if not items:
            raise RuntimeError(
                "Ushbu Google akkauntida YouTube kanali topilmadi — "
                "https://youtube.com ga kirib kanal yarating."
            )
        ch = items[0]
        snippet = ch.get("snippet", {})
        stats = ch.get("statistics", {})
        thumb = (
            snippet.get("thumbnails", {}).get("high")
            or snippet.get("thumbnails", {}).get("default")
            or {}
        )
        return ChannelInfo(
            external_id    = ch["id"],
            handle         = (snippet.get("customUrl") or "").lstrip("@") or ch["id"],
            display_name   = snippet.get("title", ""),
            avatar_url     = thumb.get("url", ""),
            follower_count = int(stats.get("subscriberCount", 0) or 0),
            video_count    = int(stats.get("videoCount", 0) or 0),
        )

    @classmethod
    def fetch_recent_videos(
        cls,
        access_token: str,
        channel_id: str,
        limit: int = 50,
        refresh_token: str = "",
    ) -> list[VideoInfo]:
        """Return the ``limit`` most recent videos for ``channel_id`` with stats.

        Uses the channel's "uploads" playlist (cheapest way to list videos),
        then batch-fetches statistics in groups of 50 ids.
        """
        yt = cls._service(access_token, refresh_token)

        ch_resp = yt.channels().list(part="contentDetails", id=channel_id).execute()
        items = ch_resp.get("items") or []
        if not items:
            return []
        uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        video_ids: list[str] = []
        page_token: str | None = None
        while len(video_ids) < limit:
            pl = yt.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_id,
                maxResults=min(50, limit - len(video_ids)),
                pageToken=page_token,
            ).execute()
            for it in pl.get("items", []):
                video_ids.append(it["contentDetails"]["videoId"])
            page_token = pl.get("nextPageToken")
            if not page_token:
                break

        out: list[VideoInfo] = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            vids = yt.videos().list(
                part="snippet,statistics", id=",".join(batch)
            ).execute()
            for v in vids.get("items", []):
                sn = v.get("snippet", {})
                st = v.get("statistics", {})
                pub = parse_datetime(sn.get("publishedAt") or "") or datetime.now(dt_timezone.utc)
                out.append(VideoInfo(
                    external_id    = v["id"],
                    caption        = sn.get("title", "") or "",
                    url            = f"https://www.youtube.com/watch?v={v['id']}",
                    published_at   = pub,
                    views          = int(st.get("viewCount", 0) or 0),
                    likes          = int(st.get("likeCount", 0) or 0),
                    comments_count = int(st.get("commentCount", 0) or 0),
                ))
        return out
