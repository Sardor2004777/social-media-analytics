web: scripts/entrypoint.sh gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --access-logfile - --error-logfile -
worker: celery -A config worker -l info -Q default,collectors,analytics
beat: celery -A config beat -l info
release: python manage.py migrate --noinput
