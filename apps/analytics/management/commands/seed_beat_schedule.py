"""Seed Celery Beat with the analytics app's periodic tasks.

django-celery-beat stores its schedule in the DB (not settings), so a one-off
management command is the cleanest way to create the rows — idempotent via
``get_or_create`` so re-running is safe.

Usage:
    python manage.py seed_beat_schedule
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


SCHEDULES = [
    {
        "name":     "analytics.weekly_digest",
        "task":     "apps.analytics.tasks.send_weekly_digest_all_users",
        "crontab":  {"minute": "0", "hour": "8", "day_of_week": "1"},  # Mon 08:00
        "description": "Every Monday 08:00 — AI-generated weekly email digest.",
    },
    {
        "name":     "analytics.daily_anomaly_scan",
        "task":     "apps.analytics.tasks.detect_anomalies_all_accounts",
        "crontab":  {"minute": "0", "hour": "9", "day_of_week": "*"},  # Daily 09:00
        "description": "Daily 09:00 — z-score anomaly scan over all live accounts.",
    },
]


class Command(BaseCommand):
    help = "Create / update the analytics periodic tasks in django-celery-beat."

    def handle(self, *args, **opts) -> None:
        for cfg in SCHEDULES:
            schedule, _ = CrontabSchedule.objects.get_or_create(**cfg["crontab"])
            task, created = PeriodicTask.objects.update_or_create(
                name=cfg["name"],
                defaults={
                    "task":        cfg["task"],
                    "crontab":     schedule,
                    "enabled":     True,
                    "description": cfg["description"],
                },
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{verb}: {task.name}  ->  {task.task}"))
