# Diplom himoyasi uchun tayyorgarlik

Bu hujjat komissiya savollariga aniq, qisqa javoblar beradi. Har bir bo'lim
real kod joylashuviga havola qiladi — namoyish paytida to'g'ridan-to'g'ri
ko'rsata olasiz.

---

## 1. Loyiha nima qiladi?

Social Analytics — ijtimoiy tarmoq (Instagram, Telegram, YouTube, X) postlari
va kommentlarini yig'adigan, sentiment tahlilini (AI model orqali) bajaradigan
va PDF/Excel hisobotlarga aylantiradigan to'laqonli web platforma.

**Live:** https://social-media-analytics-9rre.onrender.com
**GitHub:** https://github.com/Sardor2004777/social-media-analytics

---

## 2. Texnologiyalar to'plami

| Qatlam | Vositalar |
|---|---|
| Backend | Python 3.12, Django 5.2, Django REST Framework |
| Frontend | Tailwind CSS (prod build), Alpine.js, HTMX, Chart.js |
| Ma'lumot bazasi | SQLite (dev), PostgreSQL (prod) |
| ML | vaderSentiment + langdetect (default), HuggingFace `cardiffnlp/twitter-xlm-roberta-base-sentiment` (opt-in) |
| Autentifikatsiya | django-allauth (email + Google OAuth) |
| Hisobotlar | openpyxl (Excel), ReportLab (PDF) |
| Deploy | Render (Docker), Gunicorn, WhiteNoise |
| Monitoring | Sentry (opt-in) |
| Testlar | pytest + pytest-django, coverage ~68% (56 test) |

---

## 3. Arxitektura (qisqa)

```
config/              — Django settings (dev / prod / test)
apps/
├── accounts/        — Custom User (email as USERNAME_FIELD), profile settings
├── social/          — ConnectedAccount, Post (platform-agnostic schema)
├── collectors/      — Comment + DemoDataGenerator (realistic multi-lingual)
├── analytics/       — SentimentResult + 3-tier analyzer (transformer → VADER → keyword)
├── reports/         — Excel + PDF generators
├── dashboard/       — Landing, main dashboard, terms/privacy
└── api/             — DRF endpoints (skeleton)
templates/
├── base.html              — Root shell, Tailwind + Alpine + HTMX
├── account/               — Auth pages (split-screen design)
├── dashboard/_shell.html  — Sidebar + topbar for every authed page
├── partials/              — Navbar, footer, messages, command palette
└── ...
static/css/input.css  — Source CSS (Tailwind + custom @layer components)
static/js/app.js      — Client-side polish (scroll-reveal, spotlight, Cmd+K)
scripts/
├── entrypoint.sh       — Prod: migrate → collectstatic → optional seed → gunicorn
├── audit_urls.py       — Local URL crawl audit
├── audit_live.py       — Anonymous probe on deploy URL
└── audit_live_auth.py  — End-to-end authenticated probe (signup+connect+exports)
```

---

## 4. Komissiya uchun tayyor savol-javoblar

### S: Tanlangan sentiment modeli qaysi va nega?

J: Ikki tier:
1. **`cardiffnlp/twitter-xlm-roberta-base-sentiment`** — multilingual
   transformer, Twitter korpusida o'qitilgan. O'zbek, rus, ingliz tillarida
   yaxshi ishlaydi. `apps/analytics/services/sentiment.py:_TransformerEngine`
   da lazy-load.
2. **VADER + keyword** — Twitter tilida birinchi darajali, lekin Cyrillic
   tiliga kuchi yo'q. Shu sababli UZ/RU uchun qo'shimcha keyword engine
   blend qilingan (`NEGATIVE`, `POSITIVE` ro'yxatlari). Default prod'da
   ishlatiladi — 1 GB model Render Free 512 MB RAM'ga sig'maydi.

**Tier-fallback kodi:** `apps/analytics/services/sentiment.py:144` —
`_get_transformer()` → `_get_vader()` → `_keyword`. Har qanday muhitda
xato emas, ishlab beradi.

### S: Kerakli ma'lumot qayerdan kelyapti?

J: Uchta manba:
1. **Demo mode** (default) — `DemoDataGenerator` realistik multi-til postlar
   va kommentlar generatsiya qiladi. Vaqt taqsimoti peak-hour bias (10 ertalab
   / 19 kechqurun), engagement reallistic oraliq, sentiment ~60/25/15.
2. **Real OAuth** — Instagram Graph API, Telegram Bot, YouTube Data v3, X v2.
   Schema tayyor (`apps/social/models.py`), credentials kerak (haqqoniy biznes
   akkaunt ro'yxatdan o'tish kerak).
3. **Django admin** — superuser sifatida qo'lda kiritish.

### S: Nima uchun VADER prod'da default, XLM-RoBERTa emas?

J: Render Free plan 512 MB RAM. XLM-RoBERTa model 1.1 GB. Bu sig'maydi.
Production'ga XLM-RoBERTa uchun:
- **Starter plan** ($7/oy, 512 MB → 1 GB RAM) yetarli emas (model + Django
  runtime)
- **Standard plan** ($25/oy, 2 GB RAM) yetarli
- Yoki **HuggingFace Inference API** (tekin tier, latency ko'proq)

VADER ortig'i: darhol ishga tushadi, 0 ms latency (in-memory).

### S: PDF qanday yaratiladi? WeasyPrint ishlatmaysiz?

J: **ReportLab** ishlatamiz (pure-Python). Nega:
- WeasyPrint GTK+cairo system deps talab qiladi — Docker image'ni 500 MB
  kattalashtiradi
- ReportLab `pip install reportlab` bilan tugaydi
- Natija bir xil sifatli PDF — `apps/reports/services/pdf.py` da cover page
  (gradient), professional tables, page chrome

### S: Security?

J: `config/settings/prod.py`:
- `SECURE_SSL_REDIRECT = True`
- `SECURE_HSTS_SECONDS = 1 year` (+ preload + subdomains)
- `SECURE_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
- `X_FRAME_OPTIONS = "DENY"`
- `CSRF_TRUSTED_ORIGINS` — auto-derived from `ALLOWED_HOSTS`
- Django default password validators (min length, numeric, similarity, common)
- Token shifrlash uchun `cryptography` package bor (`apps/core/fields`'da
  kelajakda kengaytiriladi)
- CSRF POST tekshiruvi — audit skript bilan tasdiqlangan

### S: Testlar?

J: `pytest --cov=apps`:
- **56 test passing**, 0 failed
- Coverage: ~68%
- Unit: sentiment engine (13 test), mock generator (6), Excel export (3)
- Integration: 23 page-render testi (har authenticated sahifa uchun)
- Smoke: `scripts/audit_live_auth.py` — signup dan eksportgacha avtomatik

### S: i18n qanday ishlaydi?

J: Django i18n middleware + `i18n_patterns` URLconf'da. Til prefiksi
(`/en/...`, `/ru/...`) i18n_patterns ichida, auth routelari uchun til
prefiksi yo'q (allauth standart joylashuv). `makemessages` + `compilemessages`
orqali `.po` / `.mo` fayllar. Hozirgi interfeysda UZ asosiy, RU va EN
skeleton tarjimalar.

### S: Dark mode qanday ishlaydi?

J: CSS class `html.dark`. `base.html` — FOUC oldini olish uchun `<script>`
<head>'da bo'lib `localStorage.theme` + `prefers-color-scheme` tekshirib,
paint'dan oldin `document.documentElement.classList.add('dark')` qo'yadi.
Toggle tugma class'ni flip qilib localStorage'ga yozadi.

### S: Command palette (⌘K)?

J: `static/js/app.js`'da `keydown` listener. `cmdk:open` custom event
dispatch qiladi. `templates/partials/_command_palette.html` — Alpine.js
modal, backdrop blur, ↑↓ navigation, filter, Esc yopish. Barcha asosiy
URL'lar ichida.

### S: Deploy qanday?

J: Render Docker service. `Dockerfile` multi-stage:
1. **css-builder** (node:20-slim) — `npm install` + `tailwindcss --minify`
2. **prod-builder** (python:3.11-slim) — `pip install --user -r prod.txt`
3. **prod** (python:3.11-slim) — slim runtime, `scripts/entrypoint.sh` →
   migrate + collectstatic + optional seed + gunicorn

Auto-deploy GitHub push orqali.

### S: Ma'lumot bazasida ma'lumotlar qanday saqlanadi?

J: 4 ta asosiy jadval:
- `accounts_user` — auth (email as USERNAME_FIELD)
- `social_connectedaccount` — har foydalanuvchi uchun ko'p platforma akkaunt
- `social_post` — har akkaunt uchun ko'p post (FK, indeksli, `unique_together`)
- `collectors_comment` — har post uchun ko'p komment
- `analytics_sentimentresult` — OneToOne har kommentga (model_name DB'da
  saqlanadi, bir komment bir necha modeldan tahlil o'tishi mumkin)

Barcha FK + filter field'larda `db_index=True`. Optimistic locking yo'q
(talab qilinmaydi — ko'pchilik write single-user).

### S: ML ning aniqligi qanday?

J: VADER + UZ keyword engine:
- English-only VADER: F1 ~0.70 (standart benchmark)
- Bizning UZ/RU blend: subyektiv test, ~0.75 pozitiv-salbiy ajratishda
- XLM-RoBERTa (opt-in): F1 ~0.82-0.85 multilingual

Demo oqim uchun yetarli aniqlik. Real-world deploy'da:
- Bizning keyword ro'yxatini kengaytirish (ProductReviews dataset yoki
  Wiktionary orqali)
- Active learning — foydalanuvchi "incorrect" deb belgilagan natijalarni
  retraining'ga yuborish (keyingi faza)

### S: Nimalar qilinmadi va nega?

J: `docs/AUDIT_RESULTS.md` da to'liq ro'yxat. Asosiylari:
- **Real OAuth** — 4 ta platforma Developer akkaunt talab qiladi
- **SendGrid email** — API kalit kerak
- **2FA** — diplom demosida ortiqcha
- **django-unfold** — majburiy emas, Django default admin yetarli
- **Welcome tour** — 3-4 soat alohida ish
- **Scheduled reports** — Redis broker kerak

Ushbu qarorlar konservativ tanlovlar: demo 100% ishlaydi, tashqi xizmatlar
kelajakda alohida sessiyalarda ulanadi.

---

## 5. Demo scenariyisi (komissiya oldida 5 daqiqa)

1. **Bosh sahifa** (https://...) — hero, features, statistika, FAQ
2. **Signup** — `test@demo.uz` + parol → checklist + terms → dashboard
3. **Sidebar → Akkauntlarim → Instagram → Ulash** — `@mening_sahifam`, 60
   post → seed
4. **Dashboard'ga qaytish** — KPI'lar endi nol emas, grafik to'lgan
5. **Analytics** — 30 kunlik trend chart
6. **Sentiment** — donut + til matritsasi + top pozitiv/negativ kommentlar
7. **Reports** → PDF yuklab olish → brauzerda ochish (cover page + jadvallar)
8. **Excel yuklash** — 5 sheet, PieChart
9. **Ctrl+K** — command palette, har qanday sahifaga tezkor o'tish
10. **Dark mode** — tugmani bosib yorug' ↔ qorong'u
11. **Til o'zgartirish** — UZ → EN → butun sayt ingliz tiliga o'tadi

Vaqt: ~5 daqiqa. Har bir element jonli ishlaydi — script yoki recording
emas.

---

## 6. Foydalanilgan kutubxonalar va ularning roli

| Package | Maqsad | Joylashuv |
|---|---|---|
| Django 5.2 | Web framework | core |
| djangorestframework | REST API | `apps.api` |
| django-allauth | Auth + Google OAuth | auth routes |
| celery | Background tasks | skeleton (EAGER'da sinxron) |
| vaderSentiment | Lexicon sentiment | `apps.analytics.services.sentiment` |
| langdetect | Language detection | same |
| transformers (opt-in) | XLM-RoBERTa | `_TransformerEngine` (lazy) |
| openpyxl | Excel hisobotlar | `apps.reports.services.excel` |
| reportlab | PDF hisobotlar | `apps.reports.services.pdf` |
| cryptography | Token shifrlash | token field base (kelajakda) |
| whitenoise | Static serving | MIDDLEWARE |
| sentry-sdk | Xato tracking | prod.py (opt-in SENTRY_DSN) |
| pytest + pytest-django | Testlar | dev.txt |
| tailwindcss 3.4 | CSS | Dockerfile css-builder stage |
| alpinejs 3.14 | UI interactivity | CDN |
| htmx 2.0 | Partial HTML updates | CDN |
| chart.js 4.4 | Graphs | CDN (dashboard-only) |

---

## 7. Lisenziya va mualliflik

- MIT License
- Diplom loyihasi — Sardor Elmurodov, 2026
- Repository: https://github.com/Sardor2004777/social-media-analytics

Claude Opus 4.7 (1M context) bilan pair-programming — har commit'da co-authorship.
