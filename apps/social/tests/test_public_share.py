"""Integration tests for the public share-link flow.

Covers:
  * :class:`PublicShareLink.create_for` generates unique tokens.
  * ``social:toggle_share`` requires login, POST, and ownership.
  * ``social:public_share`` is reachable unauthenticated for active links,
    404s otherwise.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.social.models import ConnectedAccount, Platform, PublicShareLink

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    User = get_user_model()
    u = User(username="share-user@example.com", email="share-user@example.com")
    u.set_password("x!23QWE123")
    u.save()
    return u


@pytest.fixture
def other_user():
    User = get_user_model()
    u = User(username="other-share@example.com", email="other-share@example.com")
    u.set_password("x!23QWE123")
    u.save()
    return u


@pytest.fixture
def account(user):
    return ConnectedAccount.objects.create(
        user=user,
        platform=Platform.TELEGRAM,
        external_id="ext-share-1",
        handle="durov",
        display_name="Pavel Durov",
        follower_count=100,
    )


# ---------- Model ----------

def test_create_for_generates_unique_tokens(account) -> None:
    a = PublicShareLink.create_for(account)
    b = PublicShareLink.create_for(account)
    assert a.token != b.token
    assert a.is_active is True
    assert b.is_active is True


def test_create_for_links_to_account(account) -> None:
    link = PublicShareLink.create_for(account)
    assert link.account == account
    assert len(link.token) >= 12


# ---------- toggle_share_link view ----------

def test_toggle_requires_login(client, account) -> None:
    resp = client.post(reverse("social:toggle_share", kwargs={"pk": account.pk}))
    assert resp.status_code in (302, 403)
    assert PublicShareLink.objects.count() == 0


def test_toggle_only_accepts_post(client, user, account) -> None:
    client.force_login(user)
    resp = client.get(reverse("social:toggle_share", kwargs={"pk": account.pk}))
    assert resp.status_code == 405


def test_toggle_creates_link_on_first_call(client, user, account) -> None:
    client.force_login(user)
    resp = client.post(reverse("social:toggle_share", kwargs={"pk": account.pk}))
    assert resp.status_code == 302
    assert PublicShareLink.objects.filter(account=account, is_active=True).count() == 1


def test_toggle_revokes_on_second_call(client, user, account) -> None:
    client.force_login(user)
    url = reverse("social:toggle_share", kwargs={"pk": account.pk})
    client.post(url)  # create
    client.post(url)  # revoke
    assert PublicShareLink.objects.filter(account=account, is_active=True).count() == 0
    assert PublicShareLink.objects.filter(account=account, is_active=False).count() == 1


def test_toggle_blocks_other_users_accounts(client, other_user, account) -> None:
    client.force_login(other_user)
    resp = client.post(reverse("social:toggle_share", kwargs={"pk": account.pk}))
    assert resp.status_code == 404
    assert PublicShareLink.objects.count() == 0


# ---------- public_share view ----------

def test_public_share_renders_for_active_link(client, account) -> None:
    link = PublicShareLink.create_for(account)
    resp = client.get(reverse("social:public_share", kwargs={"token": link.token}))
    assert resp.status_code == 200
    assert b"@durov" in resp.content


def test_public_share_404_for_inactive_link(client, account) -> None:
    link = PublicShareLink.create_for(account)
    link.is_active = False
    link.save()
    resp = client.get(reverse("social:public_share", kwargs={"token": link.token}))
    assert resp.status_code == 404


def test_public_share_404_for_missing_token(client) -> None:
    resp = client.get(reverse("social:public_share", kwargs={"token": "nonexistent-token"}))
    assert resp.status_code == 404


def test_public_share_does_not_require_auth(account) -> None:
    link = PublicShareLink.create_for(account)
    fresh = Client()
    resp = fresh.get(reverse("social:public_share", kwargs={"token": link.token}))
    assert resp.status_code == 200
