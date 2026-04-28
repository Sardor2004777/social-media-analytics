"""Analytics + Sentiment dashboard pages.

Everything reads directly from the real DB. No Faker. Empty states are used
when the user has no ConnectedAccount rows yet.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDay
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.collectors.models import Comment
from apps.core.ratelimit import rate_limit
from apps.social.models import ConnectedAccount, Platform, Post, PostType

from .models import SentimentLabel, SentimentResult
from .services.chat import ChatNotConfigured, ask as chat_ask, is_configured as chat_is_configured
from .services.wordcloud import WordcloudEntry, top_words

logger = logging.getLogger(__name__)


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

    # ---------------- Best-time heatmap: 7 weekdays × 24 hours ----------------
    # Average engagement rate per (weekday, hour) bucket. Empty cells render
    # at 0; the template colour-scales each cell against the matrix max.
    heatmap = [[0.0] * 24 for _ in range(7)]
    counts  = [[0] * 24 for _ in range(7)]
    for p in (
        Post.objects.filter(account__user=user, published_at__gte=start)
        .values("published_at", "engagement_rate")
    ):
        ts = p["published_at"]
        wd = ts.weekday()
        hr = ts.hour
        heatmap[wd][hr] += p["engagement_rate"] or 0
        counts[wd][hr] += 1
    for wd in range(7):
        for hr in range(24):
            if counts[wd][hr]:
                heatmap[wd][hr] = round(heatmap[wd][hr] / counts[wd][hr] * 100, 2)
    heatmap_max = max((max(row) for row in heatmap), default=0)
    # Best (weekday, hour) over the window — featured under the grid.
    best_wd, best_hr, best_val = 0, 0, 0.0
    for wd in range(7):
        for hr in range(24):
            if heatmap[wd][hr] > best_val:
                best_wd, best_hr, best_val = wd, hr, heatmap[wd][hr]
    weekday_names = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    weekday_full = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba",
                    "Juma", "Shanba", "Yakshanba"]

    # ---------------- Top topics + hashtags from post captions ----------------
    import re as _re
    captions = list(
        Post.objects.filter(account__user=user)
        .exclude(caption="")
        .values_list("caption", flat=True)[:1000]
    )
    top_topics_entries = top_words(captions, n=30)
    hashtag_re = _re.compile(r"#(\w{2,30})", flags=_re.UNICODE)
    hashtag_counter: Counter = Counter()
    for cap in captions:
        for tag in hashtag_re.findall(cap):
            hashtag_counter[tag.lower()] += 1
    top_hashtags = [
        {"tag": t, "count": c}
        for t, c in hashtag_counter.most_common(15)
    ]
    # ---------------- Post-length buckets — engagement vs caption length -----
    # Buckets are inclusive lower / exclusive upper. The last bucket catches
    # everything 401+ chars so a single 5000-char essay doesn't blow the chart.
    LENGTH_BUCKETS = [
        ("0–80",    0,    80),
        ("80–150",  80,   150),
        ("150–300", 150,  300),
        ("300–500", 300,  500),
        ("500+",    500,  10**9),
    ]
    bucket_stats = []
    for label, lo, hi in LENGTH_BUCKETS:
        bucket_qs = Post.objects.filter(
            account__user=user, published_at__gte=start,
        ).extra(  # noqa: S610  small fixed expression, no user input
            where=["LENGTH(caption) >= %s AND LENGTH(caption) < %s"],
            params=[lo, hi],
        )
        cnt = bucket_qs.count()
        if cnt == 0:
            bucket_stats.append({
                "label": label, "count": 0, "avg_engagement": 0,
                "avg_likes": 0, "avg_views": 0,
            })
            continue
        agg = bucket_qs.aggregate(
            avg_eng=Avg("engagement_rate"),
            avg_lk=Avg("likes"),
            avg_vw=Avg("views"),
        )
        bucket_stats.append({
            "label":          label,
            "count":          cnt,
            "avg_engagement": round((agg["avg_eng"] or 0) * 100, 2),
            "avg_likes":      int(agg["avg_lk"] or 0),
            "avg_views":      int(agg["avg_vw"] or 0),
        })
    # Best bucket by avg engagement (skipping empty ones).
    best_bucket = max(
        (b for b in bucket_stats if b["count"] > 0),
        key=lambda b: b["avg_engagement"],
        default=None,
    )

    # ---------------- Engagement funnel: views → likes → comments → shares ---
    funnel_agg = posts_qs.aggregate(
        v=Sum("views"),
        l=Sum("likes"),
        c=Sum("comments_count"),
        s=Sum("shares"),
    )
    funnel_v = int(funnel_agg["v"] or 0)
    funnel_l = int(funnel_agg["l"] or 0)
    funnel_c = int(funnel_agg["c"] or 0)
    funnel_s = int(funnel_agg["s"] or 0)
    # Each step's % is relative to views (the top of the funnel). When we have
    # no views yet (groups, low-data accounts) the funnel collapses gracefully
    # to zeros — template hides the block in that case.
    def _pct(num, denom):
        return round(num * 100 / denom, 2) if denom else 0
    funnel_steps = [
        {"label": "Ko'rishlar", "value": funnel_v, "pct": 100,                       "color": "from-sky-500 to-blue-600"},
        {"label": "Likes",      "value": funnel_l, "pct": _pct(funnel_l, funnel_v),  "color": "from-emerald-500 to-teal-500"},
        {"label": "Kommentlar", "value": funnel_c, "pct": _pct(funnel_c, funnel_v),  "color": "from-amber-500 to-orange-500"},
        {"label": "Repostlar",  "value": funnel_s, "pct": _pct(funnel_s, funnel_v),  "color": "from-rose-500 to-pink-500"},
    ]

    # Engagement comparison — current 30 days vs prior 30 days.
    prior_start = start - timedelta(days=window_days)
    prior_qs = Post.objects.filter(
        account__user=user,
        published_at__gte=prior_start,
        published_at__lt=start,
    )
    cur_eng_avg   = posts_qs.aggregate(v=Avg("engagement_rate"))["v"] or 0
    prior_eng_avg = prior_qs.aggregate(v=Avg("engagement_rate"))["v"] or 0
    if prior_eng_avg:
        eng_delta_pct = round((cur_eng_avg - prior_eng_avg) * 100 / prior_eng_avg, 1)
    else:
        eng_delta_pct = 0.0
    cur_post_count   = posts_qs.count()
    prior_post_count = prior_qs.count()
    if prior_post_count:
        post_delta_pct = round((cur_post_count - prior_post_count) * 100 / prior_post_count, 1)
    else:
        post_delta_pct = 0.0
    # Pre-zip rows so the template doesn't need awkward index gymnastics.
    # Each row is {"name": "Du", "cells": [{"hour": 0, "value": 1.2, "ratio": 0.4}, …]}.
    safe_max = heatmap_max or 1
    heatmap_rows = []
    for wd in range(7):
        cells = []
        for hr in range(24):
            v = heatmap[wd][hr]
            cells.append({
                "hour": hr,
                "value": v,
                "ratio": round(v / safe_max, 3) if v else 0,
            })
        heatmap_rows.append({"name": weekday_names[wd], "cells": cells})

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
        "heatmap_rows": heatmap_rows,
        "heatmap_max": heatmap_max,
        "best_time": {
            "weekday": weekday_full[best_wd] if best_val else "",
            "hour": best_hr,
            "engagement": best_val,
        },
        "top_topics":   top_topics_entries,
        "top_hashtags": top_hashtags,
        "length_buckets": bucket_stats,
        "best_length":    best_bucket,
        "funnel_steps":   funnel_steps,
        "comparison": {
            "post_delta_pct":     post_delta_pct,
            "engagement_delta_pct": eng_delta_pct,
            "engagement_now":     round(cur_eng_avg * 100, 2),
            "engagement_prior":   round(prior_eng_avg * 100, 2),
        },
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

    # Sentiment timeline — last 30 days, stacked counts by label.
    now = timezone.now()
    days = 30
    start = now - timedelta(days=days - 1)
    pos_series = [0] * days
    neu_series = [0] * days
    neg_series = [0] * days
    for row in results_qs.filter(comment__published_at__gte=start).values(
        "comment__published_at", "label"
    ):
        idx = (row["comment__published_at"].date() - start.date()).days
        if 0 <= idx < days:
            if row["label"] == SentimentLabel.POSITIVE:
                pos_series[idx] += 1
            elif row["label"] == SentimentLabel.NEGATIVE:
                neg_series[idx] += 1
            else:
                neu_series[idx] += 1
    timeline_labels = [(start + timedelta(days=i)).strftime("%d %b") for i in range(days)]

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
        "timeline": {
            "labels":   timeline_labels,
            "positive": pos_series,
            "neutral":  neu_series,
            "negative": neg_series,
        },
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


TOP_POSTS_SORT_OPTIONS = {
    "likes":      ("-likes",           "Eng ko'p like"),
    "views":      ("-views",           "Eng ko'p ko'rilgan"),
    "comments":   ("-comments_count",  "Eng ko'p izoh"),
    "shares":     ("-shares",          "Eng ko'p ulashilgan"),
    "engagement": ("-engagement_rate", "Eng yuqori engagement"),
    "recent":     ("-published_at",    "Eng yangilari"),
}
TOP_POSTS_DAYS_OPTIONS = [7, 30, 90, 365, 0]  # 0 = all-time


@login_required
def analytics_top_posts(request: HttpRequest) -> HttpResponse:
    """Ranked list of posts with filter + sort controls."""
    user = request.user

    sort_key = request.GET.get("sort", "likes")
    if sort_key not in TOP_POSTS_SORT_OPTIONS:
        sort_key = "likes"
    order_field = TOP_POSTS_SORT_OPTIONS[sort_key][0]

    try:
        days = int(request.GET.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    if days not in TOP_POSTS_DAYS_OPTIONS:
        days = 30

    platform = request.GET.get("platform") or ""
    if platform not in dict(Platform.choices):
        platform = ""

    post_type = request.GET.get("type") or ""
    if post_type not in dict(PostType.choices):
        post_type = ""

    qs = Post.objects.filter(account__user=user).select_related("account")
    if days > 0:
        qs = qs.filter(published_at__gte=timezone.now() - timedelta(days=days))
    if platform:
        qs = qs.filter(account__platform=platform)
    if post_type:
        qs = qs.filter(post_type=post_type)
    qs = qs.order_by(order_field, "-published_at")

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))

    posts = [
        {
            "platform":       p.account.platform,
            "platform_label": PLATFORM_LABELS.get(p.account.platform, p.account.platform.title()),
            "color":          PLATFORM_COLORS.get(p.account.platform, "#94a3b8"),
            "handle":         p.account.handle,
            "caption":        (p.caption or "—")[:120],
            "type":           p.post_type,
            "likes":          p.likes,
            "views":          p.views,
            "comments":       p.comments_count,
            "shares":         p.shares,
            "engagement":     round(p.engagement_rate * 100, 2),
            "published_at":   p.published_at,
            "url":            p.url,
        }
        for p in page.object_list
    ]

    ctx: dict[str, Any] = {
        "active_nav":  "top_posts",
        "posts":       posts,
        "page":        page,
        "total":       paginator.count,
        "filters": {
            "sort":      sort_key,
            "days":      days,
            "platform":  platform,
            "post_type": post_type,
        },
        "sort_options":     [(k, v[1]) for k, v in TOP_POSTS_SORT_OPTIONS.items()],
        "days_options":     TOP_POSTS_DAYS_OPTIONS,
        "platform_options": Platform.choices,
        "type_options":     PostType.choices,
    }
    return render(request, "dashboard/top_posts.html", ctx)


@login_required
@rate_limit(key="chat", rate="20/h", scope="user", methods=("POST",))
@require_http_methods(["GET", "POST"])
def analytics_chat(request: HttpRequest) -> HttpResponse:
    """AI analytics chat — ask questions about your data via OpenAI.

    GET renders the chat panel (or a "not configured" notice if the API key
    is missing). POST takes ``question`` form data, builds a data summary,
    calls OpenAI, and returns JSON ``{answer, model, tokens}``.

    Per-user rate-limited to 20 requests / hour to bound OpenAI spend.
    """
    if request.method == "POST":
        question = (request.POST.get("question") or "").strip()
        if not question:
            return JsonResponse({"error": "Savol bo'sh bo'lmasligi kerak."}, status=400)
        if len(question) > 500:
            return JsonResponse({"error": "Savol 500 belgidan oshmasligi kerak."}, status=400)

        try:
            resp = chat_ask(request.user, question)
        except ChatNotConfigured as e:
            return JsonResponse({"error": str(e)}, status=503)
        except Exception as e:
            logger.exception("AI chat failed for user %s", request.user.id)
            return JsonResponse(
                {"error": "Texnik xato yuz berdi. Keyinroq urinib ko'ring."},
                status=500,
            )

        return JsonResponse({
            "answer": resp.answer,
            "model":  resp.model,
            "tokens": {"in": resp.tokens_in, "out": resp.tokens_out},
        })

    return render(request, "dashboard/chat.html", {
        "active_nav": "chat",
        "configured": chat_is_configured(),
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
