"""Idempotent: create the demo user + seed if data is missing.

Designed to be safe to call on every deploy. Logic:

  1. Create demo@social-analytics.app with the default password if missing.
  2. If that user has zero ConnectedAccount rows, seed a fresh demo dataset.

Triggered by ``scripts/entrypoint.sh`` when ``AUTO_SEED_DEMO=1`` is set in the
environment (Render / Railway dashboard). Never modifies data for a user that
already has posts — safe to run repeatedly.

Usage:
    python manage.py ensure_demo_data
    python manage.py ensure_demo_data --email custom@example.com
"""
from __future__ import annotations

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.collectors.services.mock_generator import DemoDataGenerator
from apps.social.models import ConnectedAccount

DEFAULT_EMAIL = "demo@social-analytics.app"
DEFAULT_PASSWORD = "Demo12345!"  # noqa: S105 — demo-only


class Command(BaseCommand):
    help = "Create/reset demo user and seed data if the user has no accounts."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--email",    default=DEFAULT_EMAIL)
        parser.add_argument("--password", default=DEFAULT_PASSWORD)
        parser.add_argument("--posts",    type=int, default=80)
        parser.add_argument("--force",    action="store_true",
                            help="Re-seed even if user already has accounts.")

    def handle(self, *args, **options) -> None:
        User = get_user_model()
        email = options["email"]
        password = options["password"]

        user, created = User.objects.get_or_create(email=email, defaults={"username": email})
        if created or not user.has_usable_password():
            user.set_password(password)
            user.save(update_fields=["password"])
        EmailAddress.objects.update_or_create(
            user=user, email=email,
            defaults={"verified": True, "primary": True},
        )

        has_data = ConnectedAccount.objects.filter(user=user).exists()

        if has_data and not options["force"]:
            self.stdout.write(self.style.SUCCESS(
                f"Demo user {email} already has data; skipping seed. "
                f"(Use --force to re-seed.)"
            ))
            return

        stats = DemoDataGenerator(seed=42).seed(
            user,
            posts_per_platform=options["posts"],
            comments_per_post_range=(3, 18),
            days_back=180,
            analyze_sentiment=True,
            replace=options["force"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {email}: {stats.accounts} accounts · {stats.posts} posts · "
            f"{stats.comments} comments · {stats.sentiments} sentiments ({stats.model_name})"
        ))
