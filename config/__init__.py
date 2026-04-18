"""Project configuration package.

Exposes the Celery app so decorators like @shared_task pick it up.
"""
from .celery import app as celery_app

__all__ = ["celery_app"]
