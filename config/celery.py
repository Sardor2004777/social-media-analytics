"""Celery application for social-analytics.

Queues:
    - ``default``     — misc tasks
    - ``collectors``  — platform data collection (low-priority, long-running)
    - ``analytics``   — aggregation + sentiment (higher priority, CPU/ML)
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:
    """Print task request info — used to sanity-check worker wiring."""
    print(f"Request: {self.request!r}")
