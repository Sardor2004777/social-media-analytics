#!/bin/sh
# Entrypoint for prod container. Runs migrations + collectstatic, then execs
# the passed CMD (gunicorn / celery / etc.).
set -e

echo "==> Running database migrations"
python manage.py migrate --noinput

# Only collect static for the web server. Worker/beat don't need it.
if echo "$@" | grep -q "gunicorn"; then
    echo "==> Collecting static files"
    python manage.py collectstatic --noinput --clear

    # Opt-in demo seed for the deployed dashboard. Safe to leave on — the
    # command is idempotent: creates demo@social-analytics.app only if missing,
    # and skips seeding if the user already has ConnectedAccount rows.
    if [ "${AUTO_SEED_DEMO}" = "1" ] || [ "${AUTO_SEED_DEMO}" = "true" ]; then
        echo "==> Ensuring demo data"
        python manage.py ensure_demo_data || echo "(demo seed skipped)"
    fi
fi

echo "==> Starting: $@"
exec "$@"
