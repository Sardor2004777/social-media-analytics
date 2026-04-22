"""Signal wiring for the analytics app.

Newly created ``Alert`` rows fan out to the user's configured notification
channel via Celery — keeping the HTTP/SMTP call off the web process and out
of the detection task's transaction.
"""
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Alert


@receiver(post_save, sender=Alert)
def _alert_created(sender, instance: Alert, created: bool, **kwargs) -> None:
    if not created:
        return
    # Import here to avoid import-time Celery dependency during migrations.
    from .tasks import notify_alert

    notify_alert.delay(instance.id)
