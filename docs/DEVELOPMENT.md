# Rivojlanish qo'llanmasi

## Lokal muhit

### Docker bilan (tavsiya etiladi)

```bash
cp .env.example .env
# .env ichidagi qiymatlarni to'ldiring, kamida SECRET_KEY

docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

- `http://localhost:8000/` — bosh sahifa
- `http://localhost:8000/admin/` — admin panel
- `http://localhost:8000/api/v1/docs/` — Swagger UI

### Virtualenv bilan (Docker'siz)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / Mac

pip install -r requirements/dev.txt

# Redis'ni alohida ishga tushiring (Docker yoki lokal o'rnatma)
python manage.py migrate
python manage.py runserver

# Boshqa terminalda (Celery uchun):
celery -A config worker -l info
celery -A config beat -l info
```

## Kod sifati

```bash
ruff check .              # Lint (auto-fix: --fix)
black .                   # Format (check-only: --check)
pre-commit install        # Commit'dan oldin tekshirish
pre-commit run --all-files
```

## Testlar

```bash
pytest                                # Barcha testlar
pytest apps/accounts/                 # Faqat bitta app
pytest -m "not slow"                  # Slow marker'larsiz
pytest --cov=apps --cov-report=html   # HTML coverage
pytest -x -vv                         # Birinchi xatoda to'xtash, verbose
```

Target coverage: **≥70%** (phase 9'da majburiy, oldingi phase'larda target).

## Migratsiyalar

```bash
python manage.py makemigrations <app_name>
python manage.py migrate
python manage.py showmigrations
```

## i18n

```bash
# Yangi string'larni chiqarib olish:
python manage.py makemessages -l uz -l ru -l en

# locale/*/LC_MESSAGES/django.po ni tahrirlang, keyin:
python manage.py compilemessages
```

## Celery

```bash
# Worker (default + collectors + analytics queue'lar)
celery -A config worker -l info -Q default,collectors,analytics

# Beat (scheduler) — faqat bitta instance
celery -A config beat -l info

# Manual task ishga tushirish:
python manage.py shell
>>> from config.celery import debug_task
>>> debug_task.delay()
```

## Commit'lar

Conventional Commits ishlatamiz:

```
feat(accounts): add custom User model
fix(social): handle expired IG token
docs(api): add JWT auth example
test(collectors): cover rate-limit retry
chore: bump django to 5.2.1
refactor(analytics): extract SentimentBackend
```

Har bosqich oxirida mustaqil commit. "WIP" commit'lar qabul qilinmaydi.
