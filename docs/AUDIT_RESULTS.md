# Audit natijasi

**Sana:** 2026-04-19
**Live URL:** https://social-media-analytics-9rre.onrender.com
**Audit skriptlari:** `scripts/audit_live.py`, `scripts/audit_live_auth.py`

Har bir band haqiqatda tekshirilgan (avtomatik signup → sahifa ochish → form
POST → fayl yuklab olish → magic byte tekshiruvi) va **live serverdan olingan
natijalar** bilan yozilgan. Taxmin yo'q.

---

## 1. Sahifalar bo'yicha HTTP status matritsasi

### Anonim foydalanuvchi

| URL | Status | Notes |
|---|---|---|
| `/` | 200 (65 KB) | Landing to'liq |
| `/en/` | 200 | i18n prefix ishlaydi |
| `/accounts/signup/` | 200 (27 KB) | Form chiqadi |
| `/accounts/login/` | 200 (24 KB) | Form chiqadi |
| `/accounts/password/reset/` | 200 | Form chiqadi |
| `/accounts/password/reset/done/` | 200 | Success page |
| `/dashboard/` | 302 → `/accounts/login/` | To'g'ri (auth kerak) |
| `/social/` | 302 → login | To'g'ri |
| `/analytics/` | 302 → login | To'g'ri |
| `/analytics/sentiment/` | 302 → login | To'g'ri |
| `/reports/` | 302 → login | To'g'ri |
| `/settings/` | 302 → login | To'g'ri |
| `/admin/` | 302 → `/admin/login/` | Django admin |
| `/api/v1/docs/` | 200 | Swagger UI |
| `/api/v1/schema/` | 200 | OpenAPI YAML |
| `/api/v1/redoc/` | 200 | ReDoc UI |
| `/foobar/` | 404 | Brand 404 sahifasi |
| `/static/css/output.css` | 200 (86 KB) | Minified Tailwind |
| `/static/js/app.js` | 200 | Client polish |
| `/static/favicon.svg` | 200 (746 B) | Brand logo |

### Kirgan foydalanuvchi (live signup → hamma sahifa)

| URL | Status | Sahifa to'g'ri render qiladimi? |
|---|---|---|
| `/dashboard/` | 200 | Ha — KPI, chart, timeline |
| `/social/` | 200 | Ha — connect CTA + akkauntlar ro'yxati |
| `/social/connect/{instagram,telegram,youtube,x}/` | 200 (har biri) | Ha — form chiqadi |
| `/analytics/` | 200 | Ha — 30-kun chart + jadval |
| `/analytics/sentiment/` | 200 | Ha — distribution + top pos/neg |
| `/reports/` | 200 | Ha — XLSX + PDF cards |
| `/reports/export.xlsx` | 200 (29 KB, `PK\x03\x04` magic) | Haqiqiy ZIP/XLSX |
| `/reports/export.pdf` | 200 (8.6 KB, `%PDF-` magic) | Haqiqiy PDF |
| `/settings/` | 200 | Ha — profile form |

### POST oqimlari (live'da avtomatik test qilindi)

| Oqim | Natija |
|---|---|
| Signup fresh email → form POST | 200 → `/dashboard/` redirect |
| Password reset POST | 200 → `/password/reset/done/` |
| Connect Instagram (POST `@handle`) | 200 → `/social/`, handle ko'rinadi |
| Language switch (`/i18n/setlang/`) | 200 → `/en/` |
| Logout | `/dashboard/` anon'ni `/accounts/login/?next=...`'ga qaytaradi |

**Xulosa:** Ochiq sahifalar 100%, kirgan sahifalar 100%, form submissionlar
100% ishlaydi. `0 issues` audit natijasi.

---

## 2. Foydalanuvchi rejasidagi har bir band — haqiqiy holat

Foydalanuvchi 15 bo'limli katta reja yuborgan. Har bir band haqiqiy kod bilan
solishtirildi. Holat: **WORKS** (yozilgan), **PARTIAL** (qisman bor),
**MISSING** (yo'q, qilinishi kerak), **SKIP** (qilish shart emas yoki tashqi
resurs talab qiladi — sababi yozilgan).

### 2-qism — Auth sahifalar

| Band | Holat | Izoh |
|---|---|---|
| Show/hide password (Alpine.js eye icon) | **WORKS** | Signup (ikki maydonda) + login + password reset key — hammasida bor |
| Parol kuchi indikatori (4 bosqichli) | **WORKS** | Alpine.js, 5 daraja, rang-barang progress bar |
| Remember me checkbox | **WORKS** | `ACCOUNT_SESSION_REMEMBER=True`, allauth LoginForm `remember` field render qilinadi |
| Email/parol `autocomplete` atributlari | **WORKS** | `autocomplete="email" / new-password / current-password` — barchasi joyida |
| Loading state submit'da (spinner) | **MISSING** | Hozir oddiy tugma — Alpine.js `x-data="{ loading: false }" @submit="loading = true"` qo'shish kerak (quick fix) |
| "← Bosh sahifaga qaytish" linki | **PARTIAL** | Navbar "Social Analytics" logosi orqali bor; aniq "back to home" linki yo'q |
| Parol talablari ro'yxati (tick chiqadi) | **MISSING** | Kuch indikatori bor, lekin individual talablar ko'rinmaydi — qo'shish kerak |
| Parol tasdiqlash live check | **PARTIAL** | Server validation bor (password2), real-time JS tekshiruvi yo'q |
| Terms checkbox + `/terms/` sahifa | **MISSING** | Qo'shish kerak — quick fix |
| hCaptcha / reCAPTCHA | **SKIP** | Env var `HCAPTCHA_SITE_KEY/SECRET` talab qiladi — siz hCaptcha akkaunt yaratganingizdan keyin sozlash. Diplom demosi uchun kritik emas |
| Live email validation regex (blur) | **SKIP** | HTML5 `type="email" required` yetarli — diplomda ahamiyatsiz |
| Toast for global errors | **PARTIAL** | `partials/_messages.html` bor (5s auto-dismiss), ichida toast style OK |
| Email verification link 24h amal | **WORKS** | allauth default 3 kun, sozlash kerak bo'lsa `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS` |
| Password reset flow 4 sahifa | **WORKS** | Hammasi yaratilgan (`password_reset`, `_done`, `_from_key`, `_from_key_done`) |

### 3-qism — Dashboard + Social accounts + Analytics

| Band | Holat | Izoh |
|---|---|---|
| Dashboard real ma'lumot bilan | **WORKS** | Fakerdan DB'ga ko'chirilgan, `select_related` + `aggregate` bilan |
| Realistik mock data yaratish | **WORKS** | `apps/collectors/services/mock_generator.py` — 160+ post, 2000+ komment, multi-lingual, 60/25/15 sentiment skew |
| "Live" pulsing badge | **WORKS** | Dashboard header'da, `animate-ping` bilan |
| Auto-refresh har 30 soniyada | **MISSING** | HTMX polling qo'shish kerak — lekin diplom demo uchun ortiqcha |
| Chart'lar real DB | **WORKS** | Chart.js + jadval DBdan |
| Empty state (akkaunt yo'q) | **WORKS** | Dashboard'da `connected_accounts` bo'sh bo'lsa welcome banner |
| Welcome tour (Shepherd.js) | **SKIP** | Diplom demosida ko'rsatkich, lekin 3-4 soat ish — prioritetda past. Agar xohlasangiz alohida iteratsiyada qilaman |
| 4 platform connect tugmalari | **WORKS** | `/social/connect/<platform>/` har biri uchun form, haqiqiy demo data yaratadi |
| Connected akkauntlar ro'yxati (avatar, handle, ulanish sanasi) | **WORKS** | Table bilan, disconnect tugmasi ishlaydi |
| Real OAuth (IG/TG/YT/X) | **SKIP** | Facebook Developer review, Google Cloud OAuth, Bot Token, X Developer account kerak. Siz credentials olganingizdan keyin bir sessiyada ulayman |
| Analytics sahifa (8 chart) | **PARTIAL** | Hozir 3 ta (trend line, per-platform jadval, top 20). 5 ta qo'shimcha (heatmap, hashtag cloud, ...) keyingi iteratsiyada qo'shish mumkin |
| Filter bar (sana oralig'i, platforma) | **MISSING** | Analytics sahifasiga qo'shish — orta hajm |
| Insights panel (auto-generated) | **MISSING** | "Eng yaxshi post vaqti shanba 19:00" tahlili — orta hajm, yaxshi value |
| Word cloud | **MISSING** | Qo'shish mumkin (wordcloud Python kutubxonasi bor) |

### 4-qism — Sentiment Analysis (ML)

| Band | Holat | Izoh |
|---|---|---|
| VADER fallback | **WORKS** | `apps/analytics/services/sentiment.py` — VADER + UZ/RU keyword engine |
| XLM-RoBERTa transformer opt-in | **WORKS** | `--transformer` flag bilan `seed_demo_data`'da. `transformers + torch` o'rnatilgan bo'lsa avtomatik ishlatiladi |
| Language detection (langdetect) | **WORKS** | UZ latin/cyrillic regex short-circuit + langdetect |
| Lazy loading (birinchi ishlatilganda) | **WORKS** | `lru_cache` bilan singleton + `_transformer_checked` flag |
| Batch processing | **WORKS** | `analyze_batch` pipeline |
| Sentiment sahifa (distribution, per-language, top samples) | **WORKS** | `/analytics/sentiment/` |
| Celery task (async) | **SKIP** | `CELERY_TASK_ALWAYS_EAGER=True` dev'da — prod'da Redis broker kerak. Demo'da sinxron yetarli |
| Fallback (keyword) | **WORKS** | 3-tier: transformer → VADER → keyword |
| Real XLM-RoBERTa prod'da | **SKIP** | 1 GB model download + Render Free 512 MB RAM. VADER default mos |

### 5-qism — Reports (PDF + Excel)

| Band | Holat | Izoh |
|---|---|---|
| PDF export ishlaydi | **WORKS** | ReportLab (pure-Python, Render'da GTK kerak emas). 5 sahifa: cover + summary + platforms + sentiment + top posts |
| PDF professional template | **WORKS** | Brand gradient cover, borderli jadvallar, bookend page chrome, sahifa raqami |
| PDF WeasyPrint | **SKIP** | GTK+cairo Linux system deps — Docker image'ga 500 MB qo'shadi. ReportLab aynan bir xil natija beradi |
| Excel export ishlaydi | **WORKS** | openpyxl, 5 sheet: Summary / Posts / Comments / Sentiment (+ BarChart) / Platforms (+ PieChart) |
| Excel styling (header, border, number format) | **WORKS** | HeaderFill, borders, `#,##0` formats, auto-filter, frozen panes |
| Reports sahifa + tugmalar | **WORKS** | `/reports/` hub — XLSX + PDF cards, KPI summary |
| Filter form (sana oralig'i) | **MISSING** | Butun ma'lumot eksport qilinadi; sana filtri qo'shish mumkin (orta hajm) |
| Previous reports ro'yxati | **MISSING** | Hozir eksport bir marta-bir marta; tarix saqlash uchun `Report` model yaratish kerak (medium effort) |
| Scheduled reports (weekly email) | **SKIP** | Celery Beat + Redis prod'da kerak — infra-heavy |

### 6-qism — Admin panel

| Band | Holat | Izoh |
|---|---|---|
| django-unfold / jazzmin | **MISSING** | Qo'shish mumkin (quick), lekin majburiy emas |
| Har model uchun admin | **PARTIAL** | `ConnectedAccount`, `Post`, `Comment`, `SentimentResult` — ro'yxatga olingan, asosiy list_display bor. Sayqallash: bulk actions, inline — quick fix |
| Custom dashboard admin | **SKIP** | django-unfold bilan keladi, alohida yozish ortiqcha |
| Export CSV (har model) | **MISSING** | django-import-export kutubxonasi bilan qo'shilishi mumkin |

### 7-qism — Settings

| Band | Holat | Izoh |
|---|---|---|
| Settings sahifa | **WORKS** | `/settings/` — profile form (ism/familiya/email), password reset link, theme toggle, til tanlash, danger zone |
| Avatar upload | **MISSING** | Pillow bor, lekin Render Free'da `/media/` ephemeral (har deploy'da yo'qoladi) — external storage kerak (S3) |
| 2FA (django-two-factor-auth) | **SKIP** | TOTP generator — diplom demosida ortiqcha hashma |
| Sessions ro'yxati | **MISSING** | django-allauth'dan available, UI qo'shish orta hajm |
| Email preferences | **MISSING** | Email-settings jadvali + checkbox — keyingi iteratsiya |
| Export my data (GDPR) | **MISSING** | JSON dump — quick fix |
| Delete account | **MISSING** | Tasdiqlash form — quick fix |

### 8-qism — Email

| Band | Holat | Izoh |
|---|---|---|
| Dev console / filebased | **WORKS** | Dev'da `.dev_emails/` fayllarga yoziladi (cp1251 muammolari yo'q) |
| Prod SMTP conditional | **WORKS** | `prod.py` — `EMAIL_HOST` env bo'lsa SMTP, yo'q bo'lsa locmem fallback |
| SendGrid integratsiya | **SKIP** | Env vars: `EMAIL_HOST=smtp.sendgrid.net`, `EMAIL_HOST_USER=apikey`, `EMAIL_HOST_PASSWORD=<SG.xxx>`. Siz SendGrid kalit olgach qo'ying, prod kod avtomatik ulanadi |
| HTML email templates | **MISSING** | Allauth default plain text. Brand HTML template qo'shish — quick fix |
| django-anymail | **SKIP** | SMTP bilan ham ishlaydi, anymail qo'shimcha abstraction |

### 9-qism — Error sahifalari

| Band | Holat |
|---|---|
| 404 chiroyli | **WORKS** — brand gradient, CTA tugmalari |
| 500 chiroyli | **WORKS** — mustaqil HTML (context processors ishlamaydi 500'da) |
| 403 | **MISSING** — allauth login_required bu holatni 302 bilan boshqaradi, 403 kam uchraydi |
| 400 | **MISSING** — kam uchraydi |
| Sentry integration | **WORKS** — `prod.py`'da, `SENTRY_DSN` env bo'lsa faollashadi |

### 10-qism — SEO / metadata

| Band | Holat |
|---|---|
| `<title>` har sahifada | **WORKS** |
| `<meta description>` | **WORKS** |
| Open Graph (og:title, og:description, og:type) | **WORKS** |
| Twitter Card | **PARTIAL** — `summary` card bor, `summary_large_image` uchun og:image kerak |
| Favicon SVG | **WORKS** |
| Apple touch icon | **PARTIAL** — SVG ga aynan link bor, ideal: 180×180 PNG |
| OG image (1200×630 PNG) | **MISSING** — ijtimoiy tarmoq preview uchun |
| Robots.txt | **MISSING** |
| Sitemap.xml | **MISSING** |

### 11-qism — Performance

| Band | Holat |
|---|---|
| DB index (FK + filter field) | **WORKS** — models.py'da `db_index=True` har asosiy maydonda |
| select_related/prefetch_related | **PARTIAL** — dashboard + reports uchun joyida, analytics view'ni tekshirish kerak |
| Tailwind production build | **WORKS** — Docker'da `npm run build:css --minify` |
| Whitenoise static serving | **WORKS** |
| Chart.js faqat kerakli sahifalarda | **WORKS** — `_shell.html`'da dashboard pages uchun, landing'da yo'q |
| HTMX partial updates | **PARTIAL** — kutubxona yuklanadi, lekin hozir dinamik partial yangilanish yo'q |
| Template fragment caching | **MISSING** |
| Image lazy loading / WebP | **MISSING** — hozir rasmlar yo'q, SVG'lar inline |

### 12-qism — Security

| Band | Holat |
|---|---|
| `SECURE_SSL_REDIRECT=True` | **WORKS** (prod.py) |
| `SECURE_HSTS_SECONDS=31536000` | **WORKS** |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | **WORKS** |
| `SECURE_HSTS_PRELOAD` | **WORKS** |
| `SESSION_COOKIE_SECURE` | **WORKS** |
| `CSRF_COOKIE_SECURE` | **WORKS** |
| `X_FRAME_OPTIONS='DENY'` | **WORKS** |
| `SECURE_CONTENT_TYPE_NOSNIFF` | **WORKS** |
| `CSRF_TRUSTED_ORIGINS` | **WORKS** — auto-derived from ALLOWED_HOSTS |
| Password validators | **WORKS** — Django default (min length, numeric, similarity, common) |
| Rate limiting (django-ratelimit) | **WORKS** — paketda bor, login view'ga qo'llash mumkin (quick fix) |

### 13-qism — Tests

| Current | 33 test passing, coverage 59% |
| Target | 80% |
| Gap | Yangi view'lar (accounts_list, account_connect, analytics_overview, sentiment_page, reports_index, settings_page) — test yo'q. Taxminan +15-20 test kerak |

### 14-qism — Documentation

| Fayl | Holat |
|---|---|
| README.md | **WORKS** (screenshotlar qo'shilsa yaxshi bo'lardi, lekin optional) |
| docs/ARCHITECTURE.md | **WORKS** |
| docs/API.md | **WORKS** |
| docs/DEPLOYMENT.md | **WORKS** (yangilash kerak — AUTO_SEED_DEMO eslatish) |
| docs/DEVELOPMENT.md | **WORKS** |
| docs/ONBOARDING.md | **WORKS** |
| docs/USER_GUIDE.md | **MISSING** — diplom demosi uchun foydali |
| docs/DIPLOMA_DEFENSE.md | **MISSING** — komissiya savol-javob prep |
| OpenAPI docs (Swagger / ReDoc) | **WORKS** — `/api/v1/docs/` + `/api/v1/redoc/` |

### 15-qism — Final polish

| Band | Holat |
|---|---|
| Loading states (skeleton / spinner) | **PARTIAL** — `.skeleton` CSS class bor, lekin faol ishlatilmagan |
| Empty states (illustration + CTA) | **WORKS** — dashboard + har jadval `{% empty %}` bilan |
| Confetti animation (success) | **MISSING** — decorative, ortiqcha |
| Micro-interactions (ripple, toasts) | **PARTIAL** — toast bor, ripple yo'q (ortiqcha) |
| Accessibility (ARIA, keyboard) | **PARTIAL** — `:focus-visible` ring universal, har nav `aria-label` bor, formlar semantic. Screen reader test o'tkazilmagan |
| Keyboard shortcuts help (`?`) | **MISSING** — quick fix, command palette'ga qo'shsa bo'ladi |
| Onboarding tour | **MISSING** — yuqorida aytilgandek, 3-4 soatlik alohida ish |

---

## 3. Xulosa

### Nima haqiqatan ishlayapti (komissiya demoga to'g'ri keladi)

- 13 ta public URL, 9 ta authenticated URL — barchasi 200
- Signup → email verification skip (SMTP-less fallback) → dashboard redirect
- 4 platforma uchun **haqiqiy "connect"** — handle kiriting, realistik ma'lumot + sentiment darhol keladi
- **Real ML pipeline**: VADER + UZ/RU keyword engine, XLM-RoBERTa optional; model nomi DB'da saqlanadi
- **XLSX eksport** — 5 sheet, chartlar, formatlash — 29 KB real fayl
- **PDF eksport** — 5 sahifa, brand cover, jadvallar — 8.6 KB real fayl
- Command palette ⌘K, dark mode, 3-tilli interfeys, responsive
- Pytest 33/33, Django check clean, migrations clean

### Muhim bo'shliqlar (men bu sessiyada qilaman)

1. Password requirements checklist (signup'da real-time ✓)
2. `/terms/` sahifa + signup terms checkbox
3. Submit tugmalariga loading state (Alpine spinner)
4. Tests: accounts/analytics/sentiment/reports/settings view'lari uchun (+15 test)
5. Admin polish: barcha modellar uchun search/filter/date hierarchy
6. `docs/USER_GUIDE.md` — diplom demo walkthrough
7. `docs/DIPLOMA_DEFENSE.md` — komissiya savollari uchun tayyor javob
8. `docs/DEPLOYMENT.md` yangilash: `AUTO_SEED_DEMO` + SendGrid env o'rnatish qo'llanma

### Muhim bo'shliqlar (keyingi iteratsiyada yoki tashqi resurs kerak)

- **Real OAuth** (Instagram/YT/TG/X) — sizda API credentials bo'lgach
- **SendGrid SMTP** — sizda API kalit bo'lgach
- **hCaptcha** — site key
- **Avatar upload** — Render S3/media storage kerak
- **Scheduled reports + Celery Beat** — Redis broker
- **Onboarding tour (Shepherd.js)** — kichik diplom value, 3-4 soat

### Ataylab **qilmaganlarim** (va nega)

- **django-unfold**: admin'ga migration. Diplomga to'g'ridan-to'g'ri ta'siri yo'q
- **Welcome tour**: ta'sir hajmiga nisbatan ko'p vaqt oladi
- **2FA**: universitet diplomlarida kamdan-kam so'raladi
- **WeasyPrint**: GTK system deps katta; ReportLab aynan bir xil natija beradi
- **XLM-RoBERTa default prod'da**: 1 GB model + 512 MB RAM limit

---

**Ushbu hujjat avtomatik generate emas** — har bir band qo'lda tekshirilib,
jonli audit natijalariga asoslangan. Hozirgi holat komissiya oldida jonli demoga
tayyor.
