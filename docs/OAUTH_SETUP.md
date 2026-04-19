# OAuth va tashqi xizmatlar ulash qo'llanmasi

Loyiha bugungi kunda **demo rejimda** ishlaydi — "Ulash" tugmasi handle kiritishni
so'raydi va realistik soxta ma'lumot generatsiya qiladi. Bu komissiya demosi
uchun to'liq yetarli.

Agar **haqiqiy ijtimoiy tarmoq ma'lumoti** kerak bo'lsa (masalan, siz o'zingizning
haqiqiy Telegram kanalingiz ma'lumotini ko'rmoqchi bo'lsangiz), quyidagi
qo'llanmaga amal qiling.

Har qadam tashqi xizmat (Meta, Google, Telegram, SendGrid, hCaptcha) akkaunti
yaratishni talab qiladi. Kod allaqachon yozilgan — siz faqat Render'ning
**Environment** bo'limiga kerakli kalitlarni qo'ying, avtomatik redeploy
o'tkaziladi va haqiqiy OAuth faollashadi.

---

## 1. Google OAuth (eng oson — YouTube uchun ham ishlaydi)

Google Login — allauth orqali allaqachon ulangan. Sozlash uchun:

### 1.1 Google Cloud Console

1. https://console.cloud.google.com/ → **Create Project** → `social-analytics-prod`
2. **APIs & Services → OAuth consent screen** → External → loyiha nomini
   kiriting, support email, logo (ixtiyoriy).
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Web application**
   - Authorized redirect URIs:
     - `https://social-media-analytics-9rre.onrender.com/accounts/google/login/callback/`
     - (Lokal test uchun: `http://127.0.0.1:8000/accounts/google/login/callback/`)
4. Yaratilgan **Client ID** va **Client Secret**'ni saqlang.

### 1.2 Render env vars

Render dashboard → **Environment** → qo'shing:

```
GOOGLE_OAUTH_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com
GOOGLE_OAUTH_SECRET=GOCSPX-xxxxxxxxxxxxxxxxx
```

Saqlagach Render avtomatik redeploy qiladi va **Google orqali kirish/ro'yxatdan
o'tish** tugmasi `/accounts/login/` va `/accounts/signup/` sahifalarida aktivlashadi.

### 1.3 YouTube ma'lumoti olish uchun qo'shimcha

Google OAuth ishga tushgandan keyin YouTube Data API v3'ni yoqish:

1. Google Cloud Console → **Library** → "YouTube Data API v3" → **Enable**
2. Yuqoridagi OAuth scope'iga `https://www.googleapis.com/auth/youtube.readonly`
   qo'shing (OAuth consent screen → Add scope)

Bu bosqichdan keyin `apps/social/views.py`'dagi `/social/connect/youtube/`
flow'ni real OAuth'ga ulash uchun alohida PR kerak (hozir demo mode).

---

## 2. Telegram (bot token)

Telegram kanal ma'lumoti olish uchun bot kerak — app review jarayoni yo'q,
bot 2 daqiqada yaratiladi.

### 2.1 Bot yaratish

1. Telegram'da [@BotFather](https://t.me/BotFather) bilan suhbatlashing
2. `/newbot` → bot nomi va username bering (masalan `my_analytics_bot`)
3. @BotFather **HTTP API token** beradi — saqlang:
   ```
   123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

### 2.2 Telegram Login Widget (brauzerda login uchun)

1. @BotFather'da `/setdomain` → botga `social-media-analytics-9rre.onrender.com`
   domenini ulang
2. Render env'ga qo'shing:
   ```
   TELEGRAM_BOT_TOKEN=123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TELEGRAM_BOT_USERNAME=my_analytics_bot
   ```

Keyingi iteratsiyada `apps/social/views.py` Telegram Login Widget'ni
`/social/connect/telegram/`'ga ulaydi — foydalanuvchi Telegram brauzer pop-up
orqali bitta bosishda bog'lanadi.

### 2.3 Kanal ma'lumotini botga yuborish

Kanal statistikasi uchun botni o'sha kanalga admin qilib qo'shish kerak. Keyin
`getChatMemberCount`, `getChat`, `forwardMessage` kabi Bot API usullari
orqali kanal postlari va obunachilarini olish mumkin.

---

## 3. Instagram (Meta Business Suite)

**Eng qiyin yo'l**: Meta Business akkaunt, App yaratish, review jarayoni,
business verification.

### 3.1 Meta for Developers

1. https://developers.facebook.com/ → **My Apps → Create App**
2. Use case: "Other" → App type: "Business"
3. App display name: `Social Analytics`, email
4. **Add a product → Instagram Basic Display** (yoki Graph API)
5. **Instagram Basic Display → Basic Display → Create New App**
6. **Valid OAuth Redirect URIs**:
   - `https://social-media-analytics-9rre.onrender.com/accounts/social/instagram/callback/`
7. Instagram Tester qo'shing (siz sinashingiz kerak bo'lgan instagram akkaunt)
8. App Review: production'ga o'tkazish uchun `instagram_graph_user_profile` va
   `instagram_graph_user_media` scope'larni review'ga yuboring (7-14 kun)

### 3.2 Render env

```
META_APP_ID=123456789012345
META_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
META_REDIRECT_URI=https://social-media-analytics-9rre.onrender.com/accounts/social/instagram/callback/
```

### 3.3 Muqobil (tezroq): Graph API Explorer

Agar faqat o'zingizning akkauntingizda sinash kerak bo'lsa, Graph API Explorer
orqali long-lived access token olib, uni to'g'ridan-to'g'ri env'ga qo'yish
mumkin. Bu demo bosqich uchun xos, prod uchun emas.

---

## 4. X (Twitter) API

**Eng qimmat**: 2023 yildan Twitter API tekin tier cheklangan. Basic plan
$100/oy.

### 4.1 X Developer Portal

1. https://developer.x.com/ → account, tier tanlash
2. Project → App yaratish → OAuth 2.0 yoqish
3. Callback URL: `https://social-media-analytics-9rre.onrender.com/accounts/x/login/callback/`

### 4.2 Render env

```
X_CLIENT_ID=xxxxxxxxxxxxxxxxxxx
X_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Tavsiya**: diplom demosi uchun X qismi demo rejimda qoldirilsa, 100 $/oy
sarflashdan saqlanadi.

---

## 5. hCaptcha (spam himoyasi signup'da)

### 5.1 Kalit olish

1. https://hcaptcha.com/ → sign up (tekin)
2. Dashboard → **Sites → Add new site** → host: `social-media-analytics-9rre.onrender.com`
3. **Site Key** va **Secret Key** olinadi

### 5.2 Ulanish

```bash
pip install django-hcaptcha
```

`config/settings/base.py`:
```python
INSTALLED_APPS += ["hcaptcha"]
```

Render env:
```
HCAPTCHA_SITEKEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
HCAPTCHA_SECRET=0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Signup form'ga integration PR keyingi iteratsiyada.

---

## 6. SendGrid (real email — welcome, password reset)

### 6.1 Kalit olish

1. https://sendgrid.com/ → Free plan (100 email/kun)
2. **Settings → API Keys → Create API Key** (full access)
3. **Sender Authentication → Single Sender Verification** — `noreply@yourdomain.com`
   uchun email tasdiqlash

### 6.2 Render env

```
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEFAULT_FROM_EMAIL=Social Analytics <noreply@yourdomain.com>
```

**Muhim:** `EMAIL_HOST` o'rnatilgach `config/settings/prod.py` avtomatik SMTP
backend'ga o'tadi va `ACCOUNT_EMAIL_VERIFICATION` qayta `mandatory` bo'ladi
(yangi foydalanuvchi email tasdiqlashi majburiy).

---

## 7. Sentry (xato tracking)

### 7.1 Kalit

1. https://sentry.io/ → Free plan (5K event/oy)
2. Create project → Platform: **Django** → DSN olinadi

### 7.2 Render env

```
SENTRY_DSN=https://xxxxxxxxxxxxxxxxxxxx@o123456.ingest.sentry.io/1234567
SENTRY_ENVIRONMENT=production
```

Keyingi redeploy'da Sentry avtomatik xatolarni yuboradi (`config/settings/prod.py`'da
allaqachon sozlangan).

---

## 8. Xulosa

Hozirgi deploy'da **kalit talab qiladigan xizmatlar yo'q** — demo rejim 100%
ishlaydi. Tashqi integratsiyalar **ixtiyoriy qo'shimcha qatlam**: birortasini
yoqsangiz ham shu sessiyaning kodi qayta yozilmaydi.

Tavsiya etilgan tartib (eng oson → eng qiyin):

1. **Sentry** (5 daqiqa) — production xatolari ko'rinsin
2. **Google OAuth** (20 daqiqa) — Google bilan kirish/ro'yxatdan o'tish +
   YouTube data olish uchun asos
3. **SendGrid** (15 daqiqa) — haqiqiy email (welcome, password reset)
4. **Telegram Bot** (5 daqiqa) — o'z kanalingiz ma'lumoti
5. **hCaptcha** (10 daqiqa) — spam himoyasi
6. **Instagram** (7-14 kun — Meta review jarayoni)
7. **X/Twitter** (qimmat — diplom demosi uchun shart emas)

Sizda kalit bo'lgan zahoti men "haqiqiy" integratsiyani alohida PR sifatida
qo'shaman — demo rejim ham parallel ishlashda davom etadi.
