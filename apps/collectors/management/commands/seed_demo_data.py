"""Populate a user's dashboard with realistic demo data.

Usage:
    python manage.py seed_demo_data                       # seeds demo@social-analytics.app
    python manage.py seed_demo_data --email a@b.com
    python manage.py seed_demo_data --posts 200 --replace # wipe + reseed
    python manage.py seed_demo_data --no-sentiment        # skip sentiment pass
    python manage.py seed_demo_data --transformer         # try XLM-RoBERTa
"""
from __future__ import annotations

import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.collectors.services.mock_generator import DemoDataGenerator


class Command(BaseCommand):
    help = "Seed a user with multi-platform demo data + sentiment results."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--email", default="demo@social-analytics.app")
        parser.add_argument("--posts", type=int, default=120, help="Posts per platform")
        parser.add_argument("--comments-min", type=int, default=4)
        parser.add_argument("--comments-max", type=int, default=22)
        parser.add_argument("--days", type=int, default=180, help="Window (days back) for published_at")
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument("--replace", action="store_true", help="Delete this user's demo data first")
        parser.add_argument("--no-sentiment", action="store_true", help="Skip sentiment classification")
        parser.add_argument("--transformer", action="store_true", help="Try XLM-RoBERTa (needs transformers+torch)")

    def handle(self, *args, **options) -> None:
        User = get_user_model()
        try:
            user = User.objects.get(email=options["email"])
        except User.DoesNotExist:
            raise CommandError(f"No user with email {options['email']}. Run `create_demo_user` first.")

        gen = DemoDataGenerator(
            seed=options["seed"],
            prefer_transformer=options["transformer"],
        )

        start = time.perf_counter()
        stats = gen.seed(
            user,
            posts_per_platform=options["posts"],
            comments_per_post_range=(options["comments_min"], options["comments_max"]),
            days_back=options["days"],
            analyze_sentiment=not options["no_sentiment"],
            replace=options["replace"],
        )
        elapsed = time.perf_counter() - start

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {user.email}: "
            f"{stats.accounts} accounts · {stats.posts} posts · {stats.comments} comments · "
            f"{stats.sentiments} sentiments ({stats.model_name})  "
            f"[{elapsed:.1f}s]"
        ))
