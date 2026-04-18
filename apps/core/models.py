"""Shared abstract models used across apps."""
from django.db import models


class TimestampedModel(models.Model):
    """Abstract base providing created_at / updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
