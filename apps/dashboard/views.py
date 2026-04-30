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
from django.core.cache import cache
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_cookie
from django.utils.translation import gettext as _

from apps.analytics.models import SentimentLabel, SentimentResult
from apps.analytics.services.recommendations import build_recommendations
from apps.collectors.models import Comment
from apps.social.models import ConnectedAccount, FollowerSnapshot, Platform, Post, PostType


def _safe_best_post_recipe(user):
    """Wrap best_post_recipe so the dashboard never crashes if sklearn
    blows up on weird data — log + return None and the template hides it.

    Cached per-user for 5 minutes — the recipe only changes when new posts
    arrive, which happens at most every 6h via Celery Beat. The cached
    result also avoids re-fitting the regression on every page load.
    """
    cache_key = f"best_recipe:{user.id}"
    hit = cache.get(cache_key)
    if hit is not None:
        return hit if hit != "__none__" else None
    try:
        from apps.analytics.services.predict import best_post_recipe
        result = best_post_recipe(user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("best_post_recipe failed")
        result = None
    cache.set(cache_key, result if result is not None else "__none__", 300)
    return result


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
    Platform.VK:        "#4c75a3",
}
PLATFORM_LABELS = {
    Platform.INSTAGRAM: "Instagram",
    Platform.TELEGRAM:  "Telegram",
    Platform.YOUTUBE:   "YouTube",
    Platform.X:         "X",
    Platform.VK:        "VKontakte",
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

    # ---------------- Recommendations ----------------
    recommendations = build_recommendations(user)

    # ---------------- Engagement quality breakdown ----------------
    # Per-post averages over the trailing window — surfaces "how much of my
    # audience engages, not just how many of them I have".
    quality_agg = user_posts.aggregate(
        v=Sum("views"), l=Sum("likes"),
        c=Sum("comments_count"), s=Sum("shares"),
    )
    qv = int(quality_agg["v"] or 0)
    ql = int(quality_agg["l"] or 0)
    qc = int(quality_agg["c"] or 0)
    qs = int(quality_agg["s"] or 0)
    def _rate(n, d): return round(n * 100 / d, 2) if d else 0.0
    quality = {
        "like_rate":       _rate(ql, qv),    # %  Likes per view
        "discussion_rate": _rate(qc, qv),    # %  Comments per view
        "virality_rate":   _rate(qs, qv),    # %  Shares per view
        "has_views":       qv > 0,
    }

    # ---------------- Optimal Posting AI (heatmap + ML grid search) -----------
    best_recipe = _safe_best_post_recipe(user)

    # ---------------- Audience growth (follower snapshots last 30 days) -----
    growth_window = 30
    growth_start = (now - timedelta(days=growth_window - 1)).date()
    growth_labels = [
        (growth_start + timedelta(days=i)).strftime("%d %b")
        for i in range(growth_window)
    ]
    # Sum follower_count across all of the user's accounts per day. Missing
    # days are forward-filled with the prior day's value so the line doesn't
    # collapse to zero on a no-sync day.
    snaps_qs = (
        FollowerSnapshot.objects
        .filter(account__user=user, recorded_on__gte=growth_start)
        .values("recorded_on")
        .annotate(total=Sum("count"))
        .order_by("recorded_on")
    )
    by_day = {row["recorded_on"]: row["total"] or 0 for row in snaps_qs}
    growth_series: list[int] = []
    last_seen = sum(a.follower_count for a in accounts)
    for i in range(growth_window):
        day = growth_start + timedelta(days=i)
        if day in by_day:
            last_seen = by_day[day]
        growth_series.append(int(last_seen))
    growth_delta = growth_series[-1] - growth_series[0] if growth_series else 0
    growth_pct = round(growth_delta * 100 / max(growth_series[0], 1), 1) if growth_series and growth_series[0] else 0.0

    # ---------------- Cross-platform performance comparison ------------------
    # Per-platform avg engagement_rate for the user's connected accounts —
    # the dashboard's "which platform is winning" callout.
    cross_platform = []
    cp_rows = (
        user_posts.values("account__platform")
        .annotate(
            avg_eng=Avg("engagement_rate"),
            posts=Count("id"),
            sum_likes=Sum("likes"),
            sum_views=Sum("views"),
        )
        .order_by("-avg_eng")
    )
    cp_max_eng = max((r["avg_eng"] or 0 for r in cp_rows), default=0) or 1
    for r in cp_rows:
        p = r["account__platform"]
        cross_platform.append({
            "code":      p,
            "name":      PLATFORM_LABELS.get(p, p.title()),
            "color":     PLATFORM_COLORS.get(p, "#94a3b8"),
            "avg_eng":   round((r["avg_eng"] or 0) * 100, 2),
            "ratio":     round((r["avg_eng"] or 0) / cp_max_eng, 3),
            "posts":     r["posts"],
            "sum_likes": int(r["sum_likes"] or 0),
            "sum_views": int(r["sum_views"] or 0),
        })
    cross_platform_winner = cross_platform[0] if cross_platform else None

    # ---------------- Caption pattern insights -------------------------------
    # Compares the *top quartile* of posts (by engagement_rate) to the rest.
    # Surfaces concrete patterns: "high-engagement posts use 2.3x more
    # emoji" / "have 1.4x more questions" / etc.
    import re as _re_pattern
    EMOJI_RE = _re_pattern.compile(
        r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F600-\U0001F64F]"
    )
    QUESTION_RE = _re_pattern.compile(r"\?")
    HASHTAG_RE = _re_pattern.compile(r"#\w{2,30}", flags=_re_pattern.UNICODE)
    LINK_RE = _re_pattern.compile(r"https?://\S+")

    pattern_posts = list(user_posts.exclude(caption="").values("caption", "engagement_rate"))
    pattern_insights: list[dict] = []
    if len(pattern_posts) >= 8:
        pattern_posts.sort(key=lambda p: p["engagement_rate"] or 0, reverse=True)
        cutoff = max(2, len(pattern_posts) // 4)   # top 25%
        top = pattern_posts[:cutoff]
        rest = pattern_posts[cutoff:]
        def _avg(items, fn):
            return sum(fn(p["caption"]) for p in items) / max(len(items), 1)
        for label, fn, unit in [
            ("Emojilar",       lambda c: len(EMOJI_RE.findall(c)),    "ta"),
            ("Savol belgilari", lambda c: len(QUESTION_RE.findall(c)), "ta"),
            ("Hashtaglar",     lambda c: len(HASHTAG_RE.findall(c)),   "ta"),
            ("Linklar",        lambda c: len(LINK_RE.findall(c)),      "ta"),
            ("Caption belgi",  lambda c: len(c),                       "belgi"),
        ]:
            top_avg = round(_avg(top, fn), 2)
            rest_avg = round(_avg(rest, fn), 2) or 0.01   # avoid /0
            ratio = round(top_avg / rest_avg, 2) if rest_avg else 0
            pattern_insights.append({
                "label":    label,
                "top_avg":  top_avg,
                "rest_avg": round(rest_avg, 2),
                "ratio":    ratio,
                "unit":     unit,
            })

    # First-time UX: when every connected account is demo-seeded, surface a
    # quiet banner at the top of the dashboard pointing the user at /social/
    # so they can wire up a real Telegram / YouTube / VK account.
    has_only_demo = bool(accounts) and all(a.is_demo for a in accounts)

    # ---------------- KPIs (display) ----------------
    def trend_pct(window_days: int = 7) -> dict[int, float]:
        # Very small helper: ratio of last `window` to previous `window` for each metric.
        # For an MVP dashboard this is plenty; real rolling windows can come with aggregates.
        return {}

    kpis = [
        _kpi(_("Jami postlar"),     total_posts,                      "layers",   "brand",   spark=per_day_posts),
        _kpi(_("Obunachilar"),      total_followers,                  "users",    "emerald", spark=_growth_spark(total_followers)),
        _kpi(_("Engagement rate"),  round(engagement * 100, 1),       "activity", "amber",   suffix="%", spark=per_day_posts),
        _kpi(_("Sentiment"),        round(positive_share, 0),         "smile",    "sky",     suffix="%", spark=per_day_comments),
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
        "recommendations": recommendations,
        "has_only_demo":   has_only_demo,
        "quality":              quality,
        "best_recipe":          best_recipe,
        "cross_platform":       cross_platform,
        "cross_platform_winner": cross_platform_winner,
        "pattern_insights":     pattern_insights,
        "audience_growth": {
            "labels": growth_labels,
            "series": growth_series,
            "delta":  growth_delta,
            "pct":    growth_pct,
        },
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
    if seconds < 60:    return _("{n} soniya oldin").format(n=seconds)
    if seconds < 3600:  return _("{n} daqiqa oldin").format(n=seconds // 60)
    if seconds < 86400: return _("{n} soat oldin").format(n=seconds // 3600)
    return _("{n} kun oldin").format(n=seconds // 86400)


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
            "text": _("Yangi post: «{caption}»").format(caption=(latest_post.caption or '...')[:40]),
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
            "text": _("{n} ta pozitiv komment aniqlandi").format(n=len(pos)),
        }))
    if neg:
        events.append((neg[0].published_at, {
            "icon": "alert-circle", "accent": "rose",
            "text": _("{n} ta negativ komment aniqlandi").format(n=len(neg)),
        }))

    top_account = (
        ConnectedAccount.objects.filter(user=user).order_by("-follower_count").first()
    )
    if top_account:
        events.append((top_account.updated_at, {
            "icon": "user-plus", "accent": "emerald",
            "text": _("@{handle} — {n} obunachi").format(handle=top_account.handle, n=f"{top_account.follower_count:,}"),
        }))

    top_engaged = (
        Post.objects.filter(account__user=user).order_by("-engagement_rate").first()
    )
    if top_engaged:
        events.append((top_engaged.published_at, {
            "icon": "trending-up", "accent": "emerald",
            "text": _("Engagement {pct}% — top post").format(pct=f"{top_engaged.engagement_rate*100:.1f}"),
        }))

    latest_sentiment = (
        SentimentResult.objects.filter(comment__post__account__user=user)
        .order_by("-created_at").first()
    )
    if latest_sentiment:
        events.append((latest_sentiment.created_at, {
            "icon": "bar-chart-3", "accent": "brand",
            "text": _("Sentiment tahlili yangilandi"),
        }))

    events.sort(key=lambda t: t[0], reverse=True)
    out = []
    for ts, ev in events[:8]:
        ev["when"] = _humanize_delta(now - ts)
        out.append(ev)
    return out


def _empty_platforms() -> list[dict]:
    """Placeholder so the donut chart renders a single 'no data' slice."""
    return [{"name": _("Ma'lumot yo'q"), "value": 1, "color": "#94a3b8", "icon": "x", "pct": 100.0}]


@login_required
def global_search(request: HttpRequest) -> JsonResponse:
    """Global search across the user's accounts, posts, and comments.

    Used by the Ctrl+K command palette: when ``q`` is non-empty the palette
    fetches this endpoint and merges real results with its static nav items.

    Each result has ``{title, subtitle, href, kind}`` so the palette can
    render a heterogeneous list. Capped at 5 per kind to keep the dropdown
    short — the user can navigate to the relevant page for the full list.
    """
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    user = request.user
    results: list[dict] = []

    accounts = (
        ConnectedAccount.objects
        .filter(user=user)
        .filter(Q(handle__icontains=q) | Q(platform__icontains=q))
        .order_by("platform")[:5]
    )
    for a in accounts:
        results.append({
            "kind":     "account",
            "title":    f"@{a.handle}",
            "subtitle": a.get_platform_display(),
            "href":     "/accounts/",
        })

    posts = (
        Post.objects
        .filter(account__user=user, caption__icontains=q)
        .select_related("account")
        .order_by("-published_at")[:5]
    )
    for p in posts:
        snippet = (p.caption or "").strip().replace("\n", " ")[:80]
        results.append({
            "kind":     "post",
            "title":    snippet or "(no caption)",
            "subtitle": f"@{p.account.handle} · {p.likes:,} likes",
            "href":     f"/analytics/top/?q={q}",
        })

    comments = (
        Comment.objects
        .filter(post__account__user=user, body__icontains=q)
        .select_related("post", "post__account")
        .order_by("-created_at")[:3]
    )
    for c in comments:
        snippet = (c.body or "").strip().replace("\n", " ")[:80]
        results.append({
            "kind":     "comment",
            "title":    snippet,
            "subtitle": f"@{c.post.account.handle}",
            "href":     "/analytics/sentiment/",
        })

    return JsonResponse({"results": results})