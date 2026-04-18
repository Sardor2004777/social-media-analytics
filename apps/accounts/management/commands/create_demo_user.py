"""Management command to create/reset a demo dashboard user.

Useful for:
  - Local preview of the authenticated dashboard without going through signup.
  - CI smoke tests that need a verified user.

Usage:
    python manage.py create_demo_user
    python manage.py create_demo_user --email alice@example.com --password s3cret!
"""
from __future__ import annotations

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

DEFAULT_EMAIL = "demo@social-analytics.app"
DEFAULT_PASSWORD = "Demo12345!"  # noqa: S105 — dev-only demo password


class Command(BaseCommand):
    help = "Create or reset the password for a verified demo dashboard user."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--email", default=DEFAULT_EMAIL)
        parser.add_argument("--password", default=DEFAULT_PASSWORD)

    def handle(self, *args, **options) -> None:
        User = get_user_model()
        email = options["email"]
        password = options["password"]

        user, created = User.objects.get_or_create(email=email)
        user.set_password(password)
        user.save()
        EmailAddress.objects.update_or_create(
            user=user,
            email=email,
            defaults={"verified": True, "primary": True},
        )

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{action} demo user: {email} / {password}"
        ))
