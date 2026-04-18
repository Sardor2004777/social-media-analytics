# Data model

> **Status:** Phase 4 (social + collectors) va Phase 5 (analytics)'da to'ldiriladi. Bu skeleton hozirgi mavjud model'larni va rejalashtirilgan model'larni hujjatlaydi.

## 1. Mavjud modellar (Phase 2)

### `core.TimestampedModel` (abstract)

Barcha boshqa model'lar uchun asos. `created_at` + `updated_at` maydonlari.

```python
class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

### `accounts.User`

`AbstractUser`'ni `email` unique + `USERNAME_FIELD = "email"` bilan kengaytiruvchi custom user.

| Maydon | Tur | Izoh |
|--------|-----|------|
| `id` | BigAutoField | PK |
| `email` | EmailField (unique) | Login identifikatori |
| `username` | CharField (unique) | Saqlanib qoladi, lekin login uchun ishlatilmaydi |
| `password` | CharField | Hashed (PBKDF2) |
| Qolganlari — Django'ning `AbstractUser`'idan ($first_name, $last_name, $is_staff, va h.k.) |

`db_table = "accounts_user"` — default `auth_user`ni almashtiradi.

---

## 2. Rejalashtirilgan modellar (Phase 4+)

### `accounts.Profile` (Phase 3)

| Maydon | Tur | Izoh |
|--------|-----|------|
| `user` | OneToOne → User | |
| `display_name` | CharField(100) | |
| `avatar` | ImageField | |
| `preferred_language` | CharField(2), choices=['uz','ru','en'] | |
| `timezone` | CharField | Default `Asia/Tashkent` |

### `social.SocialAccount` (Phase 4)

Bir user → ko'p SocialAccount (IG, TG, YT, X).

| Maydon | Tur | Izoh |
|--------|-----|------|
| `user` | FK → User | |
| `platform` | CharField, choices=['instagram','telegram','youtube','x'] | |
| `external_id` | CharField | IG: page_id, TG: chat_id, va h.k. |
| `handle` | CharField | @username |
| `access_token` | EncryptedCharField (Fernet) | DB'da shifrlangan |
| `refresh_token` | EncryptedCharField (Fernet, nullable) | |
| `token_expires_at` | DateTimeField (nullable) | |
| `status` | CharField, choices=['active','expired','revoked'] | |
| `last_collected_at` | DateTimeField (nullable) | |
| `meta` | JSONField | Platform-specific metadata |

**Index:** `(user, platform)`, `(status, last_collected_at)` (scheduler uchun)

### `social.ConnectionAttempt` (Phase 4)

OAuth urinishlari logi — debug + audit.

### `collectors.RawPost` (Phase 4)

Platform'dan ko'chirilgan xom post.

| Maydon | Tur |
|--------|-----|
| `account` | FK → SocialAccount |
| `external_id` | CharField, unique_together=(account, external_id) |
| `published_at` | DateTimeField (index) |
| `text` | TextField |
| `media_type` | CharField |
| `likes_count`, `comments_count`, `shares_count` | PositiveIntegerField |
| `raw` | JSONField — to'liq API response |

### `collectors.RawComment` (Phase 4)

Post kommentlari — sentiment analysis manbai.

### `collectors.RawFollowerSnapshot` (Phase 4)

Har collection cycle'da bitta snapshot — follower o'sishini trace qilish.

### `analytics.DailyAccountMetric` (Phase 5)

Pre-computed agregat, dashboard speed uchun.

| Maydon | Tur |
|--------|-----|
| `account` | FK → SocialAccount |
| `date` | DateField |
| `posts_count`, `likes_total`, `comments_total`, `shares_total` | Integer |
| `follower_count` | Integer (snapshot) |
| `follower_delta` | Integer |
| `engagement_rate` | Decimal(5,4) |

**Index:** `unique_together=(account, date)`, index on `date`.

### `analytics.HourlyActivityBucket` (Phase 5)

24×7 heatmap uchun — `(account, weekday, hour) → post_count, avg_engagement`.

### `analytics.PostPerformance` (Phase 5)

OneToOne → RawPost, enriched with sentiment va normalized engagement.

### `analytics.SentimentAggregate` (Phase 5)

Kunlik sentiment rollup: `(account, date) → {positive_pct, neutral_pct, negative_pct, comment_count}`.

### `reports.Report` (Phase 7)

| Maydon | Tur |
|--------|-----|
| `user` | FK → User |
| `account` | FK → SocialAccount (nullable — multi-account) |
| `format` | CharField, choices=['pdf','xlsx'] |
| `period_start`, `period_end` | DateField |
| `file` | FileField |
| `status` | CharField, choices=['pending','ready','failed'] |
| `generated_at` | DateTimeField (nullable) |

---

## 3. ERD

Phase 4'dan keyin bu yerga diagramma qo'shiladi (Mermaid yoki dbdiagram.io export).

## 4. Migration strategiyasi

- Har app — mustaqil migration zanjiri
- `social.SocialAccount.access_token` — Fernet shifrlash, migration'da `ENCRYPTION_KEY` env'i majburiy
- Data migration'lar (agar kerak bo'lsa) — alohida `data_*.py` fayllarda
- `makemigrations --check` CI'da yoqilgan — drift'ga yo'l qo'yilmaydi
