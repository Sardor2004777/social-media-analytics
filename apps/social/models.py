"""Platform-agnostic social graph models.

A ``ConnectedAccount`` represents one external account (IG handle, Telegram
channel, YouTube channel, X profile) attached to a Django user. It is the
aggregation root for every ``Post`` that flows through collectors.

The same schema is used whether data arrives from a real OAuth-backed API or
from the in-repo demo seeder — in the latter case ``is_demo=True`` so real
data is never accidentally mixed in.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.fields import EncryptedTextField
from apps.core.models import TimestampedModel


class Platform(models.TextChoices):
    INSTAGRAM = "instagram", "Instagram"
    TELEGRAM  = "telegram",  "Telegram"
    YOUTUBE   = "youtube",   "YouTube"
    X         = "x",         "X (Twitter)"


class ConnectedAccount(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connected_accounts",
    )
    platform = models.CharField(max_length=16, choices=Platform.choices, db_index=True)
    external_id  = models.CharField(max_length=128, help_text=_("Platform-side account id"))
    handle       = models.CharField(max_length=128, help_text=_("Public @username or channel id"))
    display_name = models.CharField(max_length=256, blank=True)
    avatar_url   = models.URLField(blank=True)

    follower_count  = models.PositiveIntegerField(default=0)
    following_count = models.PositiveIntegerField(default=0)

    # OAuth credentials — encrypted at rest via Fernet (ENCRYPTION_KEY).
    # Empty for Telegram MTProto (server-side session) and for public-only
    # YouTube reads using YOUTUBE_API_KEY.
    access_token     = EncryptedTextField(blank=True, default="")
    refresh_token    = EncryptedTextField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes           = models.CharField(max_length=512, blank=True, default="")

    is_demo = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("True for accounts seeded by the demo generator."),
    )

    class Meta:
        unique_together = [("platform", "external_id")]
        indexes = [
            models.Index(fields=["user", "platform"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_platform_display()}: @{self.handle}"

    @property
    def needs_token_refresh(self) -> bool:
        """True when the access token is expired or about to expire (60s slack)."""
        from datetime import timedelta
        from django.utils import timezone

        if not self.token_expires_at:
            return False
        return self.token_expires_at <= timezone.now() + timedelta(seconds=60)


class PostType(models.TextChoices):
    PHOTO        = "photo",        "Photo"
    VIDEO        = "video",        "Video"
    REEL         = "reel",         "Reel"
    CAROUSEL     = "carousel",     "Carousel"
    TWEET        = "tweet",        "Tweet"
    CHANNEL_POST = "channel_post", "Channel post"


class Post(TimestampedModel):
    account = models.ForeignKey(
        ConnectedAccount,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    external_id   = models.CharField(max_length=128)
    post_type     = models.CharField(max_length=16, choices=PostType.choices, default=PostType.PHOTO)
    caption       = models.TextField(blank=True)
    url           = models.URLField(blank=True)
    published_at  = models.DateTimeField(db_index=True)

    # Metrics (platform-normalised)
    views          = models.PositiveIntegerField(default=0)
    likes          = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    shares         = models.PositiveIntegerField(default=0)

    # Calculated / cached
    engagement_rate = models.FloatField(default=0.0, help_text=_("(likes + comments + shares) / views"))

    class Meta:
        unique_together = [("account", "external_id")]
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["account", "-published_at"]),
            models.Index(fields=["-published_at"]),
        ]

    def __str__(self) -> str:
        head = (self.caption or "").strip().replace("\n", " ")[:60]
        return f"[{self.account.platform}] {head or self.external_id}"


class PublicShareLink(TimestampedModel):
    """Shareable public URL for an account's read-only dashboard snapshot.

    Each active row (``is_active=True``) grants anonymous read access to the
    linked account at ``/social/share/<token>/``. Flipping the row inactive
    revokes the URL; a fresh ``create_for`` gets a new token. One account
    may accumulate multiple rows (rotation history); the view always resolves
    by token directly, no "pick the latest" dance required.
    """
    account = models.ForeignKey(
        ConnectedAccount,
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    token     = models.CharField(max_length=32, unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"Share {self.token} → @{self.account.handle}"

    @classmethod
    def create_for(cls, account: "ConnectedAccount") -> "PublicShareLink":
        import secrets
        return cls.objects.create(
            account=account,
            token=secrets.token_urlsafe(12),
            is_active=True,
        )
