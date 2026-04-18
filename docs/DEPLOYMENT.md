# Deployment (Railway)

> **Status:** Phase 9 fazasida to'ldiriladi. Bu fayl hozirgi skeleton holatida qo'llanma sifatida skelet.

## 1. Railway'da loyihani sozlash

1. [railway.app](https://railway.app) — GitHub bilan kirish
2. **New Project → Deploy from GitHub repo** → `social-media-analytics` repo tanlash
3. Managed addon'larni qo'shish:
   - **PostgreSQL** (avtomatik `DATABASE_URL` beradi)
   - **Redis** (avtomatik `REDIS_URL` beradi)

## 2. Service'larni yaratish

Railway'da bir xil repo'dan 3 ta alohida servis:

| Servis | Start command (Railway dashboard'da override) |
|--------|-----------------------------------------------|
| `web` | (default — `railway.toml`dan olinadi) |
| `worker` | `celery -A config worker -l info -Q default,collectors,analytics` |
| `beat` | `celery -A config beat -l info` |

> **Muhim:** `beat` servisi **faqat 1 instance** bo'lishi kerak (scheduler duplicate'ga yo'l qo'ymaydi).

## 3. Env var'lar (majburiy)

Railway dashboard → Project → Variables:

```
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(64))">
ALLOWED_HOSTS=your-domain.up.railway.app,your-custom-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.up.railway.app,https://your-custom-domain.com

ENCRYPTION_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# OAuth
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_SECRET=...
META_APP_ID=...
META_APP_SECRET=...
META_REDIRECT_URI=https://your-domain/social/callback/instagram/

# Telegram (platform fallback bot)
TELEGRAM_BOT_TOKEN=...

# Email (SendGrid)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<sendgrid-api-key>
DEFAULT_FROM_EMAIL=noreply@your-domain.com

# Observability
SENTRY_DSN=https://...@sentry.io/...

# Sentiment — prod uses HF Inference API (no torch in Docker slim)
SENTIMENT_BACKEND=api
HF_API_TOKEN=hf_...
```

## 4. Migration + superuser

Birinchi deploy'dan keyin:

```bash
# Railway CLI bilan (yoki dashboard'dagi "Shell" orqali)
railway run --service web python manage.py migrate
railway run --service web python manage.py createsuperuser
railway run --service web python manage.py compilemessages
```

> `release` komandasi `Procfile`'dan avtomatik migrate qiladi — lekin `compilemessages` qo'lda kerak.

## 5. Custom domen

1. Railway → Service → Settings → Domains → Add Custom Domain
2. CNAME yozuvini DNS provider'da yarating (`your-domain.com → xxx.up.railway.app`)
3. `ALLOWED_HOSTS` va `CSRF_TRUSTED_ORIGINS`'ga yangi domen qo'shing

## 6. Monitoring

- **Sentry** — `SENTRY_DSN` o'rnatilgach, hamma xato avtomatik jo'natiladi
- **Railway logs** — dashboard'dagi "Logs" tab'i orqali real-time
- **Celery flower** (ixtiyoriy) — ayrim servis sifatida `flower -A config`

## 7. Backups

- PostgreSQL — Railway managed addon kunlik backup qiladi (7 kun retention default)
- Qo'lda dump: `railway run pg_dump $DATABASE_URL > backup.sql`

---

**To'liq checklist** (Phase 9): uptime monitoring, staging env, blue-green deploy, cost alerts.
