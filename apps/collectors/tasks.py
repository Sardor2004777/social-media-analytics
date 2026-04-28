"""Celery tasks that fetch real data from connected social platforms.

Tasks live in the ``collectors`` queue (see ``config/settings/base.py``).
Each task takes a ``ConnectedAccount`` id and refreshes data in-place; the
``(account, external_id)`` unique constraint keeps re-runs idempotent.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from apps.social.models import ConnectedAccount, Platform, Post, PostType

from .services.instagram import (
    InstagramCollector,
    InstagramNoBusinessAccount,
    InstagramNotConfigured,
)
from .services.telegram import TelegramCollector, run_sync
from .services.youtube import YouTubeCollector, YouTubeNotConfigured

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue="collectors",
    name="apps.collectors.tasks.sync_telegram_account",
)
def sync_telegram_account(self, account_id: int, post_limit: int = 50) -> dict:
    """Refresh channel metadata + last ``post_limit`` messages for a Telegram account.

    Demo accounts are skipped (they're seeded and never touched by real collectors).
    Existing posts are updated in-place; new posts are inserted.
    """
    try:
        account = ConnectedAccount.objects.get(
            id=account_id, platform=Platform.TELEGRAM
        )
    except ConnectedAccount.DoesNotExist:
        logger.warning("sync_telegram_account: account %s not found", account_id)
        return {"account_id": account_id, "status": "not_found"}

    if account.is_demo:
        logger.info("sync_telegram_account: skipping demo account %s", account_id)
        return {"account_id": account_id, "status": "skipped_demo"}

    # Per-user session (from the phone-login flow) is preferred — falls
    # back to the platform-wide server session for legacy accounts that
    # were connected via the "type @username" path.
    user_session = account.access_token or None
    collector = TelegramCollector(session_string=user_session)

    # Recover entity_type + access_hash that the picker stuffed into scopes:
    # "tg:<channel|chat>:<access_hash>". Falls back to ("channel", 0) for
    # legacy rows from the @handle-only flow.
    entity_type, access_hash = "channel", 0
    if account.scopes and account.scopes.startswith("tg:"):
        parts = account.scopes.split(":", 2)
        if len(parts) == 3:
            entity_type = parts[1] or "channel"
            try:
                access_hash = int(parts[2] or 0)
            except ValueError:
                access_hash = 0

    # Pick the resolution target:
    # * Picker-flow rows know their entity_type — use the numeric external_id
    #   so InputPeer construction in _resolve_entity actually fires. The
    #   ``handle`` column on these rows can be a human title (e.g. "Shaxsiy
    #   music") rather than a Telegram @username, which would otherwise be
    #   misread as a username and fail with "Cannot find any entity".
    # * Legacy rows (no scopes prefix) keep the old behaviour — try the
    #   @handle first, fall back to external_id.
    if account.scopes and account.scopes.startswith("tg:"):
        handle_or_id = account.external_id
    else:
        handle_or_id = account.handle or account.external_id

    info = run_sync(collector.fetch_channel_info(
        handle_or_id, entity_type=entity_type, access_hash=access_hash,
    ))
    # ``post_limit=0`` (sentinel from the Connect view) means "every post" —
    # forward as ``None`` so Telethon iter_messages paginates until exhausted.
    fetch_limit = None if post_limit == 0 else post_limit
    messages = run_sync(
        collector.fetch_recent_messages(
            handle_or_id, limit=fetch_limit,
            entity_type=entity_type, access_hash=access_hash,
        )
    )

    with transaction.atomic():
        account.external_id = info.external_id
        account.display_name = info.display_name or account.display_name
        account.follower_count = info.follower_count
        account.save()

        # Map Telegram media kind onto our cross-platform PostType so the
        # dashboard can break down by photo / video / text instead of
        # lumping everything under CHANNEL_POST.
        _MEDIA_TO_POST_TYPE = {
            "photo":    PostType.PHOTO,
            "video":    PostType.VIDEO,
            "audio":    PostType.CHANNEL_POST,    # no PostType.AUDIO yet
            "document": PostType.CHANNEL_POST,
            "poll":     PostType.CHANNEL_POST,
            "text":     PostType.CHANNEL_POST,
        }

        created = 0
        updated = 0
        for m in messages:
            denom = max(m.views, 1)
            _obj, is_new = Post.objects.update_or_create(
                account=account,
                external_id=m.external_id,
                defaults={
                    "post_type": _MEDIA_TO_POST_TYPE.get(m.media_kind, PostType.CHANNEL_POST),
                    "caption": m.caption,
                    "url": m.url,
                    "published_at": m.published_at,
                    "views": m.views,
                    "likes": m.likes,
                    "comments_count": m.comments_count,
                    "shares": m.shares,
                    "engagement_rate": (
                        m.likes + m.comments_count + m.shares
                    ) / denom,
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

    logger.info(
        "sync_telegram_account: %s (@%s) → +%d new / %d updated",
        account.id, account.handle, created, updated,
    )
    return {
        "account_id": account_id,
        "status": "ok",
        "handle": account.handle,
        "created": created,
        "updated": updated,
        "follower_count": info.follower_count,
    }


@shared_task(
    queue="collectors",
    name="apps.collectors.tasks.sync_all_telegram_accounts",
)
def sync_all_telegram_accounts() -> dict:
    """Fan-out task: enqueue a sync for every real (non-demo) Telegram account.

    Intended for Celery Beat at ``COLLECT_INTERVAL_HOURS`` cadence.
    """
    ids = list(
        ConnectedAccount.objects.filter(
            platform=Platform.TELEGRAM, is_demo=False
        ).values_list("id", flat=True)
    )
    for aid in ids:
        sync_telegram_account.delay(aid)
    return {"enqueued": len(ids), "account_ids": ids}


# ------------------------------------------------------------------- YouTube


@shared_task(
    bind=True,
    queue="collectors",
    name="apps.collectors.tasks.sync_youtube_account",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def sync_youtube_account(self, account_id: int, video_limit: int = 50) -> dict:
    """Refresh channel metadata + last ``video_limit`` videos for a YouTube account.

    Uses the per-account encrypted OAuth tokens. Demo accounts are skipped.
    Existing videos are updated in-place via the ``(account, external_id)``
    unique key; new ones are inserted.
    """
    try:
        account = ConnectedAccount.objects.get(
            id=account_id, platform=Platform.YOUTUBE
        )
    except ConnectedAccount.DoesNotExist:
        logger.warning("sync_youtube_account: account %s not found", account_id)
        return {"account_id": account_id, "status": "not_found"}

    if account.is_demo:
        logger.info("sync_youtube_account: skipping demo account %s", account_id)
        return {"account_id": account_id, "status": "skipped_demo"}

    if not account.access_token:
        logger.warning(
            "sync_youtube_account: no access_token for account %s — reconnect required",
            account_id,
        )
        return {"account_id": account_id, "status": "missing_token"}

    try:
        info = YouTubeCollector.fetch_mine_channel(
            access_token=account.access_token,
            refresh_token=account.refresh_token,
        )
        videos = YouTubeCollector.fetch_recent_videos(
            access_token=account.access_token,
            channel_id=account.external_id,
            limit=video_limit,
            refresh_token=account.refresh_token,
        )
    except YouTubeNotConfigured as e:
        logger.error("sync_youtube_account: %s", e)
        return {"account_id": account_id, "status": "not_configured"}

    with transaction.atomic():
        account.display_name = info.display_name or account.display_name
        account.avatar_url = info.avatar_url or account.avatar_url
        account.follower_count = info.follower_count
        account.save(update_fields=[
            "display_name", "avatar_url", "follower_count", "updated_at",
        ])

        created = 0
        updated = 0
        for v in videos:
            denom = max(v.views, 1)
            _obj, is_new = Post.objects.update_or_create(
                account=account,
                external_id=v.external_id,
                defaults={
                    "post_type":       PostType.VIDEO,
                    "caption":         v.caption,
                    "url":             v.url,
                    "published_at":    v.published_at,
                    "views":           v.views,
                    "likes":           v.likes,
                    "comments_count":  v.comments_count,
                    "shares":          0,  # YouTube Data API doesn't expose share count
                    "engagement_rate": (v.likes + v.comments_count) / denom,
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

    logger.info(
        "sync_youtube_account: %s (@%s) → +%d new / %d updated",
        account.id, account.handle, created, updated,
    )
    return {
        "account_id":     account_id,
        "status":         "ok",
        "handle":         account.handle,
        "created":        created,
        "updated":        updated,
        "follower_count": info.follower_count,
    }


@shared_task(
    queue="collectors",
    name="apps.collectors.tasks.sync_all_youtube_accounts",
)
def sync_all_youtube_accounts() -> dict:
    """Fan-out task: enqueue a sync for every real (non-demo) YouTube account."""
    ids = list(
        ConnectedAccount.objects.filter(
            platform=Platform.YOUTUBE, is_demo=False
        ).exclude(access_token="").values_list("id", flat=True)
    )
    for aid in ids:
        sync_youtube_account.delay(aid)
    return {"enqueued": len(ids), "account_ids": ids}


# ----------------------------------------------------------------- Instagram


@shared_task(
    bind=True,
    queue="collectors",
    name="apps.collectors.tasks.sync_instagram_account",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def sync_instagram_account(self, account_id: int, media_limit: int = 50) -> dict:
    """Refresh IG Business profile + last ``media_limit`` media items.

    Uses the encrypted Facebook *Page* access token (not the user token) — IG
    Graph API requires page tokens for all downstream calls.
    """
    try:
        account = ConnectedAccount.objects.get(
            id=account_id, platform=Platform.INSTAGRAM
        )
    except ConnectedAccount.DoesNotExist:
        logger.warning("sync_instagram_account: account %s not found", account_id)
        return {"account_id": account_id, "status": "not_found"}

    if account.is_demo:
        logger.info("sync_instagram_account: skipping demo account %s", account_id)
        return {"account_id": account_id, "status": "skipped_demo"}

    if not account.access_token:
        logger.warning(
            "sync_instagram_account: no access_token for account %s — reconnect required",
            account_id,
        )
        return {"account_id": account_id, "status": "missing_token"}

    try:
        info = InstagramCollector.fetch_account_info(
            ig_user_id=account.external_id,
            page_token=account.access_token,
        )
        media = InstagramCollector.fetch_recent_media(
            ig_user_id=account.external_id,
            page_token=account.access_token,
            limit=media_limit,
        )
    except (InstagramNotConfigured, InstagramNoBusinessAccount) as e:
        logger.error("sync_instagram_account: %s", e)
        return {"account_id": account_id, "status": "error", "detail": str(e)}

    # Map Meta media_type → our PostType
    _POST_TYPE = {
        "IMAGE":           PostType.PHOTO,
        "VIDEO":           PostType.VIDEO,
        "CAROUSEL_ALBUM":  PostType.CAROUSEL,
        "REELS":           PostType.REEL,
    }

    with transaction.atomic():
        account.display_name = info.display_name or account.display_name
        account.avatar_url = info.avatar_url or account.avatar_url
        account.follower_count = info.follower_count
        account.save(update_fields=[
            "display_name", "avatar_url", "follower_count", "updated_at",
        ])

        created = 0
        updated = 0
        for m in media:
            denom = max(m.likes + m.comments_count, 1)
            _obj, is_new = Post.objects.update_or_create(
                account=account,
                external_id=m.external_id,
                defaults={
                    "post_type":       _POST_TYPE.get(m.media_type, PostType.PHOTO),
                    "caption":         m.caption,
                    "url":             m.url,
                    "published_at":    m.published_at,
                    "views":           0,   # needs insights scope; keep 0 for now
                    "likes":           m.likes,
                    "comments_count": m.comments_count,
                    "shares":          0,
                    "engagement_rate": (m.likes + m.comments_count) / denom,
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

    logger.info(
        "sync_instagram_account: %s (@%s) → +%d new / %d updated",
        account.id, account.handle, created, updated,
    )
    return {
        "account_id":     account_id,
        "status":         "ok",
        "handle":         account.handle,
        "created":        created,
        "updated":        updated,
        "follower_count": info.follower_count,
    }


@shared_task(
    queue="collectors",
    name="apps.collectors.tasks.sync_all_instagram_accounts",
)
def sync_all_instagram_accounts() -> dict:
    """Fan-out task: enqueue a sync for every real (non-demo) Instagram account."""
    ids = list(
        ConnectedAccount.objects.filter(
            platform=Platform.INSTAGRAM, is_demo=False
        ).exclude(access_token="").values_list("id", flat=True)
    )
    for aid in ids:
        sync_instagram_account.delay(aid)
    return {"enqueued": len(ids), "account_ids": ids}
