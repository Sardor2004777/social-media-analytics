# Social Analytics

**Ijtimoiy tarmoq foydalanuvchilari faoliyatini tahlil qilish axborot tizimi**

Production-ready ijtimoiy tarmoq analitika platformasi. Foydalanuvchilar o'z Instagram, Telegram, YouTube va X (Twitter) akkauntlarini ulab, faollik dinamikasi, kontent samaradorligi, obunachilar o'sishi va sentiment tahlil hisobotlarini olishi mumkin.

---

## 📋 Texnologiyalar

- **Backend:** Python 3.11+, Django 5.2 LTS + DRF
- **DB:** PostgreSQL 16 (prod), SQLite (dev)
- **Background:** Celery 5.4 + Redis 7
- **Frontend:** Django templates + Tailwind CSS + Alpine.js + HTMX + Chart.js
- **ML:** HuggingFace `cardiffnlp/twitter-xlm-roberta-base-sentiment` (multilingual sentiment)
- **Export:** WeasyPrint (PDF), openpyxl (Excel)
- **Deploy:** Docker + Railway
- **i18n:** O'zbek (lotin), Rus, Ingliz — Django gettext

---

## 🚀 Tezkor ishga tushirish (Docker)

```bash
# 1. .env faylini yarating
cp .env.example .env
# Keyin .env ichidagi qiymatlarni to'ldiring (SECRET_KEY, GOOGLE_OAUTH_*, va h.k.)

# 2. Konteynerlarni ko'taring
docker compose up --build

# 3. Migratsiya va superuser
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser

# 4. Brauzerda oching
# http://localhost:8000/         — bosh sahifa
# http://localhost:8000/admin/   — Django admin
# http://localhost:8000/api/v1/docs/ — Swagger UI
```

## 🛠 Lokal (Docker'siz) ishga tushirish

Qurilma bilan to'g'ridan-to'g'ri ishlash uchun:

```bash
# Virtual muhit
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
.venv\Scripts\activate             # Windows

# Bog'liqliklar
pip install -r requirements/dev.txt

# Migratsiya
python manage.py migrate

# Ishga tushirish
python manage.py runserver
# Boshqa terminalda:
celery -A config worker -l info
celery -A config beat -l info
```

> **Eslatma:** Lokal rejimda Redis alohida ishlatilishi kerak (`redis-server` yoki Docker).

---

## 📁 Loyiha strukturasi

```
social-analytics/
├── config/          # Django settings (base/dev/prod/test), celery, urls
├── apps/
│   ├── core/        # Shared utilities, base models
│   ├── accounts/    # Custom User, Profile, allauth
│   ├── social/      # SocialAccount + OAuth flows
│   ├── collectors/  # Platform collectors + Celery tasks
│   ├── analytics/   # Metrics, aggregation, sentiment
│   ├── dashboard/   # UI views + HTMX partials
│   ├── reports/     # PDF/Excel generators
│   └── api/         # DRF viewsets + JWT + Swagger
├── locale/          # i18n .po/.mo files (uz, ru, en)
├── static/          # CSS, JS, images
├── templates/       # Django templates
├── tests/           # Cross-app integration tests
├── docs/            # ARCHITECTURE, API, DEPLOYMENT, DATA_MODEL
└── requirements/    # base.txt, dev.txt, prod.txt
```

To'liq arxitektura: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🧪 Testlar

```bash
pytest                                    # Barcha testlar
pytest apps/accounts/                     # Bitta app
pytest -m "not slow"                      # Slow'siz
pytest --cov=apps --cov-report=html       # Coverage HTML
```

Target coverage: **≥70%**

---

## 🎨 Kod sifati

```bash
ruff check .              # Lint
ruff check --fix .        # Avtomatik tuzatish
black .                   # Format
pre-commit run --all-files
```

---

## 🌐 Tillar

UI uch tilda: **O'zbek (lotin)** (default), **Rus**, **Ingliz**. Navbar'dagi til tanlash orqali almashtiriladi. Tarjima fayllari `locale/` ichida.

```bash
# Yangi tarjima string'larini yig'ish
python manage.py makemessages -l uz -l ru -l en

# Tarjimalarni kompilyatsiya qilish
python manage.py compilemessages
```

---

## 📊 Rivojlanish fazalari

Loyiha 9 bosqichda quriladi:

1. ✅ **Rejalashtirish** — arxitektura, qarorlar
2. ✅ **Skeleton** — loyiha strukturasi, Docker, CI, custom User + migration
3. ⏳ Auth (accounts + allauth to'liq, profil, email verification)
4. ⏳ Social + Collectors (IG + TG OAuth, Celery tasks)
5. ⏳ Analytics core (agregat modellar, sentiment pipeline)
6. ⏳ Dashboard UI (HTMX + Chart.js)
7. ⏳ Sentiment (XLM-RoBERTa) + Reports (PDF/Excel)
8. ⏳ REST API + Swagger (DRF viewsets)
9. ⏳ Yakuniy tozalash + production deploy (coverage ≥70%, Tailwind build, seed data)

---

## 📚 Hujjatlar

| Fayl | Mazmuni |
|------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Tizim arxitekturasi, komponentlar, ma'lumot oqimlari |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Model'lar, ERD, migration strategiyasi |
| [docs/API.md](docs/API.md) | REST API, JWT, endpoint'lar |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Railway setup, env var'lar, monitoring |
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | IG Business, TG bot, Meta App sozlash |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Lokal setup, testlar, kod stili |
| [docs/PUSH_INSTRUCTIONS.md](docs/PUSH_INSTRUCTIONS.md) | GitHub'ga push bosqichlari |

---

## 📄 Litsenziya

[MIT License](LICENSE) — akademik / ta'lim maqsadida. Diplom ishi doirasida ishlab chiqilmoqda.
