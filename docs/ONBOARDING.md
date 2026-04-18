# Tashqi platformalar uchun onboarding

> **Status:** Phase 4'da to'ldiriladi. Bu qo'llanma — ishlab chiqaruvchi / demo o'tkazuvchi uchun.

## 1. Instagram (Meta Graph API)

Instagram Basic Display API **deprecate** qilindi (2024). Biz **Instagram Graph API** ishlatamiz — bu **Business** yoki **Creator** account talab qiladi.

### 1.1 Facebook Developer Account
1. [developers.facebook.com](https://developers.facebook.com) — ro'yxatdan o'tish
2. **My Apps → Create App → Business** type
3. **Add Product → Instagram Graph API**

### 1.2 Instagram Business akkaunt tayyorlash

Demo/test uchun:
1. Instagram mobil app'da **Settings → Account → Switch to Professional Account → Business**
2. Facebook Page'ga ulash (yangi yoki mavjud)
3. Page + IG akkaunt bir Facebook Business hisobida bo'lishi kerak

### 1.3 Meta App sozlash

App dashboard'da:
1. **Settings → Basic** — `App ID` va `App Secret` — `.env`'ga yozish (`META_APP_ID`, `META_APP_SECRET`)
2. **Instagram Graph API → Settings** — Valid OAuth Redirect URIs:
   - Local: `http://localhost:8000/social/callback/instagram/`
   - Prod: `https://your-domain.com/social/callback/instagram/`
3. **Roles → Roles** — test user (Instagram Business akkaunt egasi) qo'shish
4. **App Review → Permissions**:
   - `instagram_basic`
   - `instagram_manage_insights`
   - `pages_show_list`
   - `pages_read_engagement`

> **Diplom demo'si uchun:** App Review'dan o'tmasdan — test user'lar bilan "Development mode"da ishlatiladi.

### 1.4 Token

- Short-lived token — 1 soat
- Long-lived token — 60 kun (biz shu bilan saqlaymiz)
- Exchange flow: `/oauth/access_token` endpoint

---

## 2. Telegram Bot API

Instagram'dan osonroq — ruxsatlar admin bo'lish orqali.

### 2.1 Bot yaratish
1. [@BotFather](https://t.me/BotFather) — `/newbot`
2. Bot nomi + username → **token** oladi

### 2.2 User flow

Bizning tizimda:
1. User "Telegram ulash" → bot username ko'rsatiladi (`@your_bot`)
2. User bot'ni o'z kanal/guruhiga **admin** qilib qo'shadi (insight uchun shart)
3. User UI'da bot token'ini kiritadi (yoki — agar platform bot ishlatilsa, chat_id)
4. Bizning tizim `getChat`, `getUpdates`, `getChatMemberCount` orqali poll qiladi

### 2.3 Cheklovlar

Telegram Bot API'da:
- Post'lar faqat bot admin bo'lgan **channel'lar** uchun (shaxsiy chat yo'q)
- Comment = channel post'ga reply (discussion group orqali)
- Subscriber demografiya yo'q — faqat total count

### 2.4 MTProto alternativasi

Chuqur analytics uchun (shaxsiy akkaunt, to'liq post history) — `Telethon` (MTProto). Phase 4'da Bot API yetarli, Phase 5+ ehtimol qo'shiladi.

---

## 3. YouTube Data API v3

Phase 4'dan keyingi faza — skeleton.

1. [Google Cloud Console](https://console.cloud.google.com) → new project
2. **APIs & Services → Enable → YouTube Data API v3**
3. **Credentials → OAuth 2.0 Client ID**
4. Redirect URI: `https://your-domain/social/callback/youtube/`
5. `.env`: `YOUTUBE_OAUTH_CLIENT_ID`, `YOUTUBE_OAUTH_SECRET`, `YOUTUBE_API_KEY`

Quota: 10,000 unit/kun (1 video list = 1 unit, 1 search = 100 unit).

---

## 4. X (Twitter) API v2

Phase 4'dan keyingi faza — ikkilanyapmiz (paid plan bo'lib ketdi).

- Free tier: 500 tweet/oy read (juda cheklangan)
- Basic tier: $200/oy — 15,000 read

Diplom uchun ehtimol X **scope'dan chiqariladi** — Phase 1 qaroriga mos (IG + TG fokus).

---

## 5. Sentiment API (HuggingFace)

Prod'da lokal transformers o'rniga HF Inference API.

1. [huggingface.co](https://huggingface.co) → sign up
2. **Settings → Access Tokens → New token** (Read scope)
3. `.env`: `HF_API_TOKEN=hf_...`, `SENTIMENT_BACKEND=api`

Model: `cardiffnlp/twitter-xlm-roberta-base-sentiment`.
Free tier: 30,000 chars/oy — diplom demo'si uchun yetarli.

---

## 6. Email — SendGrid

1. [sendgrid.com](https://sendgrid.com) → free tier (100 email/kun)
2. **Settings → API Keys → Create → Full access**
3. Sender verification: `noreply@your-domain.com` (DKIM/SPF DNS yozuvlari)
4. `.env`: `EMAIL_HOST_PASSWORD=<api-key>`
