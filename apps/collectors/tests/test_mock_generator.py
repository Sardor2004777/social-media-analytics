"""Integration tests for the demo-mode data generator."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.analytics.models import SentimentLabel, SentimentResult
from apps.collectors.models import Comment
from apps.collectors.services.mock_generator import DemoDataGenerator
from apps.social.models import ConnectedAccount, Platform, Post

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    User = get_user_model()
    u = User(username="demo-gen@example.com", email="demo-gen@example.com")
    u.set_password("x!23QWE123")
    u.save()
    return u


def test_seed_creates_four_platforms(user) -> None:
    gen = DemoDataGenerator(seed=1)
    stats = gen.seed(user, posts_per_platform=5, comments_per_post_range=(1, 2), days_back=30)
    assert stats.accounts == 4
    assert ConnectedAccount.objects.filter(user=user).count() == 4


def test_seed_post_counts(user) -> None:
    gen = DemoDataGenerator(seed=2)
    stats = gen.seed(user, posts_per_platform=8, comments_per_post_range=(0, 0), analyze_sentiment=False)
    assert stats.posts == 32  # 4 platforms * 8 posts
    assert Post.objects.filter(account__user=user).count() == 32


def test_seed_marks_accounts_as_demo(user) -> None:
    DemoDataGenerator(seed=3).seed(user, posts_per_platform=3, comments_per_post_range=(0, 0), analyze_sentiment=False)
    assert ConnectedAccount.objects.filter(user=user, is_demo=True).count() == 4
    assert ConnectedAccount.objects.filter(user=user, is_demo=False).count() == 0


def test_seed_creates_comments_with_languages(user) -> None:
    DemoDataGenerator(seed=4).seed(user, posts_per_platform=4, comments_per_post_range=(5, 6), analyze_sentiment=False)
    langs = set(Comment.objects.filter(post__account__user=user).values_list("language", flat=True))
    # Need at least 2 of the 3 language buckets to appear with reasonable volume
    assert len(langs & {"uz", "ru", "en"}) >= 2


def test_seed_runs_sentiment_and_persists(user) -> None:
    stats = DemoDataGenerator(seed=5).seed(
        user,
        posts_per_platform=3,
        comments_per_post_range=(3, 4),
        analyze_sentiment=True,
    )
    count = SentimentResult.objects.filter(comment__post__account__user=user).count()
    assert count == stats.comments
    assert count > 0
    labels = set(SentimentResult.objects.values_list("label", flat=True))
    assert labels <= {SentimentLabel.POSITIVE, SentimentLabel.NEUTRAL, SentimentLabel.NEGATIVE}


def test_seed_replace_wipes_previous(user) -> None:
    gen = DemoDataGenerator(seed=6)
    gen.seed(user, posts_per_platform=2, comments_per_post_range=(0, 0), analyze_sentiment=False)
    first = set(ConnectedAccount.objects.filter(user=user).values_list("id", flat=True))
    gen.seed(user, posts_per_platform=2, comments_per_post_range=(0, 0), analyze_sentiment=False, replace=True)
    second = set(ConnectedAccount.objects.filter(user=user).values_list("id", flat=True))
    assert first & second == set()
