"""Tests for the engagement-prediction LinearRegression service."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone as dt_tz

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.analytics.services.predict import (
    NotEnoughData,
    best_post_recipe,
    predict_for_inputs,
)
from apps.social.models import ConnectedAccount, Platform, Post, PostType


User = get_user_model()


@pytest.fixture
def user_with_posts(db):
    """A user + an account + 20 posts so the regression has enough data to fit."""
    user = User.objects.create(email="ml@test.app", username="mltest")
    account = ConnectedAccount.objects.create(
        user=user, platform=Platform.TELEGRAM,
        external_id="@mltest_chan", handle="mltest_chan",
        follower_count=1000, is_demo=False,
    )
    base = timezone.now()
    for i in range(20):
        Post.objects.create(
            account=account,
            external_id=f"post_{i}",
            post_type=PostType.PHOTO if i % 2 == 0 else PostType.CHANNEL_POST,
            caption=f"Test post {i} #tag1 #tag2",
            url=f"https://example.com/{i}",
            published_at=base.replace(hour=(i % 24)),
            views=100 + i * 10,
            likes=10 + i,
            comments_count=i,
            shares=i // 2,
            engagement_rate=0.05 + i * 0.001,
        )
    return user


def test_predict_for_inputs_returns_prediction(user_with_posts):
    """Happy path — predict_for_inputs runs and returns a Prediction with
    sensible types and bounded values."""
    result = predict_for_inputs(
        user_with_posts,
        weekday=1, hour=10, caption_len=120, hashtag_count=2, has_media=True,
    )
    assert result.expected_likes >= 0
    assert isinstance(result.expected_likes, int)
    assert 0 <= result.r2 <= 1
    assert result.sample_size == 20
    assert len(result.feature_weights) == 5
    # Weights should sum to ~100 (normalised feature importance).
    assert 95 <= sum(result.feature_weights.values()) <= 105


def test_predict_with_too_few_posts_raises(db):
    """Below MIN_TRAIN_ROWS (12) the service refuses with NotEnoughData."""
    user = User.objects.create(email="thin@test.app", username="thintest")
    account = ConnectedAccount.objects.create(
        user=user, platform=Platform.TELEGRAM,
        external_id="@thin", handle="thin", is_demo=False,
    )
    for i in range(5):
        Post.objects.create(
            account=account, external_id=f"p{i}", caption=f"x{i}",
            published_at=timezone.now(), likes=1,
        )
    with pytest.raises(NotEnoughData):
        predict_for_inputs(
            user, weekday=0, hour=9, caption_len=50, hashtag_count=0, has_media=False,
        )


def test_best_post_recipe_returns_recipe(user_with_posts):
    """best_post_recipe should return a complete recipe dict with a winning
    weekday/hour/length combo and an expected_likes >= 0."""
    recipe = best_post_recipe(user_with_posts)
    assert recipe is not None
    assert "weekday" in recipe and isinstance(recipe["weekday"], str)
    assert 0 <= recipe["hour"] <= 23
    assert recipe["caption_len"] in [40, 80, 120, 180, 280, 400]
    assert recipe["hashtag_count"] in [0, 2, 4, 6]
    assert isinstance(recipe["has_media"], bool)
    assert recipe["expected_likes"] >= 0


def test_best_post_recipe_returns_none_for_thin_data(db):
    """No recipe for users without enough training data — falls back to None."""
    user = User.objects.create(email="empty@test.app", username="emptytest")
    assert best_post_recipe(user) is None
