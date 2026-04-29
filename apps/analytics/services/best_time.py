"""Best-time-to-post analysis.

Aggregates the user's posts into a 7×24 grid (weekday × hour) where the
cell value is the average engagement_rate of posts published in that
slot. The result is consumed by ``apps.analytics.views.best_time_page``
which renders a heatmap.

Why a service: keeps the SQL aggregation testable in isolation and lets
us reuse the same numbers from a future API endpoint or AI prompt.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Avg, Count
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay
from django.utils import timezone

from apps.social.models import Post


WEEKDAYS_UZ = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass(frozen=True)
class HeatmapCell:
    weekday: int       # 1..7 (Mon=1, Sun=7) — matches ExtractIsoWeekDay
    hour:    int       # 0..23
    posts:   int
    avg_engagement: float  # in 0..1; multiply by 100 for percent


@dataclass(frozen=True)
class TopSlot:
    weekday: int
    hour:    int
    avg_engagement: float
    posts:   int


def compute_heatmap(user, *, days: int = 90) -> tuple[list[HeatmapCell], list[TopSlot]]:
    """Return (all 7×24 cells, top 3 slots) for ``user`` over the past ``days``.

    Cells with zero posts are still included with engagement 0 so the
    front-end can render a full grid; ``posts == 0`` lets the template
    show those as faded.
    """
    window_start = timezone.now() - timedelta(days=days)

    qs = (
        Post.objects
        .filter(account__user=user, published_at__gte=window_start)
        .annotate(
            wd=ExtractIsoWeekDay("published_at"),
            hr=ExtractHour("published_at"),
        )
        .values("wd", "hr")
        .annotate(
            posts=Count("id"),
            avg_eng=Avg("engagement_rate"),
        )
    )
    by_key = {(row["wd"], row["hr"]): row for row in qs}

    cells: list[HeatmapCell] = []
    for wd in range(1, 8):
        for hr in range(24):
            row = by_key.get((wd, hr))
            cells.append(HeatmapCell(
                weekday=wd,
                hour=hr,
                posts=row["posts"] if row else 0,
                avg_engagement=float(row["avg_eng"] or 0) if row else 0.0,
            ))

    # Top 3 slots by avg engagement, but only those with at least 2 posts —
    # 1-post averages are too noisy to recommend.
    candidates = [c for c in cells if c.posts >= 2]
    candidates.sort(key=lambda c: c.avg_engagement, reverse=True)
    top = [
        TopSlot(weekday=c.weekday, hour=c.hour,
                avg_engagement=c.avg_engagement, posts=c.posts)
        for c in candidates[:3]
    ]
    return cells, top


def weekday_label(wd: int, lang: str = "uz") -> str:
    """Map ISO weekday (1=Mon..7=Sun) to a 2-3 char label."""
    if 1 <= wd <= 7:
        return (WEEKDAYS_UZ if lang == "uz" else WEEKDAYS_EN)[wd - 1]
    return str(wd)
