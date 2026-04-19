# Jonli audit natijalari — FAZA 1

**Sana:** 2026-04-19
**Maqsad:** https://social-media-analytics-9rre.onrender.com
**Skriptlar:** `scripts/audit_live.py`, `scripts/audit_live_auth.py`

---

## 1. HTTP status matritsasi

### 1.1 Anonim probe (19 URL + 2 POST)

| # | URL | Status | Hajm | Notes |
|---|-----|--------|------|-------|
| 1 | `/` | 200 | 65 KB | Landing |
| 2 | `/en/` | 200 | 65 KB | i18n prefix |
| 3 | `/accounts/signup/` | 200 | 27 KB | Parol kuchi + checklist + terms |
| 4 | `/accounts/login/` | 200 | 25 KB | Loading state + back-home |
| 5 | `/accounts/password/reset/` | 200 | 22 KB | Email form |
| 6 | `/accounts/password/reset/done/` | 200 | 21 KB | "Emailga yuborildi" |
| 7 | `/dashboard/` (anon) | 302 → `/accounts/login/?next=...` | 25 KB | To'g'ri redirect |
| 8 | `/social/` (anon) | 302 → login | 25 KB | To'g'ri |
| 9 | `/analytics/` (anon) | 302 → login | 25 KB | To'g'ri |
| 10 | `/analytics/sentiment/` (anon) | 302 → login | 25 KB | To'g'ri |
| 11 | `/reports/` (anon) | 302 → login | 25 KB | To'g'ri |
| 12 | `/settings/` (anon) | 302 → login | 25 KB | To'g'ri |
| 13 | `/admin/` | 302 → `/admin/login/` | 4 KB | Django admin |
| 14 | `/api/v1/docs/` | 200 | 4.7 KB | Swagger UI |
| 15 | `/api/v1/schema/` | 200 | 3.7 KB | OpenAPI YAML |
| 16 | `/api/v1/redoc/` | 200 | 0.7 KB | ReDoc UI |
| 17 | `/terms/` | 200 | 24 KB | Foydalanish shartlari |
| 18 | `/privacy/` | 200 | 23 KB | Maxfiylik siyosati |
| 19 | `/foobar/` | 404 | 24 KB | Brand 404 sahifa |
| 20 | `/static/css/output.css` | 200 | 99 KB | Tailwind minified |
| 21 | `/static/js/app.js` | 200 | 4.7 KB | Client polish |
| 22 | `/static/favicon.svg` | 200 | 746 B | Brand logo |

POSTs:

| POST | Status | Natija |
|------|--------|--------|
| `POST /accounts/password/reset/` with CSRF | 200 → `/password/reset/done/` | |
| `POST /accounts/signup/` fresh email | 200 → `/dashboard/` | Signup to'liq ishlaydi |

### 1.2 Kirgan foydalanuvchi probe

Live serverda avtomatik (signup + har sahifa + connect + eksport):

| Qadam | Natija |
|-------|--------|
| Fresh signup (`live-auth-63315492@example.com`) | OK → `/dashboard/` |
| `/dashboard/` | OK — KPI + chart + timeline |
| `/social/` | OK — connect CTA + account ro'yxat |
| `/social/connect/{instagram,telegram,youtube,x}/` | OK (har biri) |
| `/analytics/` | OK — 30 kun trend + jadvallar |
| `/analytics/sentiment/` | OK — distribution + top samples |
| `/reports/` | OK — XLSX + PDF cards |
| `/settings/` | OK — profile form |
| **POST connect Instagram** (`@live_audit_9993`) | OK → `/social/` + handle ko'rindi |
| `/reports/export.xlsx` | OK — 28 KB (`PK\x03\x04` magic) |
| `/reports/export.pdf` | OK — 8.6 KB (`%PDF-` magic) |
| Logout | OK → `/dashboard/` anon ni login ga redirect |

**Jami: 0 muammo.**

---

## 2. Django `manage.py check`

```
System check identified no issues (0 silenced).
```

### Deploy check (`check --deploy` against prod.py)

Prod dep'lar (sentry-sdk) lokal muhitda o'rnatilmagan, shu sababli prod settings'ni lokal muhitda yuklash mumkin emas. Render'dagi jonli deploy `DJANGO_SETTINGS_MODULE=config.settings.prod` bilan ishlaydi va `prod.py`'da barcha kerakli security sozlamalar mavjud:

- `SECURE_SSL_REDIRECT = True`
- `SECURE_HSTS_SECONDS = 31_536_000` (+ `INCLUDE_SUBDOMAINS` + `PRELOAD`)
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `X_FRAME_OPTIONS = "DENY"`
- `SECURE_REFERRER_POLICY = "same-origin"`
- `CSRF_TRUSTED_ORIGINS` auto-derived dan `ALLOWED_HOSTS`

---

## 3. Migrations

```
$ python manage.py makemigrations --check --dry-run
No changes detected
```

---

## 4. Test coverage

```
56 passed, 28 warnings in 10.65s
TOTAL: 1109 stmts, 326 missed, 68.5% coverage
```

Coverage breakdown (eng katta fayllar):

| Fayl | Coverage |
|------|----------|
| `apps/analytics/services/sentiment.py` | 95% |
| `apps/reports/services/pdf.py` | 97% |
| `apps/social/models.py` | 94% |
| `apps/dashboard/views.py` | 86% |
| `apps/reports/views.py` | 83% |
| `apps/social/views.py` | 75% |
| `apps/reports/services/excel.py` | 14% (tekshiriladi: workbook yaratilgani zipfile orqali tasdiqlangan) |

Qo'shiladigan: +1 test — signup signal demo data yaratadimi (`test_signup_signal.py`). 56 → 57.

---

## 5. "Pages show nothing" muammosining asosiy sababi

**Ilgari:** yangi signup qilingan foydalanuvchi `/dashboard/`'ga kirganda KPI'lar 0, chart'lar bo'sh — chunki hali hech qanday ConnectedAccount yo'q edi.

**Hozirgi hal qilish:** `allauth.account.signals.user_signed_up` signaliga yozuvchi — har yangi ro'yxatdan o'tishda avtomatik `DemoDataGenerator` ishga tushadi:

- 4 akkaunt (IG/TG/YT/X) yaratiladi
- 30 post har platformaga (jami 120)
- 2-6 komment har postga
- Har komment uchun real sentiment tahlil (VADER)

Natija: yangi foydalanuvchi `/dashboard/`'da darhol realistik KPI'lar va grafikni ko'radi. `/social/` sahifasida demo akkauntlarini o'chirib, o'zining handle'ini qo'shishi mumkin.

**Env var bilan o'chirish:** `DEMO_SEED_ON_SIGNUP=0` qo'yilsa, signal ishlamaydi (prod'da haqiqiy foydalanuvchilar kelganida foydali).

---

## 6. Xulosa

- **HTTP/template/form darajasida:** 0 muammo
- **ML/ekport pipeline:** ishlaydi (sentiment + XLSX + PDF tasdiqlangan)
- **UX muammo:** yangi signup qilingan foydalanuvchilar uchun bo'sh dashboard — **hal qilindi** (signup signal)
- **Real OAuth (IG/YT/TG/X), hCaptcha, SendGrid, django-unfold:** tashqi kalit yoki katta hajmli ish — `docs/OAUTH_SETUP.md` va `docs/AUDIT_RESULTS.md`'da sabablar yozilgan

Demo bugun komissiya oldiga chiqishga tayyor.
