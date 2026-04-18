# syntax=docker/dockerfile:1.7
#
# Multi-stage Dockerfile for social-analytics.
# Targets:
#   - `dev`  : dev-deps + dev server, code mounted as volume via docker-compose
#   - `prod` : slim runtime image for Railway / Render, gunicorn
#
# Phase 7 (sentiment + reports) will extend runtime with WeasyPrint system libs
# (libcairo2, libpango-1.0-0, libpangoft2-1.0-0, fonts) and transformers+torch.

# ============================================================================
# Stage: deps-base — shared system build tools
# ============================================================================
FROM python:3.11-slim AS deps-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ============================================================================
# Stage: dev — full dev toolchain; code mounted as volume at runtime
# ============================================================================
FROM deps-base AS dev

COPY requirements/ ./requirements/
RUN pip install --upgrade pip \
    && pip install -r requirements/dev.txt

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ============================================================================
# Stage: prod-builder — install prod deps into /root/.local
# ============================================================================
FROM deps-base AS prod-builder

COPY requirements/ ./requirements/
RUN pip install --upgrade pip \
    && pip install --user -r requirements/prod.txt

# ============================================================================
# Stage: prod — slim runtime image
# ============================================================================
FROM python:3.11-slim AS prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/app/.local/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        gettext \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r app \
    && useradd -r -g app -m -d /home/app app

WORKDIR /app

COPY --from=prod-builder --chown=app:app /root/.local /home/app/.local
COPY --chown=app:app . .

RUN mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app/staticfiles /app/media \
    && chmod +x scripts/entrypoint.sh

USER app

EXPOSE 8000

ENTRYPOINT ["scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
