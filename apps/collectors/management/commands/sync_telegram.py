"""Manual trigger: run ``sync_telegram_account`` synchronously.

Useful for local testing without a running Celery worker. In production the
task is invoked via Celery (see ``apps/collectors/tasks.py``).

Usage::

    python manage.py sync_telegram <account_id>
    python manage.py sync_telegram <account_id> --limit 100
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.collectors.tasks import sync_telegram_account


class Command(BaseCommand):
    help = "Synchronously sync a single Telegram ConnectedAccount."

    def add_arguments(self, parser) -> None:
        parser.add_argument("account_id", type=int)
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="How many recent messages to pull (default: 50).",
        )

    def handle(self, *args, account_id: int, limit: int, **options) -> None:
        result = sync_telegram_account.apply(
            args=[account_id],
            kwargs={"post_limit": limit},
        ).get()

        self.stdout.write(json.dumps(result, default=str, indent=2))

        status = result.get("status")
        if status == "ok":
            self.stdout.write(self.style.SUCCESS(
                f"@{result['handle']}: +{result['created']} new / "
                f"{result['updated']} updated, "
                f"{result['follower_count']:,} followers."
            ))
        elif status == "skipped_demo":
            self.stdout.write(self.style.WARNING(
                "Account is a demo account — skipped. Use a real account id."
            ))
        elif status == "not_found":
            self.stdout.write(self.style.ERROR(
                f"No Telegram ConnectedAccount with id={account_id}."
            ))
        else:
            self.stdout.write(self.style.WARNING(f"Status: {status}"))
