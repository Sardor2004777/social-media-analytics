"""Sentiment classification result for a single comment.

Stored as a row-per-comment (OneToOne). The ``model_name`` field lets us swap
between a light VADER pipeline and a heavier transformer model — both can
coexist in the DB and we can filter/compare their outputs.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.collectors.models import Comment
from apps.core.models import TimestampedModel
from apps.social.models import ConnectedAccount


class SentimentLabel(models.TextChoices):
    POSITIVE = "positive", "Positive"
    NEUTRAL  = "neutral",  "Neutral"
    NEGATIVE = "negative", "Negative"


class SentimentResult(TimestampedModel):
    comment = models.OneToOneField(
        Comment,
        on_delete=models.CASCADE,
        related_name="sentiment",
    )
    label       = models.CharField(max_length=16, choices=SentimentLabel.choices, db_index=True)
    score       = models.FloatField(help_text="Confidence score, 0..1")
    model_name  = models.CharField(max_length=64, default="vader")

    class Meta:
        indexes = [
            models.Index(fields=["label"]),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.score:.2f}) via {self.model_name}"


class AnomalyMetric(models.TextChoices):
    ENGAGEMENT_RATE  = "engagement_rate",  "Engagement rate"
    FOLLOWER_GROWTH  = "follower_growth",  "Follower growth"
    SENTIMENT_RATIO  = "sentiment_ratio",  "Sentiment ratio (positive %)"
    POSTS_PER_DAY    = "posts_per_day",    "Posts per day"
    COMMENT_VOLUME   = "comment_volume",   "Comment volume"


class AnomalyDirection(models.TextChoices):
    SPIKE = "spike", "Spike (up)"
    DROP  = "drop",  "Drop (down)"


class AnomalySeverity(models.TextChoices):
    INFO     = "info",     "Info"
    WARNING  = "warning",  "Warning"
    CRITICAL = "critical", "Critical"


class Alert(TimestampedModel):
    """Automatically detected deviation on a tracked account metric.

    Populated by the :mod:`apps.analytics.tasks` Celery task that runs a
    rolling z-score over the last ``window_days`` of daily aggregates.
    A row is created only when ``|z_score| >= threshold`` (default 2.0).
    """
    account = models.ForeignKey(
        ConnectedAccount,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    metric    = models.CharField(max_length=32, choices=AnomalyMetric.choices, db_index=True)
    direction = models.CharField(max_length=8,  choices=AnomalyDirection.choices)
    severity  = models.CharField(max_length=16, choices=AnomalySeverity.choices, default=AnomalySeverity.WARNING, db_index=True)

    value       = models.FloatField(help_text="Observed value on the detection day")
    baseline    = models.FloatField(help_text="Rolling mean over the look-back window")
    z_score     = models.FloatField(help_text="Signed z-score (negative = drop)")
    window_days = models.PositiveSmallIntegerField(default=14)

    message     = models.CharField(max_length=255, blank=True)
    is_read     = models.BooleanField(default=False, db_index=True)
    is_resolved = models.BooleanField(default=False, db_index=True)
    detected_for = models.DateField(help_text="Calendar day the anomaly refers to", db_index=True)

    class Meta:
        ordering = ["-detected_for", "-created_at"]
        indexes = [
            models.Index(fields=["account", "-detected_for"]),
            models.Index(fields=["severity", "is_resolved"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "metric", "detected_for"],
                name="uniq_alert_per_account_metric_day",
            ),
        ]

    def __str__(self) -> str:
        arrow = "↑" if self.direction == AnomalyDirection.SPIKE else "↓"
        return f"{arrow} {self.get_metric_display()} · @{self.account.handle} · z={self.z_score:.1f}"


class NotificationChannel(models.TextChoices):
    TELEGRAM = "telegram", "Telegram bot"
    EMAIL    = "email",    "Email"


class NotificationPref(TimestampedModel):
    """Per-user routing config for anomaly alerts.

    Only alerts with ``severity >= min_severity`` on an *enabled* metric are
    delivered. ``telegram_chat_id`` is set after the user DMs the bot once
    (the bot's ``/start`` handler captures the chat id — this field is just
    where we persist it).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_pref",
    )
    channel          = models.CharField(max_length=16, choices=NotificationChannel.choices, default=NotificationChannel.TELEGRAM)
    telegram_chat_id = models.CharField(max_length=32, blank=True)
    is_active        = models.BooleanField(default=True)
    min_severity     = models.CharField(
        max_length=16,
        choices=AnomalySeverity.choices,
        default=AnomalySeverity.WARNING,
    )
    enabled_metrics = models.JSONField(
        default=list,
        blank=True,
        help_text="Empty list = all metrics enabled",
    )

    class Meta:
        verbose_name = "Notification preference"
        verbose_name_plural = "Notification preferences"

    def __str__(self) -> str:
        return f"{self.channel} → {self.user.email}"

    _SEVERITY_RANK = {
        AnomalySeverity.INFO:     0,
        AnomalySeverity.WARNING:  1,
        AnomalySeverity.CRITICAL: 2,
    }

    def accepts(self, alert: "Alert") -> bool:
        if not self.is_active:
            return False
        if self._SEVERITY_RANK[alert.severity] < self._SEVERITY_RANK[self.min_severity]:
            return False
        if self.enabled_metrics and alert.metric not in self.enabled_metrics:
            return False
        if self.channel == NotificationChannel.TELEGRAM and not self.telegram_chat_id:
            return False
        return True
