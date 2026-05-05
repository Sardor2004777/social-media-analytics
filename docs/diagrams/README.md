# Loyiha diagrammalari

"Social Analytics" diplom loyihasining texnik diagrammalari. Hammasi
Mermaid sintaksida yozilgan — GitHub bu blokni avtomatik render qiladi
va loyihaning Word hujjatiga PNG sifatida qo'shilgan.

Mermaid manba fayllar (`*.mmd`) shu papkada saqlanadi va PNG/SVG
ko'rinishlari `mermaid.ink` orqali render qilinadi.

---

## 2.4-rasm. Ma'lumotlar bazasi sxemasi (ER-diagram)

Foydalanuvchi → Akkaunt → Post → Komment → Sentiment zanjirini
ko'rsatadi. Asosiy entity'lar va ular orasidagi munosabatlar
(one-to-many, optional) Crow's-foot belgilashida tasvirlangan.

```mermaid
erDiagram
    USER ||--o{ SOCIAL_ACCOUNT : "ega"
    SOCIAL_ACCOUNT ||--o{ POST : "joylaydi"
    POST ||--o{ COMMENT : "uchun yoziladi"
    COMMENT ||--o| SENTIMENT_RESULT : "tahlil qilinadi"
    SOCIAL_ACCOUNT ||--o{ FOLLOWER_SNAPSHOT : "vaqtga bog'liq"
    USER ||--o{ ACTIVITY_LOG : "harakatlari"
    USER ||--o{ ALERT : "bildirishnomalari"
    USER ||--o{ SAVED_VIEW : "filterlari"

    USER {
        int id PK
        string email UK "Login identifikatori"
        string language "uz|ru|en"
        string timezone "Asia/Tashkent"
        string totp_secret "Fernet shifrlangan"
        bool totp_enabled
        bool is_demo
        datetime created_at
    }

    SOCIAL_ACCOUNT {
        int id PK
        int user_id FK
        string platform "telegram|instagram|youtube|vk|x"
        string handle "Public @username"
        string external_id "Platforma id"
        binary access_token "Fernet"
        binary refresh_token "Fernet"
        int follower_count
        bool is_active
        bool is_demo
        datetime updated_at
    }

    POST {
        int id PK
        int account_id FK
        string external_id UK
        string post_type "photo|video|reel|tweet|channel_post"
        text caption
        url url
        int likes
        int views
        int comments_count
        int shares
        float engagement_rate
        datetime published_at
    }

    COMMENT {
        int id PK
        int post_id FK
        string external_id
        string author_handle
        text body
        string language
        int likes
        datetime published_at
    }

    SENTIMENT_RESULT {
        int id PK
        int comment_id FK
        string label "positive|neutral|negative"
        float score "compound"
        string model_name "vader|xlm-roberta"
        datetime created_at
    }

    FOLLOWER_SNAPSHOT {
        int id PK
        int account_id FK
        date date
        int count
    }

    ACTIVITY_LOG {
        int id PK
        int user_id FK
        string kind "login|connect|sync|ai|2fa"
        string message
        json meta
        string ip
        datetime created_at
    }

    ALERT {
        int id PK
        int account_id FK
        string metric
        string direction "spike|drop"
        string severity
        float value
        float baseline
        float z_score
        string message
        datetime detected_for
    }

    SAVED_VIEW {
        int id PK
        int user_id FK
        string page
        string name
        string query
        datetime created_at
    }
```

---

## 2.5-rasm. Tizim arxitekturasi (4-qatlamli + DDD apps)

To'rt qatlamli yondashuv: prezentatsiya → biznes mantiq → asinxron task
queue → ma'lumot. Tashqi servislar (AI, SMTP) alohida qatlamda
ko'rsatilgan. Har bir Django app o'z chegarasiga ega (Domain-Driven
Design).

```mermaid
graph TB
    subgraph "Prezentatsiya qatlami"
        UI["Foydalanuvchi brauzeri<br/>Tailwind + Alpine.js + HTMX"]
        PWA["PWA (manifest + sw.js)<br/>Mobil home-screen"]
    end

    subgraph "Biznes mantiq qatlami — Django 5"
        URLS["URL Router<br/>i18n_patterns: /uz/ /ru/ /en/"]
        VIEWS["Views<br/>apps/dashboard apps/analytics<br/>apps/social apps/accounts"]
        SVC["Service layer<br/>chat best_time recommendations<br/>sentiment wordcloud"]
        AUTH["Auth + 2FA<br/>django-allauth + pyotp TOTP"]
    end

    subgraph "Asinxron qatlam"
        CELERY["Celery + Redis<br/>fetch_account_data<br/>fetch_all_data Beat 6h"]
        COLLECTORS["Collectors<br/>Telegram MTProto<br/>YouTube Data API v3<br/>VK API v5.131"]
    end

    subgraph "Ma'lumot qatlami"
        DB[("PostgreSQL 16<br/>User SocialAccount Post<br/>Comment SentimentResult Alert")]
        CACHE[("Redis cache<br/>recipes recommendations")]
        FERNET["Fernet shifrlash<br/>OAuth tokenlar TOTP secret"]
    end

    subgraph "Tashqi servislar"
        AI["OpenAI-compatible AI<br/>Gemini primary + Groq backup"]
        SMTP["SMTP<br/>Sentiment alert email"]
    end

    UI --> URLS
    PWA --> URLS
    URLS --> VIEWS
    VIEWS --> AUTH
    VIEWS --> SVC
    SVC --> DB
    SVC --> CACHE
    SVC --> AI
    VIEWS --> CELERY
    CELERY --> COLLECTORS
    COLLECTORS --> DB
    DB --> FERNET
    AUTH --> DB
    CELERY --> SMTP

    classDef pres fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e
    classDef biz fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef async fill:#fce7f3,stroke:#db2777,color:#831843
    classDef data fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef ext fill:#ede9fe,stroke:#7c3aed,color:#3730a3

    class UI,PWA pres
    class URLS,VIEWS,SVC,AUTH biz
    class CELERY,COLLECTORS async
    class DB,CACHE,FERNET data
    class AI,SMTP ext
```

---

## 2.7-rasm. Ma'lumot oqimi — foydalanuvchi so'rovidan natijagacha

Sequence diagrammada ikkita oqim ko'rsatiladi:
- **Foydalanuvchi so'rovi**: brauzerdan analytics sahifasini yuklash
  jarayoni, cache → DB → render zanjiri.
- **Fonda yig'ish**: Celery Beat har 6 soatda barcha akkauntlarni sync
  qiladi va sentiment tahlilini ishga tushiradi.

```mermaid
sequenceDiagram
    autonumber
    actor User as Foydalanuvchi
    participant B as Brauzer
    participant N as Nginx + Whitenoise
    participant D as Django (Gunicorn)
    participant V as View + Service
    participant C as Cache (Redis)
    participant DB as PostgreSQL
    participant Q as Celery worker
    participant API as Tashqi API<br/>(YouTube/Telegram/VK)

    User->>B: /en/analytics/ ochadi
    B->>N: HTTPS GET /en/analytics/
    N->>D: WSGI request
    D->>V: route → analytics_overview
    V->>C: cache.get("kpis:user_id")
    alt Cache hit
        C-->>V: KPI dict
    else Cache miss
        V->>DB: SELECT posts, comments, sentiment
        DB-->>V: rowlar
        V->>V: aggregate, format
        V->>C: cache.set 5 daqiqa
    end
    V-->>D: render(template, ctx)
    D-->>N: HTML 200
    N-->>B: gzip + WhiteNoise statik
    B-->>User: KPI cards, charts, grafiklar

    Note over Q,API: Fonda har 6 soatda
    Q->>DB: filter(is_active=True)
    DB-->>Q: SocialAccount ro'yxati
    loop har akkaunt
        Q->>API: fetch_posts() / fetch_comments()
        API-->>Q: JSON
        Q->>DB: bulk_create + update_or_create
        Q->>Q: VADER / XLM-RoBERTa sentiment
        Q->>DB: SentimentResult yozish
    end
    Q->>D: anomaly detect → Alert yaratish
```

---

## 2.8-rasm. Monitoring va observability arxitekturasi

Uch darajali yondashuv: manba (app/worker/db) → yig'ish (logger,
Sentry, ActivityLog) → saqlash (Render Logs, Sentry Cloud, PostgreSQL)
→ foydalanuvchi (developer alertlari, foydalanuvchi tarixi sahifasi,
admin paneli).

```mermaid
graph LR
    subgraph "Manba qatlami"
        APP["Django<br/>Gunicorn workers"]
        WORK["Celery worker"]
        DB[("PostgreSQL")]
    end

    subgraph "Yig'ish qatlami"
        LOG["Logging<br/>structlog JSON"]
        SENTRY["Sentry<br/>sentry-sdk[django]"]
        ACTIVITY["ActivityLog<br/>apps.core.models"]
    end

    subgraph "Saqlash qatlami"
        SLOG[("Render Logs<br/>14 kun ushlaydi")]
        SCLOUD[("Sentry Cloud<br/>error events + performance")]
        SDB[("PostgreSQL<br/>activity log table")]
    end

    subgraph "Foydalanuvchi qatlami"
        DEV["Diplom muallifi<br/>error alertlari, trace"]
        USER["Foydalanuvchi<br/>/settings/activity/ sahifasi"]
        ADMIN["Admin paneli<br/>django.contrib.admin"]
    end

    APP --> LOG
    APP --> SENTRY
    APP --> ACTIVITY
    WORK --> LOG
    WORK --> SENTRY
    DB --> ACTIVITY

    LOG --> SLOG
    SENTRY --> SCLOUD
    ACTIVITY --> SDB

    SCLOUD --> DEV
    SLOG --> DEV
    SDB --> USER
    SDB --> ADMIN

    classDef src fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef collect fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e
    classDef store fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef consume fill:#fce7f3,stroke:#db2777,color:#831843

    class APP,WORK,DB src
    class LOG,SENTRY,ACTIVITY collect
    class SLOG,SCLOUD,SDB store
    class DEV,USER,ADMIN consume
```
