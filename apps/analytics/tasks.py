"""Celery tasks for automated anomaly detection over daily metric series.

Runs on the ``analytics`` queue. The algorithm is intentionally simple — a
rolling z-score over the last ``window_days`` of daily aggregates — so it stays
cheap per-account and explainable to end-users. Heavier approaches (Prophet,
IsolationForest) can plug in later without changing the ``Alert`` schema.
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from statistics import mean, pstdev

from celery import shared_task
from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from apps.analytics.models import (
    Alert,
    AnomalyDirection,
    AnomalyMetric,
    AnomalySeverity,
    SentimentLabel,
    SentimentResult,
)
from apps.collectors.models import Comment
from apps.social.models import ConnectedAccount, Post

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 14
DEFAULT_Z_THRESHOLD = 2.0
CRITICAL_Z_THRESHOLD = 3.5


def _severity_for(z: float) -> str:
    az = abs(z)
    if az >= CRITICAL_Z_THRESHOLD:
        return AnomalySeverity.CRITICAL
    if az >= DEFAULT_Z_THRESHOLD:
        return AnomalySeverity.WARNING
    return AnomalySeverity.INFO


def _daily_engagement(account: ConnectedAccount, start: date, end: date) -> dict[date, float]:
    qs = (
        Post.objects.filter(
            account=account,
            published_at__date__gte=start,
            published_at__date__lte=end,
        )
        .values("published_at__date")
        .annotate(er=Avg("engagement_rate"))
    )
    return {row["published_at__date"]: float(row["er"] or 0.0) for row in qs}


def _daily_post_count(account: ConnectedAccount, start: date, end: date) -> dict[date, float]:
    qs = (
        Post.objects.filter(
            account=account,
            published_at__date__gte=start,
            published_at__date__lte=end,
        )
        .values("published_at__date")
        .annotate(n=Count("id"))
    )
    return {row["published_at__date"]: float(row["n"]) for row in qs}


def _daily_comment_volume(account: ConnectedAccount, start: date, end: date) -> dict[date, float]:
    qs = (
        Comment.objects.filter(
            post__account=account,
            created_at__date__gte=start,
            created_at__date__lte=end,
        )
        .values("created_at__date")
        .annotate(n=Count("id"))
    )
    return {row["created_at__date"]: float(row["n"]) for row in qs}


def _daily_sentiment_ratio(account: ConnectedAccount, start: date, end: date) -> dict[date, float]:
    qs = (
        SentimentResult.objects.filter(
            comment__post__account=account,
            created_at__date__gte=start,
            created_at__date__lte=end,
        )
        .values("created_at__date", "label")
        .annotate(n=Count("id"))
    )
    totals: dict[date, int] = {}
    positive: dict[date, int] = {}
    for row in qs:
        d = row["created_at__date"]
        totals[d] = totals.get(d, 0) + row["n"]
        if row["label"] == SentimentLabel.POSITIVE:
            positive[d] = positive.get(d, 0) + row["n"]
    return {d: positive.get(d, 0) / t for d, t in totals.items() if t}


METRIC_FETCHERS = {
    AnomalyMetric.ENGAGEMENT_RATE: _daily_engagement,
    AnomalyMetric.POSTS_PER_DAY:   _daily_post_count,
    AnomalyMetric.COMMENT_VOLUME:  _daily_comment_volume,
    AnomalyMetric.SENTIMENT_RATIO: _daily_sentiment_ratio,
}


def _zscore_of_last(series: dict[date, float], target_day: date) -> tuple[float, float, float] | None:
    """Return (value, baseline_mean, z_score) or None if insufficient data.

    The target day is compared against the distribution of the *preceding* days
    in the window so a single outlier does not dampen its own z-score.
    """
    history = [series[d] for d in sorted(series) if d < target_day]
    if len(history) < 5:
        return None
    mu = mean(history)
    sd = pstdev(history)
    value = series.get(target_day, 0.0)
    if sd == 0:
        return (value, mu, 0.0) if value == mu else (value, mu, math.copysign(4.0, value - mu))
    return value, mu, (value - mu) / sd


def _human_message(metric: str, direction: str, value: float, baseline: float) -> str:
    arrow = "ko'paydi" if direction == AnomalyDirection.SPIKE else "pasaydi"
    if baseline:
        pct = (value - baseline) / baseline * 100
        delta = f"{pct:+.0f}%"
    else:
        delta = f"{value:+.2f}"
    label = dict(AnomalyMetric.choices).get(metric, metric)
    return f"{label} keskin {arrow} ({delta} o'rtachaga nisbatan)"


@shared_task(
    bind=True,
    queue="analytics",
    name="apps.analytics.tasks.detect_anomalies_for_account",
)
def detect_anomalies_for_account(
    self,
    account_id: int,
    window_days: int = DEFAULT_WINDOW_DAYS,
    threshold: float = DEFAULT_Z_THRESHOLD,
) -> dict:
    """Compute z-scores for every tracked metric and persist ``Alert`` rows."""
    try:
        account = ConnectedAccount.objects.get(id=account_id)
    except ConnectedAccount.DoesNotExist:
        logger.warning("detect_anomalies_for_account: %s not found", account_id)
        return {"account_id": account_id, "status": "not_found"}

    today = timezone.localdate()
    start = today - timedelta(days=window_days)
    created: list[int] = []

    with transaction.atomic():
        for metric, fetcher in METRIC_FETCHERS.items():
            series = fetcher(account, start, today)
            result = _zscore_of_last(series, today)
            if result is None:
                continue
            value, baseline, z = result
            if abs(z) < threshold:
                continue
            direction = AnomalyDirection.SPIKE if z > 0 else AnomalyDirection.DROP
            alert, was_created = Alert.objects.update_or_create(
                account=account,
                metric=metric,
                detected_for=today,
                defaults={
                    "direction":   direction,
                    "severity":    _severity_for(z),
                    "value":       value,
                    "baseline":    baseline,
                    "z_score":     z,
                    "window_days": window_days,
                    "message":     _human_message(metric, direction, value, baseline),
                },
            )
            if was_created:
                created.append(alert.id)

    return {
        "account_id": account_id,
        "detected_for": today.isoformat(),
        "new_alert_ids": created,
    }


@shared_task(
    bind=True,
    queue="analytics",
    name="apps.analytics.tasks.detect_anomalies_all_accounts",
)
def detect_anomalies_all_accounts(self, window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """Fan-out wrapper — schedules per-account detection for every live account."""
    account_ids = list(
        ConnectedAccount.objects.filter(is_demo=False).values_list("id", flat=True)
    )
    for aid in account_ids:
        detect_anomalies_for_account.delay(aid, window_days=window_days)
    return {"scheduled": len(account_ids)}


@shared_task(
    bind=True,
    queue="analytics",
    name="apps.analytics.tasks.notify_alert",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def notify_alert(self, alert_id: int) -> dict:
    """Dispatch a single ``Alert`` to the owning user's preferred channel."""
    from apps.analytics.notifications import dispatch

    try:
        alert = Alert.objects.select_related("account", "account__user").get(id=alert_id)
    except Alert.DoesNotExist:
        logger.warning("notify_alert: alert %s not found", alert_id)
        return {"alert_id": alert_id, "status": "not_found"}

    return {"alert_id": alert_id, **dispatch(alert)}


@shared_task(
    bind=True,
    queue="analytics",
    name="apps.analytics.tasks.send_weekly_digest_for_user",
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 2},
)
def send_weekly_digest_for_user(self, user_id: int) -> dict:
    """Build an AI-generated weekly digest and email it to one user."""
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    from apps.analytics.services.chat import (
        ChatNotConfigured,
        generate_weekly_digest,
    )

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {"user_id": user_id, "status": "not_found"}

    if not user.email:
        return {"user_id": user_id, "status": "no_email"}

    if not ConnectedAccount.objects.filter(user=user).exists():
        return {"user_id": user_id, "status": "no_accounts"}

    try:
        resp = generate_weekly_digest(user)
    except ChatNotConfigured as exc:
        logger.warning("Weekly digest skipped for %s: %s", user.email, exc)
        return {"user_id": user_id, "status": "not_configured"}

    subject = "Haftalik AI hisobot — Social Analytics"
    ctx = {"user": user, "digest_markdown": resp.answer, "model": resp.model}
    text_body = render_to_string("emails/weekly_digest.txt", ctx)
    html_body = render_to_string("emails/weekly_digest.html", ctx)

    msg = EmailMultiAlternatives(
        subject,
        text_body,
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
        [user.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)

    return {
        "user_id": user_id,
        "status":  "sent",
        "tokens":  {"in": resp.tokens_in, "out": resp.tokens_out},
    }


@shared_task(
    bind=True,
    queue="analytics",
    name="apps.analytics.tasks.send_weekly_digest_all_users",
)
def send_weekly_digest_all_users(self) -> dict:
    """Celery-beat entry point — fan out the weekly digest to every active user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user_ids = list(
        User.objects.filter(is_active=True)
        .exclude(email="")
        .values_list("id", flat=True)
    )
    for uid in user_ids:
        send_weekly_digest_for_user.delay(uid)
    return {"scheduled": len(user_ids)}
