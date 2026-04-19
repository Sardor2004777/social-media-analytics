# Deploy qo'llanma — Render

Loyiha ayni paytda **Render**'da deploy qilingan:
https://social-media-analytics-9rre.onrender.com

Bu hujjat noldan Render deploy qilishni va mavjud deploy'ni boshqarishni
tushuntiradi.

---

## 1. Asosiy deploy (noldan)

### 1.1 Render akkauntini sozlash

1. [render.com](https://render.com) → GitHub orqali kirish.
2. **New → Web Service** → `social-media-analytics` repo'ni tanlang.
3. Environment: **Docker** tanlang (Python runtime emas).
4. Root directory: `/` (bo'sh qoldiring).
5. Branch: `main`.

### 1.2 Instance type

- Free tarifda **512 MB RAM** — VADER asosiy sentiment, XLM-RoBERTa yo'q.
- Starter/Standard uchun: transformers + torch qo'shish mumkin
  (`requirements/prod.txt`'ga `transformers`, `torch --index-url https://download.pytorch.org/whl/cpu` qo'shing).

### 1.3 Managed database

1. **New → PostgreSQL** (Free plan OK).
2. Databaseni web service bilan bog'lang (Internal URL avtomatik kopiyalanadi).

### 1.4 Environment variables (Render → Environment)

Talab qilinadigan:

| Nomi | Qiymat |
|---|---|
| `SECRET_KEY` | 50+ tasodifiy belgi (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) |
| `ALLOWED_HOSTS` | `social-media-analytics-9rre.onrender.com` (vergul bilan qo'shimcha) |
| `DATABASE_URL` | avtomatik Render PostgreSQL'dan |
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` (Dockerfile'da allaqachon o'rnatilgan, override kerak emas) |

Ixtiyoriy (lekin tavsiya etiladi):

| Nomi | Qiymat | Nima qiladi |
|---|---|---|
| `CSRF_TRUSTED_ORIGINS` | `https://social-media-analytics-9rre.onrender.com` | CSRF POST uchun |
| `SENTRY_DSN` | Sentry'dan DSN | Xato tracking |
| `AUTO_SEED_DEMO` | `1` | Birinchi deploy'da demo akkaunt + data avtomatik yaratadi |

Email (SendGrid ishlatish uchun):

| Nomi | Qiymat |
|---|---|
| `EMAIL_HOST` | `smtp.sendgrid.net` |
| `EMAIL_PORT` | `587` |
| `EMAIL_USE_TLS` | `True` |
| `EMAIL_HOST_USER` | `apikey` |
| `EMAIL_HOST_PASSWORD` | SendGrid API kalit (`SG.xxx...`) |
| `DEFAULT_FROM_EMAIL` | `noreply@sizning-domain.com` |

> **Email'ning default holati.** `EMAIL_HOST` o'rnatilmagan bo'lsa `prod.py`
> avtomatik **locmem** backendi'ga o'tadi — emailar xotirada yo'q qilinadi,
> lekin signup/password reset view'lari 500 xato bermaydi.
> `ACCOUNT_EMAIL_VERIFICATION` avtomatik `optional`'ga tushadi.

Google OAuth (Settings'dagi "Google orqali davom etish" tugmasi uchun):

| Nomi | Qiymat |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | Google Cloud Console'dan |
| `GOOGLE_OAUTH_SECRET` | ditto |

### 1.5 Deploy

1. **Manual Deploy → Deploy latest commit**.
2. Render avtomatik Docker build qiladi (taxminan 3-5 daqiqa):
   - `css-builder` stage (Node.js, Tailwind build)
   - `prod-builder` stage (pip install)
   - Final runtime image
3. `scripts/entrypoint.sh` avtomatik ishga tushadi:
   - `migrate` — DB schema
   - `collectstatic` — static fayllar
   - `ensure_demo_data` (agar `AUTO_SEED_DEMO=1`)
   - `gunicorn` — web server

---

## 2. Mavjud deploy'ni yangilash

`main` branch'ga push — Render avtomatik redeploy qiladi.

```bash
git add .
git commit -m "feat: new feature"
git push origin main
```

Render dashboard → **Events** bo'limida build progress ko'rinadi.

---

## 3. Muhim env var'lar

### `AUTO_SEED_DEMO=1` yoqish

Render → Environment → qo'shing.

Birinchi deploy'da `demo@social-analytics.app / Demo12345!` akkaunt + realistik
demo ma'lumot (4 akkaunt, ~320 post, ~4000 komment + sentiment) yaratadi.

**Idempotent**: agar user allaqachon mavjud bo'lsa yoki akkaunt bor bo'lsa,
qayta seed qilmaydi. Har deploy'da xavfsiz ishlaydi.

Seed tugagach, agar xohlasangiz var'ni `0` yoki olib tashlang — hech qanday
zarar yo'q.

### `SENTRY_DSN` qo'shish

1. [sentry.io](https://sentry.io) — loyiha yarating (Django platformasi).
2. DSN'ni nusxa oling.
3. Render → Environment → `SENTRY_DSN=https://xxx@yyy.ingest.sentry.io/zzz`.
4. Redeploy — xatolar Sentry'ga yuboriladi.

---

## 4. Ma'lumot bazasi amaliyotlari

### Superuser yaratish

Render → **Shell** (paid plans'da) yoki lokalda:

```bash
python manage.py createsuperuser
```

### Demo data qo'shish / tozalash

```bash
python manage.py ensure_demo_data          # idempotent
python manage.py seed_demo_data --replace  # force re-seed
python manage.py create_demo_user          # faqat user
```

### DB backup

Render PostgreSQL dashboard → **Backups** tab — avtomatik kundalik backup
(paid plans). Free tarifda `pg_dump`'ni qo'lda (Render Shell dan):

```bash
pg_dump $DATABASE_URL > backup-$(date +%Y%m%d).sql
```

---

## 5. Troubleshooting

### 1. Build crashes (Docker)

Build logs'ni tekshiring (Render → Events → latest build → logs):
- `pip install failed` — `requirements/prod.txt` sintaksisini tekshiring
- `npm install failed` — Node.js 20+ talab; Render Docker runtime'da
  avtomatik
- `tailwindcss command not found` — `package.json` "build:css" skript borligini
  tasdiqlang

### 2. 500 har sahifada

- `SECRET_KEY` o'rnatilmagan?
- `ALLOWED_HOSTS` serverdan URL'ni qamrab olmayapti?
- `DATABASE_URL` ulanmayapti? (Render DB o'chirib ketgan bo'lishi mumkin)

Render Logs'da to'liq traceback ko'rish mumkin.

### 3. Static fayl 404

Entrypoint `collectstatic --noinput --clear` ishga tushirmoqda. Agar
output.css hali ham 404:
- Docker build'da `css-builder` stage muvaffaqiyatli tugaganmi?
- Tailwind minified hajm ≥ 50 KB bo'lishi kerak

### 4. POST 500 (login, signup, password reset)

- `CSRF_TRUSTED_ORIGINS` o'rnatilganmi?
- `SECURE_PROXY_SSL_HEADER` Render uchun to'g'ri (`prod.py`'da allaqachon)
- Email backend sozlanganmi? (yo'q bo'lsa locmem ishga tushadi, 500 bermaydi)

---

## 6. Lokal dev'da deploy'ni simulyatsiya qilish

```bash
# Docker kerak (Desktop / Engine)
docker build -t social-analytics .
docker run -p 8000:8000 \
  -e SECRET_KEY=local-test \
  -e ALLOWED_HOSTS=localhost \
  -e DATABASE_URL=sqlite:///./db.sqlite3 \
  social-analytics
```

http://localhost:8000 — to'liq prod-simulyatsiya.

---

## 7. Alternativa: Railway

`railway.toml` hali ham qo'llanadi. Railway deploy uchun ko'rsatmalar
hujjat ichidagi avvalgi versiyasiga qarang yoki issue oching.

---

## 8. Audit skriptlari

Deploy'ni tezkor tekshirish:

```bash
# Anonim probe (17 URL + form POSTs)
python scripts/audit_live.py

# Authenticated probe (signup + 10 page crawl + exports + connect flow)
python scripts/audit_live_auth.py

# Lokal server'da
python scripts/audit_urls.py
```

Chiqish kodi 0 — toza, 1 — bir yoki ortiq muammo.
