"""Raw content models populated by collectors or the demo seeder.

Only ``Comment`` lives here for now — it is the input to downstream sentiment
analysis in ``apps.analytics``. Raw post/follower snapshots stay in
``apps.social`` because they're the primary domain entity, not collector state.
"""
from __future__ import annotations

from django.db import models

from apps.core.models import TimestampedModel
from apps.social.models import Post


class Language(models.TextChoices):
    UZBEK   = "uz", "O'zbek"
    RUSSIAN = "ru", "Русский"
    ENGLISH = "en", "English"
    OTHER   = "xx", "Boshqa"


class Comment(TimestampedModel):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")

    external_id   = models.CharField(max_length=128)
    author_handle = models.CharField(max_length=128, blank=True)
    body          = models.TextField()
    language      = models.CharField(max_length=2, choices=Language.choices, default=Language.OTHER, db_index=True)
    likes         = models.PositiveIntegerField(default=0)
    published_at  = models.DateTimeField(db_index=True)

    class Meta:
        unique_together = [("post", "external_id")]
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["post", "-published_at"]),
        ]

    def __str__(self) -> str:
        return f"@{self.author_handle or '?'}: {self.body[:60]}"
