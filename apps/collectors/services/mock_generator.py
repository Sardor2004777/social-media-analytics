"""Realistic demo-mode data generator.

Creates multi-platform ConnectedAccounts, Posts with temporal+engagement
distributions that look plausible in charts, and Comments in UZ/RU/EN with a
skewed sentiment mix (~60% positive, 25% neutral, 15% negative).

All generation is deterministic when you pass a ``seed`` — handy for tests
and reproducible demos.

The Sentiment classification pass is delegated to
``apps.analytics.services.sentiment.get_analyzer`` so the *real* classifier
runs over the demo comments; results land in ``SentimentResult`` and drive
the dashboard. This means even demo mode exercises the full ML path.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from apps.analytics.models import SentimentResult
from apps.analytics.services.sentiment import SentimentPrediction, get_analyzer
from apps.collectors.models import Comment, Language
from apps.social.models import ConnectedAccount, Platform, Post, PostType


# ---------------------------------------------------------------------------
# Content libraries (keeps generation realistic without shipping GB of data)
# ---------------------------------------------------------------------------

UZ_CAPTIONS = [
    "Bugungi kun haqida qisqacha mulohaza",
    "Ajoyib voqea — ko'rgan do'stlar fikrini yozing",
    "Yangi loyihamizni sizlarga taqdim etamiz",
    "Bu haftaning eng qiziqarli yangiliklari",
    "Odamlarni ilhomlantiradigan hikoya",
    "Uzbek ovqatlari — retsept ham bor",
    "Sayohat lavhalari Samarqanddan",
    "Kitob o'qish va shaxsiy rivojlanish haqida",
    "Bu video sizni kuldirishi mumkin",
    "Tabiat go'zalligi — hech qayerga ketmagan",
]
RU_CAPTIONS = [
    "Сегодняшний день прошёл насыщенно — делимся подробностями",
    "Новый пост о том, как всё начиналось",
    "Неожиданное открытие недели",
    "Путешествие по горам Узбекистана",
    "Короткая история из жизни",
    "Рецепт недели — готовим вместе",
    "Подборка лучших моментов прошлого месяца",
    "Обсуждаем тренды в социальных сетях",
    "Книжный клуб: что читать этим летом",
    "Фотография, которая всё изменила",
]
EN_CAPTIONS = [
    "Sharing a quick thought about today",
    "Reflections after an exhausting but rewarding week",
    "Behind the scenes of the latest project",
    "A short guide to getting started",
    "Loving this view — tag someone who needs to see it",
    "Things I learned this month",
    "Weekend vibes, simple and honest",
    "Here's what worked (and what didn't)",
    "A message for anyone feeling stuck right now",
    "Tried something new — results below",
]

UZ_COMMENTS_POS = [
    "Juda zo'r post!", "Rahmat, foydali bo'ldi", "Ajoyib fikrlar", "Davom eting!",
    "Qoyil! Chiroyli suratlar", "Yaxshi, judayam foydali",
    "Sevaman sizning ishlaringizni", "Mukammal chiqdi! 🔥",
]
UZ_COMMENTS_NEG = [
    "Yomon post, qiziq emas", "Afsus, kutganday chiqmadi",
    "Bu umuman kerak emas", "Men sizni tushunmadim",
    "Nafratlanaman bunday narsalardan", "Nochor, yaxshiroq qila olardingiz",
]
UZ_COMMENTS_NEU = [
    "OK, tushundim", "Davomi bormi?", "Qayerda yozilgan?", "Narxi qancha?",
    "Qancha vaqt oldin?", "Menda savol bor",
]

RU_COMMENTS_POS = [
    "Супер, спасибо!", "Очень полезно и интересно 🔥",
    "Отлично снято, красивые кадры", "Лучший пост за неделю",
    "Класс, продолжайте!", "Супер отлично!", "Красиво 👍",
]
RU_COMMENTS_NEG = [
    "Ужасно, не понравилось", "Плохо, ожидал большего",
    "Ненавижу такие посты", "Бесит, честно говоря",
    "Фу, отвратительно снято", "Плохой контент",
]
RU_COMMENTS_NEU = [
    "Хорошо, ладно", "А где был этот кадр?", "Сколько это стоит?",
    "Неплохо, но есть вопросы", "Ждём следующий пост",
]

EN_COMMENTS_POS = [
    "Love this! Amazing content", "So inspiring, thank you!",
    "Great post, keep it up 🔥", "Beautiful shot", "Best thing I saw today",
    "Perfect, exactly what I needed", "This is fire",
]
EN_COMMENTS_NEG = [
    "This is terrible", "Honestly bad content",
    "Worst post I've seen this week", "Hate this, unfollowing",
    "Awful, disappointing", "Fake and scam-like",
]
EN_COMMENTS_NEU = [
    "Interesting, where was this?", "How long did it take?",
    "Can you share more details?", "Where can I buy this?",
    "Waiting for part 2",
]

LANG_BUCKETS = {
    Language.UZBEK: (UZ_COMMENTS_POS, UZ_COMMENTS_NEU, UZ_COMMENTS_NEG, UZ_CAPTIONS),
    Language.RUSSIAN: (RU_COMMENTS_POS, RU_COMMENTS_NEU, RU_COMMENTS_NEG, RU_CAPTIONS),
    Language.ENGLISH: (EN_COMMENTS_POS, EN_COMMENTS_NEU, EN_COMMENTS_NEG, EN_CAPTIONS),
}

HANDLES = [
    "aziz_07", "nodira.life", "world_explorer", "tech_guru_uz",
    "foodie_tashkent", "music_lover_99", "bookworm_daily", "photo_studio",
    "runner_uz", "uz_student", "marketing_pro", "startup_tashkent",
    "анна_путешествия", "максим_блогер", "photo_by_dmitry",
    "cool.dev", "mindful_life", "news_digest",
]


@dataclass(frozen=True)
class SeedStats:
    """Summary of what the generator wrote to the database."""
    accounts: int
    posts: int
    comments: int
    sentiments: int
    model_name: str


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class DemoDataGenerator:
    PLATFORM_TEMPLATES: dict[str, list[str]] = {
        Platform.INSTAGRAM: [PostType.PHOTO, PostType.PHOTO, PostType.REEL, PostType.CAROUSEL, PostType.VIDEO],
        Platform.TELEGRAM:  [PostType.CHANNEL_POST, PostType.CHANNEL_POST, PostType.PHOTO, PostType.VIDEO],
        Platform.YOUTUBE:   [PostType.VIDEO, PostType.VIDEO, PostType.VIDEO],
        Platform.X:         [PostType.TWEET, PostType.TWEET, PostType.TWEET, PostType.PHOTO],
    }

    # Realistic ranges — used to seed follower counts and pick peak engagement
    FOLLOWER_RANGES = {
        Platform.INSTAGRAM: (800, 25_000),
        Platform.TELEGRAM:  (1_200, 40_000),
        Platform.YOUTUBE:   (400, 8_000),
        Platform.X:         (200, 6_000),
    }

    def __init__(
        self,
        *,
        seed: int | None = None,
        prefer_transformer: bool = False,
    ) -> None:
        self._rng = random.Random(seed)
        self._analyzer = get_analyzer(prefer_transformer=prefer_transformer)

    # --- Public entry point ---------------------------------------------------

    @transaction.atomic
    def seed(
        self,
        user,
        *,
        platforms: Iterable[str] = (Platform.INSTAGRAM, Platform.TELEGRAM, Platform.YOUTUBE, Platform.X),
        posts_per_platform: int = 120,
        comments_per_post_range: tuple[int, int] = (4, 22),
        days_back: int = 180,
        analyze_sentiment: bool = True,
        replace: bool = False,
    ) -> SeedStats:
        """Populate a user's demo graph. Idempotent when ``replace=True``.

        Args:
            user: Django User instance the accounts are attached to.
            platforms: Which platforms to seed.
            posts_per_platform: Number of posts per account.
            comments_per_post_range: (min, max) inclusive for each post.
            days_back: How far back ``published_at`` values can go.
            analyze_sentiment: If True, classify every comment and persist.
            replace: Wipe this user's existing demo accounts first.
        """
        if replace:
            ConnectedAccount.objects.filter(user=user, is_demo=True).delete()

        rng = self._rng
        now = timezone.now()

        accounts: list[ConnectedAccount] = []
        for platform in platforms:
            accounts.append(self._create_account(user, platform, now, rng))

        posts: list[Post] = []
        for account in accounts:
            posts.extend(self._create_posts(account, posts_per_platform, days_back, now, rng))

        comments: list[Comment] = []
        for post in posts:
            lo, hi = comments_per_post_range
            n = rng.randint(lo, hi)
            comments.extend(self._create_comments(post, n, rng))

        sentiments = 0
        model_name = self._analyzer.model_name
        if analyze_sentiment and comments:
            sentiments = self._classify_comments(comments)
            model_name = self._analyzer.model_name

        return SeedStats(
            accounts=len(accounts),
            posts=len(posts),
            comments=len(comments),
            sentiments=sentiments,
            model_name=model_name,
        )

    # --- Private helpers ------------------------------------------------------

    def _create_account(self, user, platform: str, now: datetime, rng: random.Random) -> ConnectedAccount:
        low, high = self.FOLLOWER_RANGES[platform]
        follower = rng.randint(low, high)
        handle = rng.choice(HANDLES) + f"_{rng.randint(10, 99)}"
        return ConnectedAccount.objects.create(
            user=user,
            platform=platform,
            external_id=f"demo-{platform}-{user.id}-{rng.randint(10**7, 10**9)}",
            handle=handle,
            display_name=handle.replace("_", " ").replace(".", " ").title(),
            avatar_url=f"https://api.dicebear.com/7.x/adventurer/svg?seed={handle}",
            follower_count=follower,
            following_count=rng.randint(50, int(follower * 0.15) + 100),
            is_demo=True,
        )

    def _create_posts(
        self,
        account: ConnectedAccount,
        n: int,
        days_back: int,
        now: datetime,
        rng: random.Random,
    ) -> list[Post]:
        templates = self.PLATFORM_TEMPLATES[account.platform]
        follower = account.follower_count
        batch: list[Post] = []
        for i in range(n):
            post_type = rng.choice(templates)
            published_at = self._pick_post_time(now, days_back, rng)
            reach = int(follower * rng.uniform(0.10, 0.65))
            views = reach if account.platform != Platform.X else int(reach * rng.uniform(1.0, 3.0))
            engagement_factor = {
                PostType.REEL: 1.4, PostType.VIDEO: 1.2, PostType.CAROUSEL: 1.15,
                PostType.PHOTO: 1.0, PostType.TWEET: 0.9, PostType.CHANNEL_POST: 0.85,
            }.get(post_type, 1.0)
            likes = int(views * rng.uniform(0.02, 0.085) * engagement_factor)
            comments_count = int(likes * rng.uniform(0.03, 0.12))
            shares = int(likes * rng.uniform(0.01, 0.06))
            lang_caption = rng.choice([UZ_CAPTIONS, RU_CAPTIONS, EN_CAPTIONS])
            caption = rng.choice(lang_caption)
            engagement_rate = (likes + comments_count + shares) / max(views, 1)
            batch.append(Post(
                account=account,
                external_id=f"demo-{account.platform}-{account.id}-{i}-{rng.randint(10**5, 10**8)}",
                post_type=post_type,
                caption=caption,
                url=f"https://example.com/{account.platform}/{rng.randint(10**6, 10**9)}",
                published_at=published_at,
                views=views,
                likes=likes,
                comments_count=comments_count,
                shares=shares,
                engagement_rate=round(engagement_rate, 4),
            ))
        return list(Post.objects.bulk_create(batch))

    def _pick_post_time(self, now: datetime, days_back: int, rng: random.Random) -> datetime:
        # Log-biased backward so more recent = more posts. Cluster at 10am/7pm.
        day_frac = 1 - rng.random() ** 1.6     # bias toward 1 (recent)
        days_ago = day_frac * days_back
        base = now - timedelta(days=days_ago)
        peak_hour = 10 if rng.random() < 0.45 else 19
        hour = int(max(0, min(23, rng.gauss(peak_hour, 3))))
        return base.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59), microsecond=0)

    def _create_comments(self, post: Post, n: int, rng: random.Random) -> list[Comment]:
        out: list[Comment] = []
        base_seed = 10**6
        for i in range(n):
            lang = self._pick_language(rng)
            polarity = self._pick_polarity(rng)
            pos, neu, neg, _ = LANG_BUCKETS[lang]
            pool = pos if polarity == 0 else neu if polarity == 1 else neg
            body = rng.choice(pool)
            minutes_after = rng.randint(2, 60 * 24 * 14)  # up to 2 weeks after
            published_at = post.published_at + timedelta(minutes=minutes_after)
            if published_at > timezone.now():
                published_at = timezone.now() - timedelta(minutes=rng.randint(1, 120))
            out.append(Comment(
                post=post,
                external_id=f"demo-c-{post.id}-{i}-{rng.randint(base_seed, base_seed*10)}",
                author_handle=rng.choice(HANDLES) + str(rng.randint(100, 9999)),
                body=body,
                language=lang,
                likes=rng.randint(0, max(1, int(post.likes * 0.003))),
                published_at=published_at,
            ))
        return list(Comment.objects.bulk_create(out))

    @staticmethod
    def _pick_language(rng: random.Random) -> str:
        r = rng.random()
        if r < 0.40: return Language.UZBEK
        if r < 0.80: return Language.RUSSIAN
        return Language.ENGLISH

    @staticmethod
    def _pick_polarity(rng: random.Random) -> int:
        """0 = positive, 1 = neutral, 2 = negative."""
        r = rng.random()
        if r < 0.60: return 0
        if r < 0.85: return 1
        return 2

    # --- Sentiment ------------------------------------------------------------

    def _classify_comments(self, comments: list[Comment]) -> int:
        preds: list[SentimentPrediction] = self._analyzer.analyze_batch(
            [c.body for c in comments],
            languages=[c.language if c.language != "xx" else None for c in comments],
        )
        to_create = [
            SentimentResult(
                comment=c,
                label=p.label,
                score=round(float(p.score), 4),
                model_name=p.model_name,
            )
            for c, p in zip(comments, preds)
        ]
        SentimentResult.objects.bulk_create(to_create)
        return len(to_create)
