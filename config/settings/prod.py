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
# Email — SMTP (SendGrid / Mailgun / etc.)
# ==============================================================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

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
