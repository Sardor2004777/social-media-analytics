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
fi

echo "==> Starting: $@"
exec "$@"
