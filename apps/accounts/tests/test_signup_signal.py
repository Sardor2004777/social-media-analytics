"""Verify the signup signal seeds a demo graph for each new user."""
from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.social.models import ConnectedAccount

pytestmark = pytest.mark.django_db


def test_signup_triggers_demo_seed(client: Client) -> None:
    """Posting the allauth signup form must create seed data for the user."""
    resp = client.post(
        reverse("account_signup"),
        data={
            "email": "signal-test@example.com",
            "password1": "GoodPassw0rd!",
            "password2": "GoodPassw0rd!",
        },
        follow=False,
    )
    # allauth redirects on success
    assert resp.status_code == 302

    from django.contrib.auth import get_user_model
    user = get_user_model().objects.get(email="signal-test@example.com")
    assert ConnectedAccount.objects.filter(user=user).exists(), (
        "user_signed_up signal did not seed demo data"
    )
