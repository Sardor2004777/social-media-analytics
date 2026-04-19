# syntax=docker/dockerfile:1.7
#
# Multi-stage Dockerfile for social-analytics.
# Stages:
#   - `css-builder` : runs Tailwind via Node 20 to produce static/css/output.css
#   - `dev`         : dev-deps + dev server, code mounted as volume via docker-compose
#   - `prod-builder`: installs prod Python deps into /root/.local
#   - `prod`        : slim runtime image for Render / Railway, gunicorn
#
# The CSS builder is a prerequisite for the prod image — the repo gitignores
# static/css/output.css so it would otherwise be missing at runtime and
# collectstatic would skip it.

# ============================================================================
# Stage: css-builder — compile Tailwind using the full template/app content
# ============================================================================
FROM node:20-slim AS css-builder

WORKDIR /app

# Install npm deps first so this layer caches across source edits.
# We use `npm install` (not `npm ci`) because package-lock.json is gitignored.
COPY package.json ./
RUN npm install --omit=optional --no-audit --no-fund --loglevel=error

# Tailwind JIT needs to scan templates + apps (per tailwind.config.js content[]).
COPY tailwind.config.js ./
COPY static/css/input.css ./static/css/input.css
COPY templates/ ./templates/
COPY apps/ ./apps/

RUN npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

# ============================================================================
# Stage: deps-base — shared Python system build tools
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

# Python packages
COPY --from=prod-builder --chown=app:app /root/.local /home/app/.local

# Source tree
COPY --chown=app:app . .

# Overlay the Tailwind CSS build (gitignored on the host, produced in css-builder).
# Must happen AFTER the full source copy so we don't get clobbered.
COPY --from=css-builder --chown=app:app /app/static/css/output.css /app/static/css/output.css

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
