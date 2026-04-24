"""Encrypted model fields (Fernet symmetric encryption at rest).

The DB column holds a Fernet ciphertext string; Python code sees plaintext.
Used for OAuth tokens on :class:`apps.social.models.ConnectedAccount` so an
attacker with read access to the database cannot immediately call partner
APIs on behalf of our users.

Requires ``settings.ENCRYPTION_KEY`` — generate with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = getattr(settings, "ENCRYPTION_KEY", "") or ""
    if not key:
        raise ImproperlyConfigured(
            "ENCRYPTION_KEY is empty. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and add it to .env."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """TextField that encrypts its value at rest via Fernet.

    Blank/None pass through unchanged so empty columns stay cheap. On read,
    values that fail decryption (legacy plaintext, key rotation) are returned
    as-is so the app never hard-crashes on stored data — rotate or wipe them
    out-of-band if that matters.
    """

    description = "Fernet-encrypted text"

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return value

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        return _fernet().encrypt(str(value).encode()).decode()
