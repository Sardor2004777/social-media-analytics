# Telegram Real-Mode Setup

Bu qo'llanma **Telegram real-mode** ni yoqish uchun — dashboard har qanday
**public** Telegram kanaldan (masalan `@durov`, `@telegram`) real post'lar,
ko'rishlar, reaksiyalar va komment sonini tortib oladi. Agar bu setup
to'liq yakunlanmasa, Telegram demo seeder'ga (soxta ma'lumot) qaytadi.

## Arxitektura

Real-mode **MTProto** (Telegram'ning native protokoli) va [Telethon](https://docs.telethon.dev/)
dan foydalanadi. **Bitta server-side user session** barcha foydalanuvchilar
uchun public kanallarni o'qiydi — foydalanuvchilar bot yaratishi yoki OAuth
orqali o'tishi shart emas. Siz (platforma operatori sifatida) bir marta o'z
Telegram akkauntingiz bilan kirishingiz kerak; session string `.env`'ga
yoziladi va barcha collector'lar shuni ishlatadi.

> ⚠ **ToS eslatma:** Telegram ToS'i user-account automation'ga shaxsiy
> foydalanish uchun ruxsat beradi. Commercial/production deploy uchun Bot API
> yondashuviga o'tish tavsiya etiladi (per-channel bot admin modeli).
> Diploma / demo uchun bu to'liq mos.

## Bir martalik setup

### 1. API ma'lumotlarini olish

<https://my.telegram.org/apps> ga kiring, telefon raqamingiz bilan login
qiling va yangi ilova yarating (nomi, short-name, URL — har qanday). So'ng:

- `App api_id` → `TELEGRAM_API_ID`
- `App api_hash` → `TELEGRAM_API_HASH`

`.env` fayliga yozing:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef0123456789abcdef0123456789
```

### 2. Session string yarating

Management command'ni ishga tushiring:

```bash
python manage.py telegram_generate_session
```

Sizdan so'raladi:

- Telefon raqamingiz (format: `+998901234567`)
- Telegram yuborgan SMS-kod
- 2FA paroli (agar akkauntingizda yoqilgan bo'lsa)

Muvaffaqiyatli yakunlansa, uzun base64 session string chop etiladi. Uni
`.env`'ga ko'chiring:

```env
TELEGRAM_SESSION_STRING=1A2B3C...
```

> 🔒 **Xavfsizlik:** bu string Telegram akkauntingizga to'liq kirish beradi.
> Hech qachon commit qilmang, ulashmang, chat'larga yopishtirmang.

### 3. Server va Celery worker'ni qayta ishga tushiring

```bash
# Django dev server
python manage.py runserver

# Celery worker (boshqa terminalda)
celery -A config worker -Q collectors -l info
```

### 4. Kanalni ulang

Ilovaga kiring → **Connected accounts** → **Telegram** → **Connect** — har
qanday public kanalning `@username`'ini kiriting (masalan `@durov`,
`@telegram`, yoki o'zingizning kanalingiz).

Orqada nima sodir bo'ladi:

1. `account_connect` view `TelegramCollector.fetch_channel_info()`'ni chaqirib,
   kanal mavjudligini tekshiradi va metadata o'qiydi.
2. `ConnectedAccount` yozuvi `is_demo=False` bilan yaratiladi.
3. `sync_telegram_account` Celery task navbatga qo'yiladi (`post_limit=<slider>`).
4. Celery worker oxirgi N ta xabarni tortib olib, `Post` yozuvlariga yozadi.
5. Dashboard keyingi refresh'da real ma'lumotni ko'rsatadi.

## Qo'lda test qilish

Celery worker ishlamasdan sinxron sync qilish uchun:

```bash
python manage.py sync_telegram <account_id>
python manage.py sync_telegram <account_id> --limit 100
```

## Muammolarni hal qilish

| Xato | Yechim |
|---|---|
| `TELEGRAM_API_ID va TELEGRAM_API_HASH .env fayliga yozilmagan` | 1-qadamni yakunlang. |
| `Telegram session not authorised` | `telegram_generate_session` ni qayta ishga tushiring — session tugagan yoki bekor qilingan. |
| `@X Telegram kanali emas` | User yoki basic group kiritilgan — faqat channel/supergroup qo'llab-quvvatlanadi. |
| `Kanal ochilmadi: ChannelPrivateError` | Kanal yopiq — faqat public kanallar ishlaydi. |
| `FloodWaitError: ... seconds` | Telegram rate-limit qildi; ko'rsatilgan soniya kuting. |

## Demo-mode'ga qaytish

`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, yoki `TELEGRAM_SESSION_STRING` dan
hech bo'lmasa bittasini bo'sh qoldiring. Connect form avtomatik ravishda
demo seeder'ga qaytadi (offline demo yoki CI uchun qulay).

## Periodic sync (ixtiyoriy, Phase 5+)

Har `COLLECT_INTERVAL_HOURS` soatda barcha real Telegram akkauntlarni
yangilash uchun, Django admin → **Periodic Tasks** orqali
`apps.collectors.tasks.sync_all_telegram_accounts` fan-out task'ni rejalashtiring.
