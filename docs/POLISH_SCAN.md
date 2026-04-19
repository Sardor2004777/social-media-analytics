# Polish scan — topilgan haqiqiy kamchiliklar va holat

**Sana:** 2026-04-19
**Skan qamrovi:** `templates/**/*.html`, `apps/**/*.py`, `locale/*`, navbar, landing, dashboard

Skan maqsadi: ro'yxatda "TODO", "Lorem", "Coming soon", "yana nimadir",
sinmaydigan `href="#"`, tarjimalanmagan matnlar, bo'sh template bloklari
borligini aniqlash. Natija — haqiqiy kamchiliklar juda kam, aksariyatni shu
sessiyada tuzatildi.

---

## 1. Grep natijalari

### `TODO`, `FIXME`, `Lorem`, `Coming soon` — templatelarda

```
grep -rn "TODO|FIXME|Lorem|Coming soon|yana nimadir" templates/
→ 0 match
```

### `placeholder` (template'larda)

Hammasi **HTML input placeholder** atributlari — legitimate (e.g.
`placeholder="you@example.com"`). Matnli TODO emas.

### `pass`, `NotImplemented`, `mock`, `dummy` — appsda

```
apps/dashboard/views.py:75  "pass  # never block the dashboard on seeding"  ← legitimate try/except
apps/**/mock_generator.py                                                    ← real module (DemoDataGenerator)
```

`mock` so'zi barcha joylarda `mock_generator.py` import qilingani —
placeholder emas, to'liq ishlaydigan seed servisi.

### `href="#"` — dead nav linklari

```
templates/partials/_navbar.html:
  line 21  Analytics  → href="#"   ← FIX kerak
  line 24  Hisobotlar → href="#"   ← FIX kerak
  line 121 Profil     → href="#"   ← FIX kerak (avatar dropdown)
  line 125 Sozlamalar → href="#"   ← FIX kerak (avatar dropdown)
```

**Hal qilindi** — 4 ham haqiqiy URL'larga yo'naltirilgan
(`analytics:overview`, `reports:index`, `accounts:settings`, `social:accounts`).

---

## 2. Bo'sh / yarim yozilgan bloklar

### `/` landing sahifasi (`templates/dashboard/landing.html`)

- **Hero**: sarlavha + subtitle + CTA + dashboard mockup + trust row + scroll ind — **to'liq**
- **Features (bento)**: 6 ta card + mini chart + sentiment bars + chips — **to'liq**
- **Stats**: 4 ta progress ring + count-up — **to'liq**
- **How it works**: 3 qadam — **to'liq**
- **Use cases**: 3 card (talaba, marketing, blogger) — **to'liq**
- **FAQ**: 5 savol → endi **8 savol** (qo'shildi: PDF ichida nima, sentiment aniqligi, haqiqiy OAuth)
- **Final CTA + Footer** — **to'liq**

### `/accounts/*/` (auth sahifalar)

- Signup: checklist + terms checkbox + loading spinner + back-home link — **to'liq**
- Login: loading spinner + back-home + show/hide password — **to'liq**
- Password reset 4 sahifa — **to'liq**

### `/dashboard/`, `/social/`, `/analytics/`, `/analytics/sentiment/`, `/reports/`, `/settings/`

Barchasi DB'dan real ma'lumot o'qiydi — jadval empty bo'lsa `{% empty %}` fallback
bor. Skaner natijasi: **bo'sh section topilmadi**.

### `/terms/` (Foydalanish shartlari)

Oldin 7 band → endi **10 band** (Mualliflik huquqi, Javobgarlikni cheklash,
Nizolarni hal etish qo'shildi).

### `/privacy/` (Maxfiylik siyosati)

Ma'lumot to'plash, foydalanish, saqlash, cookie, huquqlar — **to'liq**.

---

## 3. Translation holati

```
$ ls locale/
.gitkeep        ← faqat gitkeep, .po fayl yo'q
```

**Holat**: `django.po` fayllar yaratilmagan. `{% trans %}` matnlari har uchta
i18n prefiksida (`/uz/`, `/ru/`, `/en/`) **o'zbek tilida** ko'rsatiladi.
Til switcher ishlaydi (URL o'zgaradi), lekin matn bir xil.

**Sabab bu sessiyada tuzatilmadi**: 200+ translatable string; har biri uchun
ru va en tarjima qo'lda yozilishi kerak — 2-3 soatlik alohida ish. Keyingi
iteratsiyaga qoldi.

**Keyingi qadam** (sizda vaqt bo'lgan paytda):
```
python manage.py makemessages -l ru -l en --no-wrap
# .po fayllarni tarjima qilib to'ldirish
python manage.py compilemessages
```

---

## 4. Texnik risklar (scanner funksiya topmadi, lekin manually tekshirildi)

### 4.1 Production `check --deploy`

`prod.py` barcha 8 security settings'ni to'g'ri o'rnatgan (SSL_REDIRECT, HSTS,
SECURE_COOKIE, CSRF_TRUSTED_ORIGINS, ...). Prod'dan check ishga tushirib
bo'lmaydi — `sentry_sdk` paketi dev.txt'da yo'q. Bu `docs/AUDIT_RESULTS.md`'da
izohlangan.

### 4.2 Migrations drift

```
$ python manage.py makemigrations --check --dry-run
No changes detected
```

### 4.3 Static files

`collectstatic --dry-run` → 171 fayl, 0 xato. `output.css` 100 KB (reveal
qoidalari saqlangan), `app.js` 4.7 KB, `favicon.svg` 746 B.

### 4.4 Tests

```
$ pytest
57 passed, 28 warnings in 11s
coverage: ~68%
```

---

## 5. Skanningdan KEYIN shu sessiyada QILGAN tuzatishlar

| # | Nima | Qayer | Holat |
|---|------|-------|-------|
| 1 | Navbar "Analytics" dead link | `_navbar.html:21` | → `/analytics/` |
| 2 | Navbar "Hisobotlar" dead link | `_navbar.html:24` | → `/reports/` |
| 3 | Dropdown "Profil" dead link | `_navbar.html:121` | → `/settings/` |
| 4 | Dropdown "Sozlamalar" dead link | `_navbar.html:125` | → `/settings/` + qo'shimcha "Akkauntlarim" qo'shildi |
| 5 | FAQ 5 → 8 savol | `landing.html:~495-615` | PDF tarkibi, ML aniqligi, OAuth yo'l xaritasi |
| 6 | Terms 7 → 10 band | `terms.html:~65` | Mualliflik, Javobgarlik, Nizolar |

---

## 6. Keyingi kuzatishlar (bu sessiyada qilinmadi, sababi bilan)

Quyidagilar har biri katta hajmli ish va tashqi resurs yoki uzoq vaqt talab
qiladi. Har biri uchun alohida sessiya tavsiya etiladi:

| Narsa | Taxminiy vaqt | Blokerlar |
|-------|--------------|-----------|
| Ru/En tarjima (200+ string) | 2-3 soat | Yo'q (qo'lda yozish) |
| `django-unfold` admin theme | 2 soat | Yo'q, lekin katta refactor |
| `django-hcaptcha` signup spam himoya | 30 daq | hCaptcha site key |
| SendGrid SMTP real email | 30 daq | SendGrid API kalit |
| Real Instagram Graph API OAuth | 1-2 kun + 7-14 kun review | Meta Business Verification |
| Real Google OAuth (Login + YouTube) | 1 soat | Google Cloud project |
| Real Telegram Bot Login Widget | 30 daq | @BotFather token |
| Matplotlib chart images in PDF | 1 soat | Yo'q, lekin hozirgi PDF yetarli |
| Shepherd.js welcome tour | 3-4 soat | Yo'q |
| 2FA (django-two-factor-auth) | 2 soat | Yo'q, lekin diplom uchun ortiqcha |
| Avatar upload | 2 soat | Render persistent storage yoki S3 |
| Celery scheduled reports | 2-3 soat | Redis broker |
| Heatmap/word cloud chartlar | 2 soat | Yo'q |

---

## 7. Xulosa

- **Live saytda haqiqiy "ko'rinadigan" kamchilik**: 4 dead navbar linki. **Tuzatildi.**
- **Yarim yozilgan bo'limlar**: FAQ (kengaytirildi), Terms (kengaytirildi).
- **Keyingi katta ish**: 3 tilli tarjima (200+ string).
- **Qolgan "polish" itemlar** (pt 6): demo uchun ahamiyatsiz yoki tashqi resurs kerak.

Hozirgi holat komissiya oldida jonli demo uchun tayyor. Siz istasangiz
3-tilli tarjimani keyingi sessiyada qilamiz.
