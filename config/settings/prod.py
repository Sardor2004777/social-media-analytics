"""Production settings — Railway / Render deploy target.

Reads everything sensitive from environment variables. Fails loudly if required
values are missing.
"""
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# Required in prod — do not provide a default
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Postgres in prod (Railway/Render provide DATABASE_URL)
DATABASES = {
    "default": env.db("DATABASE_URL"),
}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# ==============================================================================
# Security headers
# ==============================================================================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# CSRF trusted origins (Railway provides its subdomain via env)
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[f"https://{host}" for host in ALLOWED_HOSTS if host not in ("*", "localhost")],
)

# ==============================================================================
# Email — SMTP when configured, otherwise a non-failing in-memory backend so a
# bare deploy (no mail credentials yet) doesn't 500 every signup / password
# reset when Django tries to reach localhost:25 by default.
#
# To enable real email (SendGrid, Mailgun, Gmail, …), set EMAIL_HOST in the
# deploy environment together with EMAIL_HOST_USER / EMAIL_HOST_PASSWORD.
# ==============================================================================
if env("EMAIL_HOST", default=""):
    EMAIL_BACKEND       = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST          = env("EMAIL_HOST")
    EMAIL_PORT          = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER     = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS       = env.bool("EMAIL_USE_TLS", default=True)
    DEFAULT_FROM_EMAIL  = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")
else:
    # Non-failing fallback. Views that send mail keep working; the message is
    # discarded into django.core.mail.outbox instead of crashing.
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    # Drop verification to optional so the signup flow doesn't lock users out
    # while email is unconfigured.
    ACCOUNT_EMAIL_VERIFICATION = "optional"

# ==============================================================================
# Observability — Sentry
# ==============================================================================
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment=env("SENTRY_ENVIRONMENT", default="production"),
        release=env("GIT_COMMIT_SHA", default="unknown"),
    )
