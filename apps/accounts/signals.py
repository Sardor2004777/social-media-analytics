"""Sign-up signal: seed every brand-new user with a small demo dataset.

Rationale: freshly-signed-up users hit /dashboard/ and see a dead, zero-KPI
page if no ConnectedAccount exists. That's the main "pages show nothing"
complaint we fix here: immediately after allauth fires ``user_signed_up``,
we generate a modest demo dataset (4 platforms × ~30 posts + comments +
sentiment) so the dashboard is already populated on first view.

The user can still connect their own handle on top of this — or disconnect
the demo accounts from ``/social/`` (each row has a Disconnect button).

Guarded by ``DEMO_SEED_ON_SIGNUP`` (default: True). Set the env var to 0
in prod to disable seeding for every signup (e.g. once you have real user
traffic).
"""
from __future__ import annotations

import logging
import os

from allauth.account.signals import user_signed_up
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def _log_login(sender, request, user, **kwargs) -> None:
    from apps.core.models import log_activity
    log_activity(user, "login", "Tizimga kirildi", request=request)


@receiver(user_logged_out)
def _log_logout(sender, request, user, **kwargs) -> None:
    from apps.core.models import log_activity
    if user is not None:
        log_activity(user, "logout", "Tizimdan chiqildi", request=request)


@receiver(user_signed_up)
def _log_signup(sender, request, user, **kwargs) -> None:
    from apps.core.models import log_activity
    log_activity(user, "login", "Ro'yxatdan o'tildi", request=request)


def _enabled() -> bool:
    raw = os.environ.get("DEMO_SEED_ON_SIGNUP", "1").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@receiver(user_signed_up)
def seed_on_signup(sender, request, user, **kwargs) -> None:
    """Populate a tiny demo graph so the dashboard isn't empty on first visit."""
    if not _enabled():
        return
    try:
        from apps.collectors.services.mock_generator import DemoDataGenerator
        gen = DemoDataGenerator(seed=user.id if user.id else None)
        stats = gen.seed(
            user,
            posts_per_platform=30,
            comments_per_post_range=(2, 6),
            days_back=90,
            analyze_sentiment=True,
            replace=False,
        )
        logger.info(
            "seed_on_signup: %s -> %d accounts, %d posts, %d comments (%s)",
            user.email, stats.accounts, stats.posts, stats.comments, stats.model_name,
        )
    except Exception as exc:
        # Never block signup on a seeding problem — user can always connect
        # manually via /social/.
        logger.warning("seed_on_signup failed for %s: %s", user.email, exc)
