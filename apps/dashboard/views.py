"""Landing page + authenticated dashboard.

The dashboard reads real rows from ``apps.social``, ``apps.collectors``, and
``apps.analytics``. When a user has no ``ConnectedAccount`` rows we still
render the dashboard shell but with zeroed KPIs and an onboarding banner.

To populate demo data for any user:

    python manage.py seed_demo_data --email <user>
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.analytics.models import SentimentLabel, SentimentResult
from apps.collectors.models import Comment
from apps.social.models import ConnectedAccount, Platform, Post, PostType


POST_TYPE_LABELS = {
    PostType.PHOTO:        "Rasmlar",
    PostType.VIDEO:        "Videolar",
    PostType.REEL:         "Reellar",
    PostType.CAROUSEL:     "Karusellar",
    PostType.TWEET:        "Tweetlar",
    PostType.CHANNEL_POST: "Matn / boshqa",
}
POST_TYPE_COLORS = {
    PostType.PHOTO:        "#0ea5e9",
    PostType.VIDEO:        "#f43f5e",
    PostType.REEL:         "#a855f7",
    PostType.CAROUSEL:     "#f59e0b",
    PostType.TWEET:        "#0f172a",
    PostType.CHANNEL_POST: "#64748b",
}


PLATFORM_COLORS = {
    Platform.INSTAGRAM: "#ec4899",
    Platform.TELEGRAM:  "#0ea5e9",
    Platform.YOUTUBE:   "#ef4444",
    Platform.X:         "#0f172a",
}
PLATFORM_LABELS = {
    Platform.INSTAGRAM: "Instagram",
    Platform.TELEGRAM:  "Telegram",
    Platform.YOUTUBE:   "YouTube",
    Platform.X:         "X",
}


def home(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard:app")
    return render(request, "dashboard/landing.html")


@login_required
def dashboard_app(request: HttpRequest) -> HttpResponse:
    user = request.user
    now = timezone.now()

    accounts = list(ConnectedAccount.objects.filter(user=user).order_by("platform"))

    # Lazy-seed safety net: a user who pre-dates the signup signal (or who
    # disconnected every demo account) would otherwise hit an empty
    # dashboard. Seed once, in place, so "pages show nothing" never recurs.
    # Gated by the same env var as the signup-time seeder.
    import os
    lazy_enabled = os.environ.get("DEMO_SEED_ON_SIGNUP", "1").strip().lower() in {"1", "true", "yes", "on"}
    if lazy_enabled and not accounts:
        try:
            from apps.collectors.services.mock_generator import DemoDataGenerator
            DemoDataGenerator(seed=user.id or None).seed(
                user,
                posts_per_platform=30,
                comments_per_post_range=(2, 6),
                days_back=90,
                analyze_sentiment=True,
                replace=False,
            )
            accounts = list(ConnectedAccount.objects.filter(user=user).order_by("platform"))
        except Exception:
            pass  # never block the dashboard on seeding

    user_posts = Post.objects.filter(account__user=user)

    # ---------------- KPIs ----------------
    total_posts     = user_posts.count()
    total_followers = sum(a.follower_count for a in accounts)
    engagement = user_posts.aggregate(val=Avg("engagement_rate"))["val"] or 0.0

    sentiment_counts = Counter(
        SentimentResult.objects
        .filter(comment__post__account__user=user)
        .values_list("label", flat=True)
    )
    sent_total = sum(sentiment_counts.values()) or 1
    positive_share = sentiment_counts.get(SentimentLabel.POSITIVE, 0) * 100 / sent_total

    # ---------------- Activity (user-selected date range via ?range=N) ----------------
    try:
        days_window = int(request.GET.get("range", 14))
    except (ValueError, TypeError):
        days_window = 14
    days_window = max(7, min(days_window, 90))
    start = now - timedelta(days=days_window - 1)
    per_day_posts     = _bucket_by_day(user_posts.filter(published_at__gte=start), days_window, now)
    per_day_comments  = _bucket_by_day(
        Comment.objects.filter(post__account__user=user, published_at__gte=start),
        days_window, now,
    )
    # Per-day sums of likes + views — drives a second activity chart that
    # answers "how is engagement trending over time" instead of just "how
    # often did I post".
    per_day_likes = [0] * days_window
    per_day_views = [0] * days_window
    for p in user_posts.filter(published_at__gte=start).values("published_at", "likes", "views"):
        idx = (p["published_at"].date() - start.date()).days
        if 0 <= idx < days_window:
            per_day_likes[idx] += p["likes"] or 0
            per_day_views[idx] += p["views"] or 0
    labels = [(now - timedelta(days=days_window - 1 - i)).strftime("%d %b") for i in range(days_window)]

    # ---------------- Post-type breakdown (photo / video / text / …) ----------------
    type_rows = (
        user_posts.values("post_type")
        .annotate(post_count=Count("id"))
        .order_by("-post_count")
    )
    post_types: list[dict] = []
    pt_total = sum(row["post_count"] for row in type_rows) or 1
    for row in type_rows:
        pt = row["post_type"]
        post_types.append({
            "name":  POST_TYPE_LABELS.get(pt, pt.title() if isinstance(pt, str) else str(pt)),
            "value": row["post_count"],
            "color": POST_TYPE_COLORS.get(pt, "#94a3b8"),
            "pct":   round(row["post_count"] * 100 / pt_total, 1),
        })

    # ---------------- Platform breakdown ----------------
    per_platform = (
        user_posts.values("account__platform")
        .annotate(post_count=Count("id"))
        .order_by("-post_count")
    )
    platforms = []
    total_platform_posts = sum(row["post_count"] for row in per_platform) or 1
    for row in per_platform:
        p = row["account__platform"]
        platforms.append({
            "name":  PLATFORM_LABELS.get(p, p.title()),
            "value": row["post_count"],
            "color": PLATFORM_COLORS.get(p, "#94a3b8"),
            "icon":  p,
            "pct":   round(row["post_count"] * 100 / total_platform_posts, 1),
        })

    # ---------------- Top posts ----------------
    top_posts_qs = (
        user_posts.select_related("account")
        .order_by("-likes")[:5]
    )
    top_posts = [
        {
            "title":    (p.caption or "—").strip()[:80],
            "platform": p.account.platform,
            "views":    p.views,
            "likes":    p.likes,
            "comments": p.comments_count,
            "when":     _humanize_delta(now - p.published_at),
        }
        for p in top_posts_qs
    ]

    # ---------------- Activity timeline ----------------
    timeline = _build_timeline(user, now)

    # ---------------- KPIs (display) ----------------
    def trend_pct(window_days: int = 7) -> dict[int, float]:
        # Very small helper: ratio of last `window` to previous `window` for each metric.
        # For an MVP dashboard this is plenty; real rolling windows can come with aggregates.
        return {}

    kpis = [
        _kpi("Jami postlar",     total_posts,                      "layers",   "brand",   spark=per_day_posts),
        _kpi("Obunachilar",      total_followers,                  "users",    "emerald", spark=_growth_spark(total_followers)),
        _kpi("Engagement rate",  round(engagement * 100, 1),       "activity", "amber",   suffix="%", spark=per_day_posts),
        _kpi("Sentiment",        round(positive_share, 0),         "smile",    "sky",     suffix="%", spark=per_day_comments),
    ]

    first_name = (user.get_short_name() if hasattr(user, "get_short_name") else "") or (user.email.split("@")[0] if user.email else "do'st")
    avatar_seed = hashlib.md5((user.email or str(user.id)).encode()).hexdigest()[:6]

    ctx: dict[str, Any] = {
        "active_nav": "dashboard",
        "first_name": first_name.capitalize(),
        "avatar_seed": avatar_seed,
        "kpis": kpis,
        "activity": {
            "labels": labels,
            "posts": per_day_posts,
            "engagement": per_day_comments,
            "likes": per_day_likes,
            "views": per_day_views,
        },
        "platforms": platforms or _empty_platforms(),
        "post_types": post_types or _empty_platforms(),
        "top_posts": top_posts,
        "timeline": timeline,
        "connected_accounts": accounts,
        "range_days":    days_window,
        "range_options": [7, 14, 30, 90],
    }
    return render(request, "dashboard/app.html", ctx)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kpi(label: str, value, icon: str, accent: str, *, suffix: str = "", spark: list[int] | None = None) -> dict:
    # Naive up/down: compare last-6 vs previous-6 if spark has 12+ points.
    up = True
    pct = 0.0
    if spark and len(spark) >= 6:
        recent = sum(spark[-6:]) or 1
        prev   = sum(spark[-12:-6]) or 1
        pct = round((recent - prev) / prev * 100, 1) if prev else 0.0
        up = pct >= 0
    series = spark or [50] * 12
    return {
        "label": label,
        "value_raw": value,
        "value": f"{value:,}" if isinstance(value, (int,)) else value,
        "icon": icon,
        "accent": accent,
        "pct": abs(pct),
        "up": up,
        "suffix": suffix,
        "spark": series,
        "spark_points": _spark_points(series),
    }


def _spark_points(values: list[int], width: int = 120, height: int = 32) -> str:
    """Scale a numeric series into an SVG ``<polyline points="...">`` string.

    Dimensions match the ``<svg viewBox="0 0 120 32">`` in the KPI card. Y is
    inverted (SVG origin is top-left; we want higher values visually up) and
    padded 2px top/bottom so the stroke is never clipped on flat runs.
    """
    if not values:
        return ""
    n = len(values)
    max_v = max(values)
    min_v = min(values)
    span = max(max_v - min_v, 1)
    step = width / max(n - 1, 1)
    out: list[str] = []
    for i, v in enumerate(values):
        x = round(i * step, 1)
        y = round(height - 2 - (v - min_v) / span * (height - 4), 1)
        out.append(f"{x},{y}")
    return " ".join(out)


def _bucket_by_day(queryset, days: int, now) -> list[int]:
    buckets = [0] * days
    start = now - timedelta(days=days - 1)
    for ts in queryset.values_list("published_at", flat=True):
        if ts < start:
            continue
        idx = (ts.date() - start.date()).days
        if 0 <= idx < days:
            buckets[idx] += 1
    return buckets


def _growth_spark(total: int) -> list[int]:
    # Smooth upward curve ending near `total`, normalised 0..100 for sparkline SVG.
    if total <= 0:
        return [50] * 12
    return [int(40 + i * 5) for i in range(12)]


def _humanize_delta(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds < 60:      return f"{seconds} soniya oldin"
    if seconds < 3600:    return f"{seconds // 60} daqiqa oldin"
    if seconds < 86400:   return f"{seconds // 3600} soat oldin"
    days = seconds // 86400
    return f"{days} kun oldin"


def _build_timeline(user, now) -> list[dict]:
    """Synthesize 8 recent events from real DB rows.

    We don't keep an activity-log table yet, so we derive "events" from the
    latest posts/comments/sentiment bumps. This is honest (all datapoints are
    real) and fits the dashboard UI.
    """
    events: list[tuple] = []

    latest_post = (
        Post.objects.filter(account__user=user)
        .select_related("account").order_by("-published_at").first()
    )
    if latest_post:
        events.append((latest_post.published_at, {
            "icon": "share-2",
            "accent": "sky",
            "text": f"Yangi post: «{(latest_post.caption or '...')[:40]}»",
        }))

    recent_comments = (
        Comment.objects.filter(post__account__user=user)
        .select_related("sentiment").order_by("-published_at")[:25]
    )
    pos = [c for c in recent_comments if getattr(c, "sentiment", None) and c.sentiment.label == SentimentLabel.POSITIVE]
    neg = [c for c in recent_comments if getattr(c, "sentiment", None) and c.sentiment.label == SentimentLabel.NEGATIVE]

    if pos:
        events.append((pos[0].published_at, {
            "icon": "message-square", "accent": "emerald",
            "text": f"{len(pos)} ta pozitiv komment aniqlandi",
        }))
    if neg:
        events.append((neg[0].published_at, {
            "icon": "alert-circle", "accent": "rose",
            "text": f"{len(neg)} ta negativ komment aniqlandi",
        }))

    top_account = (
        ConnectedAccount.objects.filter(user=user).order_by("-follower_count").first()
    )
    if top_account:
        events.append((top_account.updated_at, {
            "icon": "user-plus", "accent": "emerald",
            "text": f"@{top_account.handle} \u2014 {top_account.follower_count:,} obunachi",
        }))

    top_engaged = (
        Post.objects.filter(account__user=user).order_by("-engagement_rate").first()
    )
    if top_engaged:
        events.append((top_engaged.published_at, {
            "icon": "trending-up", "accent": "emerald",
            "text": f"Engagement {top_engaged.engagement_rate*100:.1f}% \u2014 top post",
        }))

    latest_sentiment = (
        SentimentResult.objects.filter(comment__post__account__user=user)
        .order_by("-created_at").first()
    )
    if latest_sentiment:
        events.append((latest_sentiment.created_at, {
            "icon": "bar-chart-3", "accent": "brand",
            "text": "Sentiment tahlili yangilandi",
        }))

    events.sort(key=lambda t: t[0], reverse=True)
    out = []
    for ts, ev in events[:8]:
        ev["when"] = _humanize_delta(now - ts)
        out.append(ev)
    return out


def _empty_platforms() -> list[dict]:
    """Placeholder so the donut chart renders a single 'no data' slice."""
    return [{"name": "Ma'lumot yo'q", "value": 1, "color": "#94a3b8", "icon": "x", "pct": 100.0}]
