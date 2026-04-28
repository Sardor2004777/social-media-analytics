"""Rule-based recommendation engine.

Walks the user's recent posts + sentiment + engagement and emits 3–5 short,
actionable insights. No LLM call — every recommendation is derived from a
deterministic rule against the database, so the dashboard can render it
inline without burning OpenAI tokens for every page-load.

Each :class:`Recommendation` is a small structured record the template can
render with an icon + accent colour + headline + sub-text, similar to the
existing "Tadbirlar" timeline.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from apps.analytics.models import SentimentLabel, SentimentResult
from apps.collectors.models import Comment
from apps.social.models import ConnectedAccount, Platform, Post, PostType


@dataclass
class Recommendation:
    """One insight card on the dashboard."""
    headline: str        # 1-line title (Uzbek)
    body: str            # 1-line explanation
    icon: str            # lucide-style icon name used by template SVG switch
    accent: str          # tailwind accent: brand | emerald | amber | rose | sky


_DAY_NAMES = [
    "Dushanba", "Seshanba", "Chorshanba", "Payshanba",
    "Juma", "Shanba", "Yakshanba",
]
_POST_TYPE_LABELS = {
    PostType.PHOTO:        "rasm postlar",
    PostType.VIDEO:        "video postlar",
    PostType.REEL:         "reels",
    PostType.CAROUSEL:     "karusellar",
    PostType.TWEET:        "tweetlar",
    PostType.CHANNEL_POST: "matnli postlar",
}


def build_recommendations(user) -> list[Recommendation]:
    """Return up to 5 recommendations sorted by likely impact.

    The order is deliberate: we always lead with the *positive* observation
    (best day / best content) so the card opens with something motivating,
    then surface gaps + warnings.
    """
    out: list[Recommendation] = []
    now = timezone.now()
    window = now - timedelta(days=30)

    posts = Post.objects.filter(account__user=user, published_at__gte=window)
    if not posts.exists():
        out.append(Recommendation(
            headline="Birinchi postlaringizni yuklang",
            body="Akkauntingizni ulagandan so'ng tahlil avtomatik boshlanadi.",
            icon="upload-cloud",
            accent="brand",
        ))
        return out

    # 1. Best day-of-week — average engagement_rate by weekday.
    day_eng: dict[int, list[float]] = defaultdict(list)
    for p in posts.values("published_at", "engagement_rate"):
        day_eng[p["published_at"].weekday()].append(p["engagement_rate"] or 0)
    if day_eng:
        best_day, vals = max(day_eng.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
        avg = sum(vals) / len(vals)
        if avg > 0:
            out.append(Recommendation(
                headline=f"{_DAY_NAMES[best_day]} kunlari eng samarali",
                body=f"O'sha kunlardagi postlaringizning o'rtacha engagement'i — {avg*100:.1f}%. "
                     f"Asosiy postlaringizni shu kunda chiqaring.",
                icon="trending-up",
                accent="emerald",
            ))

    # 2. Best post type — by total likes/views ratio.
    type_score: Counter = Counter()
    type_count: Counter = Counter()
    for p in posts.values("post_type", "likes", "views"):
        score = (p["likes"] or 0) + 0.1 * (p["views"] or 0)
        type_score[p["post_type"]] += score
        type_count[p["post_type"]] += 1
    if type_score:
        best_type = max(type_score, key=type_score.get)
        label = _POST_TYPE_LABELS.get(best_type, str(best_type))
        if type_count[best_type] >= 3:
            out.append(Recommendation(
                headline=f"{label.capitalize()} eng yaxshi natija beryapti",
                body=f"So'nggi 30 kunda {type_count[best_type]} ta {label} eng "
                     f"ko'p o'qildi va layk to'pladi. Ko'proq shu turdagi kontent yarating.",
                icon="layers",
                accent="brand",
            ))

    # 3. Sentiment trend — compare last 7 vs prior 7 days.
    last_7  = SentimentResult.objects.filter(
        comment__post__account__user=user,
        created_at__gte=now - timedelta(days=7),
    )
    prior_7 = SentimentResult.objects.filter(
        comment__post__account__user=user,
        created_at__gte=now - timedelta(days=14),
        created_at__lt=now - timedelta(days=7),
    )
    def neg_share(qs):
        c = Counter(qs.values_list("label", flat=True))
        total = sum(c.values()) or 1
        return c.get(SentimentLabel.NEGATIVE, 0) / total
    if last_7.exists() and prior_7.exists():
        a, b = neg_share(last_7), neg_share(prior_7)
        if a > b + 0.05 and a > 0.15:
            out.append(Recommendation(
                headline="Negativ kommentlar ko'paymoqda",
                body=f"O'tgan haftaga nisbatan negativ ulush {(a-b)*100:.0f}% oshdi "
                     f"(hozir {a*100:.0f}%). Yaqin kunlardagi postlar va kommentlarni ko'rib chiqing.",
                icon="alert-circle",
                accent="rose",
            ))
        elif a < b - 0.05 and a < 0.15:
            out.append(Recommendation(
                headline="Auditoriya kayfiyati yaxshilandi",
                body=f"Negativ kommentlar ulushi {(b-a)*100:.0f}% kamaydi — "
                     f"hozir atigi {a*100:.0f}%. Davom eting!",
                icon="smile",
                accent="emerald",
            ))

    # 4a. Posting consistency score — std-dev of gap intervals over last 30 days.
    # Low std-dev = regular cadence (good), high = bursts + droughts (bad).
    # Score: 100 = perfect daily consistency, 0 = random bursts.
    timestamps = sorted(posts.values_list("published_at", flat=True))
    if len(timestamps) >= 4:
        gaps_hours = [
            (timestamps[i+1] - timestamps[i]).total_seconds() / 3600
            for i in range(len(timestamps) - 1)
        ]
        avg_gap = sum(gaps_hours) / len(gaps_hours)
        if avg_gap > 0:
            variance = sum((g - avg_gap) ** 2 for g in gaps_hours) / len(gaps_hours)
            std = variance ** 0.5
            cv = std / avg_gap                # coefficient of variation
            consistency_score = max(0, min(100, int(100 * (1 - min(cv, 1)))))
            if consistency_score < 50:
                out.append(Recommendation(
                    headline=f"Postlar tartibi past ({consistency_score}/100)",
                    body="Auditoriya doimiy ritm bilan to'planadi. Postlarni teng intervalga "
                         "tushiring — har 2-3 kunda yoki haftada bir xil kunlarda.",
                    icon="calendar",
                    accent="amber",
                ))
            elif consistency_score >= 80:
                out.append(Recommendation(
                    headline=f"Tartib mukammal ({consistency_score}/100)",
                    body="Postlaringiz teng intervalda chiqyapti — auditoriya kutgan vaqtda "
                         "kontent oladi. Davom eting.",
                    icon="award",
                    accent="emerald",
                ))

    # 4. Posting cadence — gaps in the last 14 days.
    last_14 = posts.filter(published_at__gte=now - timedelta(days=14))
    last_14_count = last_14.count()
    if last_14_count == 0:
        out.append(Recommendation(
            headline="Oxirgi 2 haftada post yo'q",
            body="Faolligingizni qaytarish uchun haftada kamida 2 ta post chiqaring "
                 "— auditoriya engagement'i tezda pasayadi.",
            icon="calendar",
            accent="amber",
        ))
    elif last_14_count < 3:
        out.append(Recommendation(
            headline="Post chastotasini oshiring",
            body=f"Oxirgi 14 kunda {last_14_count} ta post bor. "
                 f"Haftada 3-4 ta post auditoriyani faol ushlab turadi.",
            icon="calendar",
            accent="amber",
        ))

    # 5. Top engagement post — show what worked best as a model to repeat.
    top = posts.order_by("-engagement_rate").first()
    if top and top.engagement_rate and top.engagement_rate > 0:
        snippet = (top.caption or "").strip().replace("\n", " ")
        if not snippet:
            snippet = top.url
        snippet = snippet[:80] + ("…" if len(snippet) > 80 else "")
        out.append(Recommendation(
            headline=f"Engagement {top.engagement_rate*100:.1f}% — top post",
            body=f"«{snippet}» — shu post sizning eng samarali ishingiz. "
                 f"Mavzu va formatini takrorlashga harakat qiling.",
            icon="award",
            accent="sky",
        ))

    return out[:5]
