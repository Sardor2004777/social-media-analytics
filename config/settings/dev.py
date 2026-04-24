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

# File-based email backend in dev. The console backend would otherwise crash
# when any email (e.g. allauth verification) contains Unicode outside cp1251 —
# runserver stdout on Windows is locked to the console code page and can't
# encode characters like the Uzbek modifier apostrophe (\u02bb).
# Emails land as plain-text files under .dev_emails/ so we can still inspect
# them without burning the whole signup flow.
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = BASE_DIR / ".dev_emails"
EMAIL_FILE_PATH.mkdir(exist_ok=True)

# Dev tooling: debug_toolbar + extensions (import guarded — optional)
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar", "django_extensions"]
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.common.CommonMiddleware") + 1,
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
    INTERNAL_IPS = ["127.0.0.1", "localhost"]
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda r: DEBUG and r.META.get("REMOTE_ADDR") in INTERNAL_IPS,
        "SHOW_COLLAPSED": True,
        "RESULTS_CACHE_SIZE": 3,
        # Don't hijack 3xx responses — without this the toolbar replaces every
        # redirect with its own intercept page (renders as ~13KB),
        # which breaks plain flows like `/` -> `/dashboard/`.
        "DISABLE_PANELS": {
            "debug_toolbar.panels.redirects.RedirectsPanel",
            "debug_toolbar.panels.profiling.ProfilingPanel",
        },
    }
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

# Run Celery tasks inline in dev so you don't need a local Redis + worker
# just to click "Connect YouTube". Prod still uses the real async queue.
# Set CELERY_TASK_ALWAYS_EAGER=false in .env if you want to test the real broker.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)
CELERY_TASK_EAGER_PROPAGATES = True
