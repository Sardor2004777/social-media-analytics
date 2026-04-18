"""Test settings — fast, isolated, deterministic.

- In-memory SQLite (no disk I/O between tests)
- Celery in eager mode (tasks run inline, no worker needed)
- MD5 password hasher (tests create users; bcrypt is too slow)
- Local-memory email backend
"""
from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = "test-secret-key-not-for-any-real-use"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

# Celery: run tasks synchronously
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Fast hasher — tests create many users
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Email stored in memory (inspect with django.core.mail.outbox)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# No email verification gate during tests
ACCOUNT_EMAIL_VERIFICATION = "none"

# Throttles off (don't want throttling to affect test outcomes)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"user": None, "anon": None},
}

# Static storage without manifest (tests don't run collectstatic)
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
