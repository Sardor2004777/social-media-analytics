# REST API v1

> **Status:** Phase 8'da to'ldiriladi. Hozir faqat JWT auth endpoint'lari + Swagger UI skeleton.

## 1. Base URL

```
https://your-domain/api/v1/
```

Local dev: `http://localhost:8000/api/v1/`

## 2. Hujjatlar (auto-generated)

| URL | Mazmuni |
|-----|---------|
| `/api/v1/schema/` | OpenAPI 3 schema (YAML/JSON) |
| `/api/v1/docs/` | Swagger UI |
| `/api/v1/redoc/` | ReDoc UI |

## 3. Autentifikatsiya

API faqat JWT orqali ishlaydi (session auth ham qo'llaniladi — lekin faqat admin debug uchun).

### Token olish

```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "..."
}
```

Javob:
```json
{
  "access": "eyJ0eXAiOiJKV1Qi...",
  "refresh": "eyJ0eXAiOiJKV1Qi..."
}
```

- `access` — 60 daqiqa amal qiladi
- `refresh` — 14 kun, rotation bilan (har refresh'da yangi access + yangi refresh)

### Token yangilash

```http
POST /api/v1/auth/token/refresh/
Content-Type: application/json

{ "refresh": "..." }
```

### Protected endpoint'ga so'rov

```http
GET /api/v1/accounts/
Authorization: Bearer <access_token>
```

## 4. Throttling

| Tip | Limit |
|-----|-------|
| Authenticated user | 1000 so'rov / kun |
| Anonymous | 100 so'rov / kun |

429 response + `Retry-After` header.

## 5. Rejalashtirilgan resurslar (Phase 8)

| Endpoint | Method | Tavsif |
|----------|--------|--------|
| `/api/v1/social-accounts/` | GET, POST | Ulangan akkauntlar |
| `/api/v1/social-accounts/{id}/` | GET, DELETE | Bitta akkaunt |
| `/api/v1/social-accounts/{id}/refresh/` | POST | Qo'lda ma'lumot yig'ish |
| `/api/v1/analytics/daily/` | GET | DailyAccountMetric list (filter by account, date range) |
| `/api/v1/analytics/hourly-heatmap/` | GET | HourlyActivityBucket aggregate |
| `/api/v1/analytics/top-posts/` | GET | Top N posts (engagement bo'yicha) |
| `/api/v1/analytics/sentiment/` | GET | SentimentAggregate timeseries |
| `/api/v1/reports/` | GET, POST | Hisobotlar ro'yxati + yaratish |
| `/api/v1/reports/{id}/` | GET | Bitta hisobot |
| `/api/v1/reports/{id}/download/` | GET | Fayl yuklab olish |

Barchasi `IsAuthenticated + OwnerOnlyFilter` bilan — foydalanuvchi faqat o'z ma'lumotini ko'radi.

## 6. Pagination

`PageNumberPagination`, default `PAGE_SIZE=25`, max 100.

```
GET /api/v1/analytics/daily/?page=2&page_size=50
```

## 7. Filtering + ordering

`django-filter` orqali — har endpoint'da `?field=value` query param'lari.

```
GET /api/v1/analytics/daily/?account=3&date__gte=2026-01-01&ordering=-date
```

## 8. Xatoliklar

Standard DRF format:
```json
{
  "detail": "Not authenticated.",
  "code": "not_authenticated"
}
```

Validation errors — field-level:
```json
{
  "email": ["This field is required."],
  "password": ["Too short (min 8)."]
}
```

## 9. Versioning

URL-based: `/api/v1/`. v2 kelganda v1 deprecate qilinadi (6 oy cadence).
