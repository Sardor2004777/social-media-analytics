"""Analytics + Sentiment dashboard pages.

Everything reads directly from the real DB. No Faker. Empty states are used
when the user has no ConnectedAccount rows yet.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDay
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.collectors.models import Comment
from apps.social.models import ConnectedAccount, Platform, Post

from .models import SentimentLabel, SentimentResult
from .services.wordcloud import WordcloudEntry, top_words


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


@login_required
def analytics_overview(request: HttpRequest) -> HttpResponse:
    """Longer-window analytics: 30-day trend + per-platform breakdown table."""
    user = request.user
    now = timezone.now()
    window_days = 30
    start = now - timedelta(days=window_days - 1)

    posts_qs = Post.objects.filter(account__user=user, published_at__gte=start)

    # Per-day trend series (30 points)
    buckets = defaultdict(lambda: {"posts": 0, "likes": 0, "views": 0})
    for p in posts_qs.values("published_at", "likes", "views"):
        day = p["published_at"].date()
        buckets[day]["posts"] += 1
        buckets[day]["likes"] += p["likes"]
        buckets[day]["views"] += p["views"]

    labels = []
    posts_series = []
    likes_series = []
    views_series = []
    for i in range(window_days):
        d = (start + timedelta(days=i)).date()
        labels.append(d.strftime("%d %b"))
        b = buckets.get(d, {"posts": 0, "likes": 0, "views": 0})
        posts_series.append(b["posts"])
        likes_series.append(b["likes"])
        views_series.append(b["views"])

    # Per-platform aggregates
    per_platform = (
        Post.objects.filter(account__user=user)
        .values("account__platform")
        .annotate(
            posts=Count("id"),
            total_likes=Sum("likes"),
            total_views=Sum("views"),
            total_comments=Sum("comments_count"),
            avg_eng=Avg("engagement_rate"),
        )
        .order_by("-posts")
    )
    platforms = []
    for row in per_platform:
        p = row["account__platform"]
        platforms.append({
            "code": p,
            "label": PLATFORM_LABELS.get(p, p.title()),
            "color": PLATFORM_COLORS.get(p, "#94a3b8"),
            "posts": row["posts"],
            "likes": row["total_likes"] or 0,
            "views": row["total_views"] or 0,
            "comments": row["total_comments"] or 0,
            "engagement": round((row["avg_eng"] or 0) * 100, 2),
        })

    # Top posts (all-time)
    top_posts = []
    for p in (
        Post.objects.filter(account__user=user)
        .select_related("account")
        .order_by("-likes")[:20]
    ):
        top_posts.append({
            "platform": p.account.platform,
            "caption": (p.caption or "—")[:80],
            "handle": p.account.handle,
            "likes": p.likes,
            "views": p.views,
            "comments": p.comments_count,
            "engagement": round(p.engagement_rate * 100, 2),
            "published_at": p.published_at,
        })

    ctx: dict[str, Any] = {
        "active_nav": "analytics",
        "trend": {
            "labels": labels,
            "posts":  posts_series,
            "likes":  likes_series,
            "views":  views_series,
        },
        "platforms": platforms,
        "top_posts": top_posts,
        "total_posts": posts_qs.count(),
        "total_views": sum(views_series),
        "total_likes": sum(likes_series),
    }
    return render(request, "dashboard/analytics.html", ctx)


@login_required
def sentiment_page(request: HttpRequest) -> HttpResponse:
    """Sentiment distribution + language breakdown + top examples."""
    user = request.user
    results_qs = SentimentResult.objects.filter(comment__post__account__user=user)

    # Global distribution
    dist_counts = Counter(results_qs.values_list("label", flat=True))
    total = sum(dist_counts.values()) or 1
    distribution = [
        {
            "label": SentimentLabel.POSITIVE, "count": dist_counts.get(SentimentLabel.POSITIVE, 0),
            "pct": round(dist_counts.get(SentimentLabel.POSITIVE, 0) * 100 / total, 1),
            "color": "#10b981", "emoji": "😊",
        },
        {
            "label": SentimentLabel.NEUTRAL, "count": dist_counts.get(SentimentLabel.NEUTRAL, 0),
            "pct": round(dist_counts.get(SentimentLabel.NEUTRAL, 0) * 100 / total, 1),
            "color": "#64748b", "emoji": "😐",
        },
        {
            "label": SentimentLabel.NEGATIVE, "count": dist_counts.get(SentimentLabel.NEGATIVE, 0),
            "pct": round(dist_counts.get(SentimentLabel.NEGATIVE, 0) * 100 / total, 1),
            "color": "#f43f5e", "emoji": "😠",
        },
    ]

    # By-language matrix
    by_lang_raw = Counter()
    for row in results_qs.values_list("comment__language", "label"):
        by_lang_raw[row] += 1
    languages = sorted({l for (l, _) in by_lang_raw.keys()})
    by_language = []
    for lang in languages:
        pos = by_lang_raw.get((lang, SentimentLabel.POSITIVE), 0)
        neu = by_lang_raw.get((lang, SentimentLabel.NEUTRAL), 0)
        neg = by_lang_raw.get((lang, SentimentLabel.NEGATIVE), 0)
        t = pos + neu + neg or 1
        by_language.append({
            "lang":     lang,
            "total":    pos + neu + neg,
            "positive": pos, "positive_pct": round(pos * 100 / t, 1),
            "neutral":  neu, "neutral_pct":  round(neu * 100 / t, 1),
            "negative": neg, "negative_pct": round(neg * 100 / t, 1),
        })

    # Top positive / negative comments (by sentiment score)
    top_pos = (
        results_qs.filter(label=SentimentLabel.POSITIVE)
        .select_related("comment", "comment__post__account")
        .order_by("-score")[:5]
    )
    top_neg = (
        results_qs.filter(label=SentimentLabel.NEGATIVE)
        .select_related("comment", "comment__post__account")
        .order_by("-score")[:5]
    )

    # Wordclouds — top tokens per sentiment label, pre-sized for the template.
    pos_bodies = results_qs.filter(
        label=SentimentLabel.POSITIVE
    ).values_list("comment__body", flat=True)
    neg_bodies = results_qs.filter(
        label=SentimentLabel.NEGATIVE
    ).values_list("comment__body", flat=True)

    ctx: dict[str, Any] = {
        "active_nav": "sentiment",
        "distribution": distribution,
        "by_language": by_language,
        "top_positive": [_serialize_comment(r) for r in top_pos],
        "top_negative": [_serialize_comment(r) for r in top_neg],
        "wordcloud_positive": [_cloud_entry(w) for w in top_words(pos_bodies)],
        "wordcloud_negative": [_cloud_entry(w) for w in top_words(neg_bodies)],
        "total_analyzed": sum(dist_counts.values()),
        "model_used": results_qs.values_list("model_name", flat=True).first() or "—",
    }
    return render(request, "dashboard/sentiment.html", ctx)


@login_required
def analytics_compare(request: HttpRequest) -> HttpResponse:
    """Side-by-side comparison of 2–3 user-owned ConnectedAccounts.

    Accounts come in via ``?accounts=<id>&accounts=<id>`` query string. With
    fewer than 2 resolved accounts we render a checkbox selector; otherwise
    per-account KPIs + an overlay 30-day likes chart.
    """
    user = request.user
    now = timezone.now()

    raw_ids = request.GET.getlist("accounts")
    try:
        selected_ids = [int(x) for x in raw_ids][:3]
    except (ValueError, TypeError):
        selected_ids = []

    all_accounts = list(
        ConnectedAccount.objects.filter(user=user).order_by("platform", "handle")
    )
    accounts = [a for a in all_accounts if a.id in selected_ids]

    if len(accounts) < 2:
        return render(request, "dashboard/compare.html", {
            "active_nav": "compare",
            "state": "select",
            "all_accounts": all_accounts,
            "selected_ids": [a.id for a in accounts],
        })

    window_days = 30
    start = now - timedelta(days=window_days - 1)
    labels = [(start + timedelta(days=i)).strftime("%d %b") for i in range(window_days)]

    summaries: list[dict[str, Any]] = []
    series: list[dict[str, Any]] = []

    for acct in accounts:
        posts_qs = Post.objects.filter(account=acct)

        # 30-day daily likes series for the overlay chart
        buckets = [0] * window_days
        for p in posts_qs.filter(published_at__gte=start).values("published_at", "likes"):
            idx = (p["published_at"].date() - start.date()).days
            if 0 <= idx < window_days:
                buckets[idx] += p["likes"]

        agg = posts_qs.aggregate(
            total_likes=Sum("likes"),
            total_views=Sum("views"),
            total_comments=Sum("comments_count"),
            avg_eng=Avg("engagement_rate"),
        )

        sentiment_counts = Counter(
            SentimentResult.objects
            .filter(comment__post__account=acct)
            .values_list("label", flat=True)
        )
        sent_total = sum(sentiment_counts.values()) or 1
        top_post = posts_qs.order_by("-likes").first()

        summaries.append({
            "id":             acct.id,
            "handle":         acct.handle,
            "platform":       acct.platform,
            "platform_label": PLATFORM_LABELS.get(acct.platform, acct.platform.title()),
            "color":          PLATFORM_COLORS.get(acct.platform, "#94a3b8"),
            "followers":      acct.follower_count,
            "posts":          posts_qs.count(),
            "likes":          agg["total_likes"] or 0,
            "views":          agg["total_views"] or 0,
            "comments":       agg["total_comments"] or 0,
            "engagement":     round((agg["avg_eng"] or 0) * 100, 2),
            "pos_pct":        round(sentiment_counts.get(SentimentLabel.POSITIVE, 0) * 100 / sent_total, 1),
            "neg_pct":        round(sentiment_counts.get(SentimentLabel.NEGATIVE, 0) * 100 / sent_total, 1),
            "top_caption":    ((top_post.caption or "").strip()[:80]) if top_post else "",
        })

        series.append({
            "id":     acct.id,
            "handle": acct.handle,
            "color":  PLATFORM_COLORS.get(acct.platform, "#94a3b8"),
            "data":   buckets,
        })

    return render(request, "dashboard/compare.html", {
        "active_nav":   "compare",
        "state":        "compare",
        "all_accounts": all_accounts,
        "accounts":     summaries,
        "selected_ids": [a.id for a in accounts],
        "chart":        {"labels": labels, "series": series},
    })


def _serialize_comment(result: SentimentResult) -> dict[str, Any]:
    c = result.comment
    return {
        "body":     c.body,
        "author":   c.author_handle,
        "language": c.language,
        "platform": c.post.account.platform,
        "score":    round(result.score, 2),
        "label":    result.label,
        "when":     c.published_at,
    }


def _cloud_entry(w: WordcloudEntry) -> dict[str, Any]:
    """Render a :class:`WordcloudEntry` as a template-ready dict.

    ``font_em`` maps the 0.15..1.0 weight onto a 1.0em..2.2em range so the
    template can drop it straight into ``style="font-size:"``.
    """
    return {
        "text":    w.text,
        "count":   w.count,
        "weight":  w.weight,
        "font_em": round(0.8 + w.weight * 1.4, 2),
    }
