"""Development settings — local machine, hot reload, verbose errors."""
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True
ALLOWED_HOSTS = ["*"]  # Permissive for dev; prod tightens this.

SECRET_KEY = env("SECRET_KEY", default="dev-secret-key-not-for-production-use")

# SQLite for dev speed; override by setting DATABASE_URL=postgres://... in .env
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

# Console email backend — prints to runserver stdout
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Dev tooling: debug_toolbar + extensions (import guarded — optional)
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar", "django_extensions"]
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.common.CommonMiddleware") + 1,
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
    INTERNAL_IPS = ["127.0.0.1", "localhost"]
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda _: DEBUG}
except ImportError:
    pass

# Allow CORS from local Vite/Node dev servers
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
]

# Relax allauth email verification in dev (console backend can't really "send")
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"
