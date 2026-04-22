"""Tests for the z-score anomaly detection Celery task.

These hit real DB objects on the in-memory SQLite used by the test settings.
No mocks — we want to verify the SQL aggregations + z-score math together.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.analytics.models import (
    Alert,
    AnomalyDirection,
    AnomalyMetric,
    AnomalySeverity,
)
from apps.analytics.tasks import detect_anomalies_for_account
from apps.social.models import ConnectedAccount, Platform, Post, PostType

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="anomaly_user",
        email="anomaly@test.com",
        password="pw-for-test-only-1",  # noqa: S106
    )


@pytest.fixture
def account(user):
    return ConnectedAccount.objects.create(
        user=user,
        platform=Platform.INSTAGRAM,
        external_id="ig-123",
        handle="test_acc",
        display_name="Test Acc",
        follower_count=1000,
    )


def _mk_post(account, when, engagement=0.02, likes=10, views=500):
    return Post.objects.create(
        account=account,
        external_id=f"p-{when.isoformat()}-{engagement}",
        post_type=PostType.PHOTO,
        published_at=when,
        likes=likes,
        views=views,
        comments_count=1,
        engagement_rate=engagement,
    )


@pytest.mark.django_db
def test_detect_spike_engagement_creates_alert(account):
    """14 days of ~2% engagement → single 15% day should fire a SPIKE alert."""
    now = timezone.now()
    # 14 days of stable 2% engagement
    for i in range(1, 15):
        _mk_post(account, now - timedelta(days=i), engagement=0.02)
    # today — a massive spike
    _mk_post(account, now, engagement=0.15)

    result = detect_anomalies_for_account(account.id)

    assert result["account_id"] == account.id
    assert len(result["new_alert_ids"]) >= 1

    alerts = Alert.objects.filter(account=account, metric=AnomalyMetric.ENGAGEMENT_RATE)
    assert alerts.count() == 1
    alert = alerts.get()
    assert alert.direction == AnomalyDirection.SPIKE
    assert alert.z_score > 2.0
    assert alert.severity in {AnomalySeverity.WARNING, AnomalySeverity.CRITICAL}


@pytest.mark.django_db
def test_flat_series_produces_no_alert(account):
    """Uniform history should never fire — z-score is ~0 everywhere."""
    now = timezone.now()
    for i in range(0, 15):
        _mk_post(account, now - timedelta(days=i), engagement=0.03)

    result = detect_anomalies_for_account(account.id)
    assert result["new_alert_ids"] == []
    assert not Alert.objects.filter(account=account).exists()


@pytest.mark.django_db
def test_detection_is_idempotent(account):
    """Re-running on the same day must not duplicate alerts (unique constraint)."""
    now = timezone.now()
    for i in range(1, 15):
        _mk_post(account, now - timedelta(days=i), engagement=0.02)
    _mk_post(account, now, engagement=0.18)

    detect_anomalies_for_account(account.id)
    first_count = Alert.objects.filter(account=account).count()
    assert first_count >= 1

    detect_anomalies_for_account(account.id)
    second_count = Alert.objects.filter(account=account).count()
    assert second_count == first_count


@pytest.mark.django_db
def test_insufficient_history_returns_no_alert(account):
    """Less than 5 points of history → skip (can't compute stable baseline)."""
    now = timezone.now()
    _mk_post(account, now - timedelta(days=1), engagement=0.02)
    _mk_post(account, now - timedelta(days=2), engagement=0.02)
    _mk_post(account, now, engagement=0.99)  # extreme, but baseline too thin

    result = detect_anomalies_for_account(account.id)
    assert result["new_alert_ids"] == []


@pytest.mark.django_db
def test_missing_account_returns_status(db):
    result = detect_anomalies_for_account(999_999)
    assert result["status"] == "not_found"
