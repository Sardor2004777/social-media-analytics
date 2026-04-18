# Arxitektura

Ushbu hujjat Social Analytics loyihasining yuqori darajadagi arxitekturasini, komponentlar orasidagi aloqalarni va kritik qarorlarni tavsiflaydi.

## 1. Tizim umumiy ko'rinishi

```
┌────────────────────────────────────────────────────────────────────────┐
│                          BROWSER (User)                                │
│  ┌────────────────────────┐        ┌──────────────────────────┐        │
│  │ Django templates       │        │ HTMX / Alpine.js         │        │
│  │ (Tailwind styled)      │◄──────►│ (partial updates)        │        │
│  └────────────────────────┘        └──────────────────────────┘        │
└────────────────────┬───────────────────────────────────────────────────┘
                     │ HTTPS
┌────────────────────▼───────────────────────────────────────────────────┐
│                 DJANGO WEB SERVICE (gunicorn, Railway)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ apps/accounts│  │ apps/social  │  │ apps/dashboard (HTMX views)  │  │
│  │  (allauth)   │  │  (OAuth)     │  │                              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ apps/reports │  │ apps/api     │  │ drf-spectacular Swagger UI   │  │
│  │  (downloads) │  │ (DRF + JWT)  │  │                              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
└──────────┬───────────────────┬────────────────────────┬────────────────┘
           │                   │                        │
           ▼                   ▼                        ▼
    ┌──────────────┐     ┌────────────┐         ┌───────────────┐
    │  PostgreSQL  │     │   Redis    │         │  External APIs│
    │  (Railway)   │     │  (Railway) │         │  Meta Graph   │
    └──────────────┘     │  broker +  │         │  Telegram Bot │
                         │  cache     │         │  YouTube v3   │
                         └─────▲──────┘         │  X API v2     │
                               │                │  HF Inference │
                               │ tasks          └───────▲───────┘
                    ┌──────────┴─────────┐              │
                    │                    │              │
              ┌─────▼──────┐      ┌──────▼──────┐       │
              │ CELERY     │      │ CELERY      │       │
              │ worker     │      │ worker      ├───────┘
              │ (collectors│      │ (analytics: │
              │  queue)    │      │  sentiment) │
              └────────────┘      └─────────────┘
                    ▲
                    │
              ┌─────┴──────┐
              │ CELERY     │
              │ beat       │
              │ (scheduler)│
              └────────────┘
```

## 2. App'lar va ularning mas'uliyati

| App | Mas'uliyat | Asosiy modellar | Asosiy route'lar |
|-----|-----------|-----------------|------------------|
| **core** | Umumiy utilities (TimestampedModel, shifrlash, logger) | `TimestampedModel` (abstract) | — |
| **accounts** | Foydalanuvchi, autentifikatsiya, profil | `User` (AbstractUser), `Profile` | `/accounts/*` (allauth), `/profile/` |
| **social** | Ijtimoiy akkauntlarni ulash, OAuth | `SocialAccount`, `ConnectionAttempt` | `/social/connect/<platform>/`, `/social/callback/<platform>/` |
| **collectors** | Real API'lardan ma'lumot yig'ish (Celery) | `RawPost`, `RawComment`, `RawFollowerSnapshot` | — (background) |
| **analytics** | Agregatsiya, metrikalar, sentiment | `DailyAccountMetric`, `HourlyActivityBucket`, `PostPerformance`, `SentimentAggregate` | — |
| **dashboard** | Foydalanuvchi UI, grafiklar, KPI | (model yo'q) | `/`, `/dashboard/partials/*` |
| **reports** | PDF / Excel hisobot yaratish | `Report` | `/reports/`, `/reports/<id>/download/` |
| **api** | REST API (JWT + Swagger) | (serializer orqali boshqa app'lar modellari) | `/api/v1/*` |

## 3. Ma'lumotlar oqimlari

### 3.1 OAuth ulanish (Instagram misolida)

```
User → "Instagram ulash" tugmasi → /social/connect/instagram/
   → Meta auth URL + state token generatsiya → Redirect
   → User Meta'da ruxsat beradi
   → Meta → /social/callback/instagram/?code=...&state=...
   → services/oauth/instagram.exchange_code_for_token(code)
   → Long-lived token (60 kun)
   → SocialAccount.objects.create(token=Fernet.encrypt(access_token))
   → ConnectionAttempt log: success
   → Dashboard'ga redirect
```

### 3.2 Ma'lumot yig'ish (har 6 soatda)

```
Celery Beat → schedule_all_collections.delay()
   → SocialAccount.objects.filter(status="active") loop
      → collect_account_data.delay(account_id)  [queue: collectors]
   → Worker (collectors queue) pick:
      → BaseCollector.run()
      → IG Graph API / TG Bot API chaqirish
      → RawPost / RawComment / RawFollowerSnapshot saqlash
      → compute_daily_aggregates.delay(...)   [queue: analytics]
      → compute_post_sentiment.delay(...)     [queue: analytics]
   → Analytics worker:
      → Daily rollup yoziladi
      → Sentiment modeli orqali postlar tahlili
      → Dashboard cache invalidate (Redis)
```

### 3.3 Dashboard HTMX oqim

```
/ → base page (skeleton, loading states)
  → HTMX (hx-get) → /dashboard/partials/kpi/?account_id=X&from=...&to=...
     → KpiPartialView → DailyAccountMetric query
     → partial HTML fragment qaytadi (Chart.js data-attrlar bilan)
  → Alpine.js date-picker → URL update → HTMX re-fetch
```

### 3.4 Sentiment pipeline

```
Yangi RawComment → compute_post_sentiment.delay(post_id)
  → SentimentBackend.analyze(texts):
     - "local"  → XLM-RoBERTa (transformers + torch, CPU)
     - "api"    → HF Inference API POST
  → PostPerformance.sentiment_{label,score} yangilanadi
  → Kunlik SentimentAggregate rollup
```

## 4. Kritik arxitektura qarorlari

### 4.1 Real API + OAuth — mock yo'q
Soxta ma'lumot generator yozilmaydi. Instagram Graph API (Business account talab) + Telegram Bot API (bot admin bo'lishi kerak) asosida ishlanadi. Qarorning asosi: user tanlovi + diplom sifati uchun "haqiqiy ishlaydigan" tizim muhim.

### 4.2 Sentiment — distilled multilingual transformer
`cardiffnlp/twitter-xlm-roberta-base-sentiment` (~278MB) 50+ tilda ishlaydi — O'zbek, rus, ingliz hammasi qamrovga kiradi. To'liq XLM-RoBERTa (~500MB) Railway 512MB tierga sig'maydi.

Abstraksiya: `SentimentBackend` interface ikki implementation bilan:
- `LocalTransformerBackend` — dev uchun, lokal inference
- `HFInferenceAPIBackend` — prod uchun, remote API (model hosting tashqarida)

`SENTIMENT_BACKEND` env var'i orqali almashtiriladi.

### 4.3 i18n — faqat UI chrome
`gettext` orqali 3 tilli (uz/ru/en) UI string'lar. User-generated kontent (post matni, kommentlar) asl tilda saqlanadi va shunday tahlil qilinadi. `django-modeltranslation` ishlatilmaydi.

### 4.4 Token shifrlash
OAuth access/refresh tokenlar DB'da Fernet (`cryptography` kutubxonasi) bilan shifrlab saqlanadi. Kalit `ENCRYPTION_KEY` env var'da. DB dump/backup tokenlar to'g'ridan-to'g'ri ochilmasligiga olib keladi.

### 4.5 Dual auth stack
- **Web UI:** Django session + allauth cookie-based auth (CSRF bilan himoyalangan)
- **REST API:** JWT (`djangorestframework-simplejwt`) — stateless, mobile/external client uchun mos

### 4.6 Pre-computed agregatlar
Dashboard query'lari tez bo'lishi uchun `DailyAccountMetric`, `HourlyActivityBucket` kabi agregat modellar raw ma'lumotlardan pre-compute qilinadi. Raw `RawPost`/`RawComment` source of truth bo'lib qoladi.

### 4.7 Celery queue ajratish
- `default` — umumiy task'lar
- `collectors` — API poll (past priority, uzun davomlik)
- `analytics` — aggregation + sentiment (yuqori priority, CPU/ML)

Sentiment ML Instagram poll'ni block qilmaydi.

## 5. Deployment topologiyasi (Railway)

Railway'da 3 alohida service + 2 managed addon:

| Service | Start command | Scale |
|---------|---------------|-------|
| `web` | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2` | 1+ instance |
| `worker` | `celery -A config worker -l info -Q default,collectors,analytics` | 1+ instance |
| `beat` | `celery -A config beat -l info` | **1 only** (scheduler) |
| PostgreSQL | Railway addon | managed |
| Redis | Railway addon | managed |

Har 3 service bir xil Docker image'ni ishlatadi, faqat CMD boshqacha.

Production env var'lar Railway dashboard'da o'rnatiladi (SECRET_KEY, ALLOWED_HOSTS, META_*, GOOGLE_OAUTH_*, SENTRY_DSN, va h.k.).

## 6. Xavfsizlik

- SECRET_KEY, barcha API kalitlar .env'da. Hech qachon git'ga commit qilinmaydi.
- CSRF, XSS himoyasi Django default sozlamalari bilan.
- Prod SSL redirect, HSTS 1 yil, secure cookies.
- Rate limiting — `DRF throttle` (user: 1000/day, anon: 100/day).
- Token encryption at rest (Fernet).
- Django ORM ishlatiladi — SQL injection'dan avtomatik himoyalangan.

## 7. Hujjatlar (boshqa fayllar)

| Fayl | Mazmuni |
|------|---------|
| [DATA_MODEL.md](DATA_MODEL.md) | ERD, field'lar, indeks'lar (Phase 4'dan keyin) |
| [API.md](API.md) | REST endpoint'lar, JWT auth, misollar (Phase 8) |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Railway setup, env var'lar, monitoring (Phase 9) |
| [ONBOARDING.md](ONBOARDING.md) | IG Business account, TG bot yaratish, Meta App sozlash (Phase 4) |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Lokal setup, testlar, kod stili |
