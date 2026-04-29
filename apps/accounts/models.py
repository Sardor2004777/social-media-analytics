"""Custom user model — implemented fully in Phase 3.

For Phase 2 skeleton we only need a minimal AbstractUser subclass so the rest
of Django (admin, allauth, migrations) can wire up against `accounts.User`.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.fields import EncryptedTextField


class User(AbstractUser):
    """Placeholder custom user — expanded in Phase 3."""

    email = models.EmailField(unique=True)

    # 2FA (TOTP) — secret is encrypted at rest with the same Fernet key as
    # OAuth tokens. Enabled flag is separate so a user can pre-generate the
    # secret, scan the QR, and only flip it on after a successful first
    # verification.
    totp_secret  = EncryptedTextField(blank=True, default="")
    totp_enabled = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta(AbstractUser.Meta):
        db_table = "accounts_user"

    def __str__(self) -> str:
        return self.email or self.username
