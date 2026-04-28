"""Tests for TF-IDF + KMeans post clustering."""
from __future__ import annotations

import pytest

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.analytics.services.clustering import (
    NotEnoughPosts,
    cluster_posts,
)
from apps.social.models import ConnectedAccount, Platform, Post


User = get_user_model()


@pytest.fixture
def user_with_topical_posts(db):
    """A user with two clear topic groups in their captions: sports vs cooking."""
    user = User.objects.create(email="cl@test.app", username="cltest")
    acc = ConnectedAccount.objects.create(
        user=user, platform=Platform.TELEGRAM,
        external_id="@cl", handle="cl", is_demo=False,
    )
    sports = [
        "futbol o'yini bugun ajoyib bo'ldi yutdik",
        "futbol mashqlari haftada uch marta zarur",
        "futbol bo'yicha statistika juda muhim ko'rsatkich",
        "futbolchi karyerada eng yaxshi mashq qilish",
        "stadion kelgan oyda yangi futbol o'yinlari",
        "futbol o'yini natijalari bugun e'lon qilindi",
    ]
    cooking = [
        "osh tayyorlash uchun guruch yog' sabzi kerak",
        "osh ichidagi guruch yumshoq pishishi kerak",
        "osh tayyorlanganda guruch tuzli bo'lishi kerak",
        "osh ustiga sabzi qo'shilsa mazasi yaxshi",
        "yangi osh retsepti ovqat tayyorlashda klassik",
        "osh tayyorlash mashqlar bilan tezroq bo'ladi",
    ]
    base = timezone.now()
    for i, cap in enumerate(sports + cooking):
        Post.objects.create(
            account=acc, external_id=f"post_{i}",
            caption=cap, published_at=base, likes=10 + i,
            engagement_rate=0.04 + i * 0.001,
        )
    return user


def test_cluster_posts_returns_at_least_two_clusters(user_with_topical_posts):
    """With 12 posts in two distinct topic groups, the service should produce
    at least 2 clusters."""
    clusters = cluster_posts(user_with_topical_posts)
    assert len(clusters) >= 2
    # Sorted by avg_engagement_pct descending.
    for prev, nxt in zip(clusters, clusters[1:]):
        assert prev.avg_engagement_pct >= nxt.avg_engagement_pct
    for c in clusters:
        assert c.size >= 1
        assert isinstance(c.label, str)
        assert c.avg_engagement_pct >= 0


def test_cluster_posts_raises_on_thin_data(db):
    """Below MIN_POSTS_FOR_CLUSTERING (12) NotEnoughPosts is raised."""
    user = User.objects.create(email="thin2@test.app", username="thin2")
    acc = ConnectedAccount.objects.create(
        user=user, platform=Platform.TELEGRAM,
        external_id="@thin2", handle="thin2", is_demo=False,
    )
    for i in range(5):
        Post.objects.create(
            account=acc, external_id=f"p{i}", caption=f"text {i}",
            published_at=timezone.now(),
        )
    with pytest.raises(NotEnoughPosts):
        cluster_posts(user)
