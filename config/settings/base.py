"""Base settings — shared across dev / prod / test.

Environment-specific modules (dev.py, prod.py, test.py) override only what differs.
All environment-dependent values are loaded from ``.env`` via django-environ.
"""
from datetime import timedelta
from pathlib import Path

import environ

# ==============================================================================
# Paths + environment
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    REDIS_URL=(str, "redis://localhost:6379/0"),
    CELERY_BROKER_URL=(str, "redis://localhost:6379/1"),
    CELERY_RESULT_BACKEND=(str, "redis://localhost:6379/2"),
    SENTIMENT_BACKEND=(str, "local"),
    SENTIMENT_MODEL=(str, "cardiffnlp/twitter-xlm-roberta-base-sentiment"),
    COLLECT_INTERVAL_HOURS=(int, 6),
    API_THROTTLE_USER=(str, "1000/day"),
    API_THROTTLE_ANON=(str, "100/day"),
)

# Read .env if present (no-op in prod where vars come from environment)
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ==============================================================================
# Applications
# ==============================================================================
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.social",
    "apps.collectors",
    "apps.analytics",
    "apps.dashboard",
    "apps.reports",
    "apps.api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

SITE_ID = 1

# ==============================================================================
# Middleware
# ==============================================================================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ==============================================================================
# Templates
# ==============================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ==============================================================================
# Database (overridden in dev/prod/test)
# ==============================================================================
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# ==============================================================================
# Password validation
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==============================================================================
# Authentication (allauth + custom user)
# ==============================================================================
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# allauth
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_EMAIL_NOTIFICATIONS = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "APP": {
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": env("GOOGLE_OAUTH_SECRET", default=""),
            "key": "",
        },
    },
}

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

# ==============================================================================
# i18n / L10n / Timezone
# ==============================================================================
LANGUAGE_CODE = "uz"

LANGUAGES = [
    ("uz", "O'zbekcha"),
    ("ru", "Русский"),
    ("en", "English"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# ==============================================================================
# Static & media
# ==============================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==============================================================================
# REST framework
# ==============================================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": env("API_THROTTLE_USER"),
        "anon": env("API_THROTTLE_ANON"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Social Analytics API",
    "DESCRIPTION": "REST API for social media analytics platform",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+/",
}

# ==============================================================================
# Celery
# ==============================================================================
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ROUTES = {
    "apps.collectors.tasks.*": {"queue": "collectors"},
    "apps.analytics.tasks.*": {"queue": "analytics"},
}
CELERY_TASK_DEFAULT_QUEUE = "default"

# ==============================================================================
# CORS (dev is permissive; prod tightens via env)
# ==============================================================================
CORS_ALLOWED_ORIGINS: list[str] = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# ==============================================================================
# App-specific
# ==============================================================================
# Fernet key for SocialAccount.access_token encryption-at-rest
ENCRYPTION_KEY = env("ENCRYPTION_KEY", default="")

# Sentiment backend: "local" (transformers) | "api" (HF Inference API)
SENTIMENT_BACKEND = env("SENTIMENT_BACKEND")
SENTIMENT_MODEL = env("SENTIMENT_MODEL")
HF_API_TOKEN = env("HF_API_TOKEN", default="")

# How often collectors run (Celery Beat)
COLLECT_INTERVAL_HOURS = env("COLLECT_INTERVAL_HOURS")

# OAuth — Instagram (Meta Graph API)
META_APP_ID = env("META_APP_ID", default="")
META_APP_SECRET = env("META_APP_SECRET", default="")
META_REDIRECT_URI = env(
    "META_REDIRECT_URI",
    default="http://localhost:8000/social/callback/instagram/",
)

# Telegram platform-level fallback bot (per-account tokens stored on SocialAccount)
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")

# Telegram MTProto (Telethon) real-mode — reads any public channel by @username
# using a server-side user session. All three must be set for real mode;
# otherwise Telegram falls back to the demo seeder.
TELEGRAM_API_ID = env("TELEGRAM_API_ID", default="")
TELEGRAM_API_HASH = env("TELEGRAM_API_HASH", default="")
TELEGRAM_SESSION_STRING = env("TELEGRAM_SESSION_STRING", default="")

# OpenAI — powers /analytics/chat/ and the weekly digest email. Leave
# OPENAI_API_KEY blank to hide the chat feature. Default model is gpt-4o-mini
# (cheapest good-enough tier). OPENAI_BASE_URL lets you route through a proxy
# or an OpenAI-compatible gateway (Azure, Groq, etc.).
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o-mini")
OPENAI_MAX_TOKENS = env.int("OPENAI_MAX_TOKENS", default=1024)
OPENAI_DIGEST_MAX_TOKENS = env.int("OPENAI_DIGEST_MAX_TOKENS", default=800)
OPENAI_BASE_URL = env("OPENAI_BASE_URL", default="")
OPENAI_ORGANIZATION = env("OPENAI_ORGANIZATION", default="")

# YouTube / X
YOUTUBE_API_KEY = env("YOUTUBE_API_KEY", default="")
YOUTUBE_OAUTH_CLIENT_ID = env("YOUTUBE_OAUTH_CLIENT_ID", default="")
YOUTUBE_OAUTH_SECRET = env("YOUTUBE_OAUTH_SECRET", default="")
X_CLIENT_ID = env("X_CLIENT_ID", default="")
X_CLIENT_SECRET = env("X_CLIENT_SECRET", default="")

# ==============================================================================
# Email (overridden per env)
# ==============================================================================
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# ==============================================================================
# Logging
# ==============================================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}:{lineno} — {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
