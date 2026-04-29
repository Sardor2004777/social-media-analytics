"""Hashtag analyzer.

Extracts ``#hashtag`` tokens from post captions and aggregates the
engagement they drive. Returns a sorted list of HashtagStat tuples for
the front-end table.

The regex is intentionally permissive — Cyrillic and Latin chars,
digits, underscore. Skips numeric-only tags (``#1``, ``#2025``) since
those are usually noise.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.social.models import Post


HASHTAG_RE = re.compile(r"#([\wÀ-￿]{2,40})", re.UNICODE)


@dataclass(frozen=True)
class HashtagStat:
    tag:           str
    posts:         int
    total_likes:   int
    total_views:   int
    avg_engagement: float  # 0..1; multiply by 100 for %


def extract_hashtags(text: str) -> list[str]:
    """Return lowercased hashtags found in ``text`` (no leading ``#``).

    Drops numeric-only tags. Deduplicates per-call so repeating ``#foo``
    twice in one caption only counts once.
    """
    if not text:
        return []
    found = {m.group(1).lower() for m in HASHTAG_RE.finditer(text)}
    return [t for t in found if not t.isdigit()]


def top_hashtags(user, *, days: int = 90, limit: int = 20) -> list[HashtagStat]:
    """Return the top-``limit`` hashtags by average engagement for ``user``.

    Only includes hashtags that appear in at least 2 posts — single-post
    averages are too noisy to recommend.
    """
    window_start = timezone.now() - timedelta(days=days)
    posts = (
        Post.objects
        .filter(account__user=user, published_at__gte=window_start)
        .values("caption", "likes", "views", "engagement_rate")
    )

    buckets: dict[str, dict] = defaultdict(
        lambda: {"posts": 0, "likes": 0, "views": 0, "eng_sum": 0.0}
    )
    for p in posts:
        for tag in extract_hashtags(p["caption"] or ""):
            b = buckets[tag]
            b["posts"]   += 1
            b["likes"]   += p["likes"] or 0
            b["views"]   += p["views"] or 0
            b["eng_sum"] += float(p["engagement_rate"] or 0)

    stats: list[HashtagStat] = []
    for tag, b in buckets.items():
        if b["posts"] < 2:
            continue
        stats.append(HashtagStat(
            tag=tag,
            posts=b["posts"],
            total_likes=b["likes"],
            total_views=b["views"],
            avg_engagement=b["eng_sum"] / b["posts"],
        ))
    stats.sort(key=lambda s: s.avg_engagement, reverse=True)
    return stats[:limit]
