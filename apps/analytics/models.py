"""Sentiment classification result for a single comment.

Stored as a row-per-comment (OneToOne). The ``model_name`` field lets us swap
between a light VADER pipeline and a heavier transformer model — both can
coexist in the DB and we can filter/compare their outputs.
"""
from __future__ import annotations

from django.db import models

from apps.collectors.models import Comment
from apps.core.models import TimestampedModel


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
