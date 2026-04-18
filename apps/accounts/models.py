"""Custom user model — implemented fully in Phase 3.

For Phase 2 skeleton we only need a minimal AbstractUser subclass so the rest
of Django (admin, allauth, migrations) can wire up against `accounts.User`.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Placeholder custom user — expanded in Phase 3."""

    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta(AbstractUser.Meta):
        db_table = "accounts_user"

    def __str__(self) -> str:
        return self.email or self.username
