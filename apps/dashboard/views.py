"""Landing page + authenticated user dashboard."""
from __future__ import annotations

import hashlib
import random
from datetime import timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone


def home(request: HttpRequest) -> HttpResponse:
    """Root URL handler.

    Authenticated users -> dashboard. Anonymous users -> landing page.
    """
    if request.user.is_authenticated:
        return redirect("dashboard:app")
    return render(request, "dashboard/landing.html")


@login_required
def dashboard_app(request: HttpRequest) -> HttpResponse:
    """Main authenticated dashboard with KPIs, charts, timeline.

    Uses per-user deterministic mock data until the collectors (Phase 5)
    and analytics (Phase 6) apps populate real metrics.
    """
    user_id = request.user.id or 0
    rng = random.Random(user_id * 1337 + 42)

    posts = rng.randint(120, 480)
    followers = rng.randint(1800, 12_400)
    engagement = round(rng.uniform(2.1, 7.8), 1)
    sentiment = rng.randint(62, 88)

    def trend(current: float, pct_min: float = -8.0, pct_max: float = 14.0) -> dict[str, Any]:
        pct = round(rng.uniform(pct_min, pct_max), 1)
        return {"value": current, "pct": pct, "up": pct >= 0}

    kpis = [
        {
            "label": "Jami postlar",
            "icon": "layers",
            "accent": "brand",
            **trend(posts),
            "suffix": "",
            "spark": [rng.randint(20, 100) for _ in range(12)],
        },
        {
            "label": "Obunachilar",
            "icon": "users",
            "accent": "emerald",
            **trend(followers),
            "suffix": "",
            "spark": [rng.randint(40, 100) for _ in range(12)],
        },
        {
            "label": "Engagement rate",
            "icon": "activity",
            "accent": "amber",
            **trend(engagement, -2.0, 3.5),
            "suffix": "%",
            "spark": [rng.randint(30, 90) for _ in range(12)],
        },
        {
            "label": "Sentiment",
            "icon": "smile",
            "accent": "sky",
            **trend(sentiment, -4.0, 6.0),
            "suffix": "%",
            "spark": [rng.randint(50, 95) for _ in range(12)],
        },
    ]

    today = timezone.now().date()
    activity_labels = [(today - timedelta(days=13 - i)).strftime("%d %b") for i in range(14)]
    activity_posts = [rng.randint(3, 22) for _ in range(14)]
    activity_engagement = [rng.randint(40, 240) for _ in range(14)]

    platform_breakdown = [
        {"name": "Instagram", "value": rng.randint(28, 42), "color": "#ec4899", "icon": "instagram"},
        {"name": "Telegram",  "value": rng.randint(18, 34), "color": "#0ea5e9", "icon": "send"},
        {"name": "YouTube",   "value": rng.randint(12, 24), "color": "#ef4444", "icon": "youtube"},
        {"name": "X",         "value": rng.randint(8, 18),  "color": "#0f172a", "icon": "x"},
    ]
    total = sum(p["value"] for p in platform_breakdown) or 1
    for p in platform_breakdown:
        p["pct"] = round(p["value"] * 100 / total, 1)

    sample_titles = [
        "Yangi post: bugungi ob-havo haqida",
        "Telegram kanal statistikasi yangilandi",
        "Instagram reel: 10K ko'rishga yetdi",
        "YouTube video yangi yuklandi",
        "Sentiment o'zgarishi sezildi",
        "Yangi obunachilar to'lqini",
        "Top kommentlar tahlili tayyor",
        "Haftalik hisobot generatsiya qilindi",
    ]
    top_posts = []
    for i in range(5):
        title = rng.choice(sample_titles)
        top_posts.append({
            "title": title,
            "platform": rng.choice(["instagram", "telegram", "youtube", "x"]),
            "views": rng.randint(320, 18_400),
            "likes": rng.randint(12, 1_240),
            "comments": rng.randint(4, 189),
            "when": f"{rng.randint(1, 23)} soat oldin",
        })

    actions = [
        ("user-plus",    "{n} ta yangi obunachi qo'shildi", "emerald"),
        ("message-square", "{n} ta yangi komment", "brand"),
        ("bar-chart-3",  "Hisobot avtomatik yaratildi", "amber"),
        ("trending-up",  "Engagement {n}% ga oshdi", "emerald"),
        ("alert-circle", "Negativ kommentlar aniqlandi", "rose"),
        ("share-2",      "Post reshare: {n} marta", "sky"),
    ]
    timeline = []
    for i in range(8):
        icon, template, accent = rng.choice(actions)
        timeline.append({
            "icon": icon,
            "text": template.format(n=rng.randint(3, 120)),
            "accent": accent,
            "when": f"{rng.randint(1, 59)} daqiqa oldin" if i < 3 else f"{rng.randint(1, 23)} soat oldin",
        })

    first_name = (request.user.get_short_name() if hasattr(request.user, "get_short_name") else "")
    if not first_name:
        first_name = request.user.email.split("@")[0] if request.user.email else "do'st"

    avatar_seed = hashlib.md5((request.user.email or str(user_id)).encode()).hexdigest()[:6]

    ctx: dict[str, Any] = {
        "first_name": first_name.capitalize(),
        "avatar_seed": avatar_seed,
        "kpis": kpis,
        "activity": {
            "labels": activity_labels,
            "posts": activity_posts,
            "engagement": activity_engagement,
        },
        "platforms": platform_breakdown,
        "top_posts": top_posts,
        "timeline": timeline,
        "connected_accounts": [],
    }
    return render(request, "dashboard/app.html", ctx)
