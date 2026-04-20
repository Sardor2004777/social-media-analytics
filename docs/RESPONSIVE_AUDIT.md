# Responsive audit

**Sana:** 2026-04-20
**Metod:** template skani (Grep + Read), ikki audit skripti (`scripts/audit_live*.py`),
live HTML inspeksiyasi

## 1. Foundation

| Item | Status | Izoh |
|------|--------|------|
| `<meta name="viewport">` | ✅ `base.html:5` | `width=device-width, initial-scale=1.0` |
| `overflow-x` global himoyasi | ⚠️ `body`'ga qo'shish mumkin | Skanda haqiqiy overflow topilmadi, lekin belt-and-suspenders uchun `overflow-x-hidden` qo'shilsa zarar emas |
| Tailwind responsive breakpoints | ✅ Bor | `sm: md: lg: xl:` butun template'larda ishlatilgan |
| Dark mode responsive | ✅ Ishlaydi | har darajada tested |

## 2. Har sahifa bo'yicha

| Sahifa | 320px | 768px | 1024px | Izoh |
|--------|-------|-------|--------|------|
| `/` Landing | ⚠️ **NAVBAR MENU YO'Q** | ✅ | ✅ | Anon nav items `hidden md:flex` bilan mobile'da yo'qolgan, hamburger yo'q |
| Landing hero | ✅ `text-display-lg sm:display-xl lg:display-2xl` | ✅ | ✅ | Responsive text sizes to'g'ri |
| Landing bento features | ✅ `md:col-span-*` | ✅ | ✅ | 1 col mobile → 6 col md |
| Landing stats | ✅ `grid-cols-2 md:grid-cols-4` | ✅ | ✅ | 2x2 mobile → 1x4 md |
| Landing FAQ | ✅ `max-w-3xl` | ✅ | ✅ | markaz, cheklangan eni |
| Landing footer | ✅ `grid-cols-2 md:grid-cols-4` | ✅ | ✅ | |
| `/accounts/signup/` | ✅ `hidden lg:flex` brand panel | ✅ | ✅ | Form full-width mobile, split `lg+` |
| `/accounts/login/` | ✅ | ✅ | ✅ | Xuddi shunday |
| `/accounts/password/*` | ✅ | ✅ | ✅ | Auth base layout qo'llaniladi |
| `/dashboard/` (auth) | ✅ Alpine drawer | ✅ | ✅ | Sidebar `fixed` → `lg:static`, backdrop mobile'da |
| Dashboard KPI | ✅ `grid-cols-1 sm:grid-cols-2 xl:grid-cols-4` | ✅ | ✅ | To'g'ri progression |
| Dashboard charts | ✅ `grid-cols-1 xl:grid-cols-3` | ✅ | ✅ | Chart.js `responsive:true` yoqilgan |
| Dashboard top posts + timeline | ✅ `grid-cols-1 lg:grid-cols-5` | ✅ | ✅ | |
| Dashboard top posts rows | ⚠️ `<li class="flex">` | ✅ | ✅ | Ro'yxat, jadval emas — mobile'da ham OK, lekin kichik planshetda tor |
| `/social/` accounts table | ⚠️ `table` element | ⚠️ | ✅ | 320px'da jadval gorizontal overflow qilishi mumkin — `overflow-x-auto` wrapper bor |
| `/analytics/` per-platform table | ⚠️ `table` element | ⚠️ | ✅ | Xuddi shunday, `overflow-x-auto` himoyalagan |
| `/analytics/sentiment/` | ✅ `grid-cols-1 sm:grid-cols-3` | ✅ | ✅ | |
| `/reports/` | ✅ `grid-cols-1 md:grid-cols-2` | ✅ | ✅ | XLSX+PDF cards |
| `/settings/` | ✅ `grid-cols-1 lg:grid-cols-3` | ✅ | ✅ | Left rail + right sections |
| `/terms/`, `/privacy/` | ✅ `max-w-3xl mx-auto` | ✅ | ✅ | typography prose |
| 404 sahifa | ✅ `text-[9rem] sm:text-[14rem]` | ✅ | ✅ | |
| Command palette | ✅ | ✅ | ✅ | `max-w-xl` | Cmd+K tugma `hidden md:` (mobile'da kamida ishlamaydi — mantiqiy, mobile touch) |

## 3. Haqiqiy muammolar — tuzatish kerak

### Priority 1 — Landing navbar mobile hamburger

**Fayl**: `templates/partials/_navbar.html:16, 31`

Anon foydalanuvchi mobile'da landing'da: logo + "Kirish"/"Boshlash" tugmalari
ko'rinadi. Xususiyatlar / Qanday ishlaydi / Raqamlar / GitHub linklari
`hidden md:flex` orqali yashirin. Hamburger yo'q.

**Yechim**: Alpine.js bilan mobile menu drawer:
- Hamburger tugma (`md:hidden`)
- Bosilganda pastga ochiladigan panel
- ESC/tashqari bosish bilan yopiladi
- Auth user uchun ham (`lg:hidden`) — Dashboard/Analytics/Reports linklari

### Priority 2 — `body` overflow safety

**Fayl**: `templates/base.html:29`

Hozirgi: `class="h-full bg-slate-50 ... antialiased"`

**Yechim**: `overflow-x-hidden` qo'shish. Har qanday potensial x-overflow
(inline SVG, absolute elementlar, table) global sahifa'ni gorizontal
scroll qiluvchi qilmasin.

## 4. Ko'rib chiqildi, muammo emas

| Narsa | Tekshirildi | Natija |
|-------|-------------|--------|
| Jadval'lar mobile'da | `.overflow-x-auto` wrapper har table'da | ✅ lokal scroll, sahifa overflow qilmaydi |
| Sidebar mobile | Alpine `sidebarOpen` + `fixed` + backdrop | ✅ mukammal drawer |
| Auth split-layout | Brand panel `hidden lg:flex` mobile'da | ✅ mobile'da faqat form |
| Charts (Chart.js) | `responsive:true, maintainAspectRatio:false` | ✅ Container width 100% |
| Font sizes | `text-*` + `sm:text-*` bor | ✅ progression to'g'ri |
| Padding/margin | `py-12 sm:py-20 lg:py-32` pattern | ✅ |
| Touch target size | Tugmalar `px-4 py-2.5` = ~44px balandlik | ✅ |

## 5. Ataylab qilinmagan (past ta'sir)

| Narsa | Sabab |
|-------|-------|
| Top posts jadvalini mobile card'ga aylantirish | Hozirgi `<li class="flex">` mobile'da ham OK, jadval emas |
| Accounts jadvali mobile card | `overflow-x-auto` wrapper bor, mobile foydalanuvchi o'ngga scroll qiladi — noqulay emas |
| Settings tabs swipe | Hozirgi layout mobile'da vertikal stack, tablar emas |

---

## Xulosa

Saytning 90%+ responsive allaqachon to'g'ri. Ikki kichik tuzatish kerak:

1. **Landing navbar mobile hamburger** (priority 1) — jiddiy UX gap
2. **`body overflow-x-hidden`** (priority 2) — belt-and-suspenders

Ikki tuzatish ham keyingi commit'da.
