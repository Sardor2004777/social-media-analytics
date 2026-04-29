"""TOTP (Time-based One-Time Password) helpers.

Thin wrapper around :mod:`pyotp` that generates secrets, builds the
otpauth URI for QR rendering on the client, and verifies 6-digit codes.

We do NOT call ``pyotp.qrcode`` server-side — instead the otpauth URI is
embedded in the settings page and rendered to a QR code via JS
(qrcode.js) so we don't need to push a binary image down to the user.
"""
from __future__ import annotations

import pyotp


ISSUER = "Social Analytics"


def new_secret() -> str:
    """Return a fresh base32 TOTP secret (160 bits)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_email: str) -> str:
    """Build the otpauth:// URI Google Authenticator and 1Password understand.

    The client embeds this in a QR; scanning it imports the secret with
    the right issuer + account label so the user sees ``Social Analytics
    (alice@example.com)`` in their authenticator.
    """
    if not secret:
        raise ValueError("secret is empty")
    return pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=ISSUER)


def verify(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """Return True iff ``code`` matches the current TOTP for ``secret``.

    ``valid_window=1`` accepts the previous and next 30-second window so
    a user typing a code as it rolls over isn't rejected. Returns False
    on missing inputs rather than raising — callers always treat False
    as "wrong code" anyway.
    """
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) not in (6, 8):
        return False
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=valid_window)
    except Exception:
        return False
