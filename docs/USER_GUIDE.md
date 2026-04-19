# Foydalanuvchi qo'llanmasi

Social Analytics — ijtimoiy tarmoq postlarini yig'ish, tahlil qilish va
hisobotlarga aylantirish platformasi. Bu qo'llanma saytga kirgandan boshlab
birinchi hisobotni yuklab olishgacha bo'lgan yo'lni bosqichma-bosqich
ko'rsatadi.

**Live URL:** https://social-media-analytics-9rre.onrender.com

---

## 1. Ro'yxatdan o'tish

1. Bosh sahifadagi **"Bepul boshlash"** tugmasini bosing yoki to'g'ridan-to'g'ri
   `/accounts/signup/` manziliga kiring.
2. Email manzilingizni kiriting.
3. Parol tanlang. Formadagi **real-time checklist** parol kuchini ko'rsatadi:
   - ✓ 8+ belgi
   - ✓ Katta harf
   - ✓ Kichik harf
   - ✓ Raqam
   - ✓ Maxsus belgi
4. Parolni takrorlang. Tasdiqlash maydoni mos kelishini darhol ko'rsatadi.
5. **"Foydalanish shartlari"** va **"Maxfiylik siyosati"** bilan roziligingizni
   tasdiqlang (checkbox).
6. **"Akkaunt yaratish"** tugmasini bosing.

Email tasdiqlashi ixtiyoriy (hozirgi sozlamada). Siz darhol dashboard'ga
o'tasiz.

### Muqobil: Google OAuth

Ro'yxatdan o'tish va kirish sahifalarida **"Google orqali davom etish"**
tugmasi bor (Google OAuth kaliti sozlangan bo'lsa).

---

## 2. Dashboard bilan tanishish

Kirgach siz asosiy dashboard sahifasiga yo'naltirilasiz
(`/dashboard/`). Bu yerda:

- **Breadcrumb yuqorida**: Home > Dashboard. Yonida **Live** pulsing badge.
- **⌘K qidiruv tugmasi** (yoki `Ctrl+K`): command palette — har sahifaga tez
  o'tish.
- **Til tanlash** (UZ/RU/EN) va **mavzu tugmasi** (yorug'/qorong'u).
- **Onboarding banner**: akkaunt hali ulanmagan bo'lsa yuqorida chiroyli
  ko'rsatma paydo bo'ladi.
- **4 KPI kartasi**: Jami postlar, Obunachilar, Engagement rate, Sentiment %.
- **Faollik grafigi** (14 kunlik line chart) va **Platforma donut**.
- **Top postlar** ro'yxati va **Tadbirlar timeline**.

---

## 3. Birinchi akkauntni ulash

### Qadam 1. Sidebar → Akkauntlarim

`/social/` manziliga o'tadi. 4 platforma karta sifatida ko'rsatiladi:
Instagram, Telegram, YouTube, X.

### Qadam 2. Platformani tanlang

Kerakli kartada **"Ulash"** tugmasini bosing. `/social/connect/<platform>/`
formasiga o'tasiz.

### Qadam 3. Handle va post soni kiriting

- **Handle**: `@siz_xohlaydigan_nom` (masalan: `mening_kanalim`)
- **Demo post soni**: 10 – 300 orasida. Har post uchun 3–14 komment avtomatik
  yaratiladi.

### Qadam 4. "Ulash va ma'lumot yuklash"

1-2 soniya ichida:
- ConnectedAccount yaratiladi
- Realistik multi-til post va kommentlar generatsiya qilinadi
- **Har bir komment sentiment tahlili orqali o'tadi** (VADER / XLM-RoBERTa)
- Sizni `/social/` sahifasiga qaytaradi, toast xabari ko'rinadi

> **Demo rejim haqida.** Haqiqiy Instagram/YT/TG/X API credentials tashqi
> tomondan (Facebook Developer, Google Cloud, Bot tokens) sozlanishi kerak.
> Diplom demosi uchun yuqoridagi demo oqim to'liq yetarli — dashboardda real
> grafiklar, sentiment tahlili va eksport ishlaydi.

---

## 4. Analytics sahifasi

Sidebar → **Analytics** yoki `/analytics/`

Mazmuni:
- **3 KPI**: 30 kunlik postlar, layklar, ko'rishlar
- **30 kunlik tendensiya** (line chart — 3 qator: postlar, layklar, ko'rishlar)
- **Platforma jadvali**: har akkaunt bo'yicha postlar / layklar / engagement
- **Top 20 postlar**: engagement bo'yicha saralangan

---

## 5. Sentiment sahifasi

Sidebar → **Sentiment** yoki `/analytics/sentiment/`

Mazmuni:
- **3 katta tile**: pozitiv / neytral / negativ — foiz va komment soni
- **Donut chart**: umumiy taqsimot
- **Til matritsasi**: UZ/RU/EN har biri uchun sentiment foizlari
- **Eng pozitiv kommentlar** (top 5, sentiment skor bo'yicha)
- **Eng negativ kommentlar** (top 5)
- Sarlavhada: **"1983 ta komment tahlil qilindi · model: vader"**

> **Model tafsiloti.** Default VADER (ingliz + UZ/RU keyword kengaytma).
> `apps/analytics/services/sentiment.py` XLM-RoBERTa transformer'ni ham
> qo'llaydi — `python manage.py seed_demo_data --transformer` bilan
> faollashadi.

---

## 6. Hisobotlar (PDF va Excel)

Sidebar → **Hisobotlar** yoki `/reports/`

Ikkita eksport turi:

### Excel (.xlsx)

- 5 sheet: **Summary** (KPI), **Posts**, **Comments**, **Sentiment**
  (BarChart bilan), **Platforms** (PieChart bilan)
- Formatlangan: brand rangidagi header, number format, filter, frozen panes

### PDF

- 5 sahifa:
  1. **Cover** — brand gradient, email, sana
  2. **Executive summary** — 9 qatorli KPI jadvali
  3. **Platforma bo'yicha** — har akkaunt uchun satr
  4. **Sentiment tahlili** — foiz jadval + top 5 pozitiv + top 5 negativ
     komment
  5. **Top postlar** — layklar bo'yicha 15 qator
- Har sahifada pastda raqam va brand ma'lumoti

Tugmani bosing — brauzer darhol yuklab oladi.

---

## 7. Profil sozlamalari

Sidebar → **Profil** yoki `/settings/`

Bo'limlar:
- **Shaxsiy ma'lumot**: ism, familiya, email (o'zgartirish mumkin)
- **Parol**: parolni tiklash email orqali
- **Interfeys tili**: UZ / RU / EN
- **Mavzu**: Yorug' / Qorong'u / Avtomatik
- **Xavfli zona**: chiqish

---

## 8. Qo'shimcha imkoniyatlar

### Command palette (⌘K / Ctrl+K)

Istalgan sahifada `Ctrl+K` bosing. Oynada:
- Qidiruv input
- Navigation tezkor ro'yxat
- ↑↓ klavishlar bilan tanlash, Enter — ochish, Esc — yopish

### Til o'zgartirish

Yuqoridagi til dropdown'dan birini tanlang (UZ/RU/EN). Barcha matnlar
tarjima qilinadi.

### Dark mode

Oy 🌙 / quyosh ☀️ tugmasi — bir bosishda almashadi. Tanlov localStorage'da
saqlanadi.

### API

Developer dokumentatsiyasi: `/api/v1/docs/` (Swagger UI).

---

## 9. Chiqish

Sidebar pastida avatar yonida chiqish ikonkasi yoki `/accounts/logout/`
manzili.

---

## Muammo bo'lsa

- GitHub issue: https://github.com/Sardor2004777/social-media-analytics/issues
- Sayt URL'da `/admin/` — admin panel (superuser bo'lsangiz)
