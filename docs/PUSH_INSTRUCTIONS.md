# GitHub'ga push qilish (qo'lda, sizning terminalingizda)

> **Nega qo'lda?** Hozirgi sessionda shell Cyrillic user path (`C:\Users\Адмим`) sababli bloklangan. Quyidagi buyruqlar sizning lokal Git Bash / PowerShell'ingizda ishlaydi.

## 0. Tekshirish (bir marta)

Shu uchta buyruqni ishga tushiring va natijalarni menga jo'nating — agar biror nima yo'q bo'lsa, davom etishdan oldin tuzatamiz:

```bash
git --version
git config --global user.name
git config --global user.email
```

**Agar `user.name` / `user.email` bo'sh bo'lsa**, o'rnating:

```bash
git config --global user.name "Sardor"
git config --global user.email "your-github-email@example.com"
```

GitHub auth — ikki yo'l:

**(A) HTTPS token** — [github.com/settings/tokens](https://github.com/settings/tokens) → "Generate new token (classic)" → `repo` scope → copy. Keyinchalik push qilganda username + token so'raladi.

**(B) GitHub CLI** — tez. Agar `gh --version` ishlasa:
```bash
gh auth login
# Soniyada: GitHub.com → HTTPS → browser login
```

## 1. Lokal virtualenv'da oxirgi tekshiruv (majburiy)

Push qilishdan oldin — **albatta bu buyruqlarni ishga tushiring**:

```bash
cd C:\Users\Адмим\Desktop\social-analytics

# Virtualenv
python -m venv .venv
.venv\Scripts\activate

# Deps
pip install -r requirements/dev.txt

# Migration drift check — "No changes detected" chiqishi kerak
python manage.py makemigrations --check --dry-run

# Agar drift bo'lsa (modelim migration'ga to'liq mos emas):
# python manage.py makemigrations accounts
# (bu yangi fayl yaratadi, eski 0001_initial.py'ni almashtirmaydi — xavfsiz)

# Smoke test
pytest -x -v
```

Agar hamma narsa yashil bo'lsa, davom eting. Agar xato bo'lsa — natijani menga jo'nating.

## 2. Git init + first commit

```bash
cd C:\Users\Адмим\Desktop\social-analytics

# Git repo'ni boshlash
git init -b main

# .env fayl bo'lishi mumkin — gitignore sezadi, lekin yaxshilik uchun tekshirib ko'rish:
git status | grep ".env$" && echo "OGOHLANTIRISH: .env gitignore'da yo'q!" || echo "OK — .env himoyalangan"

# Barcha fayllarni qo'shish
git add .

# Statusni ko'rish — .env YO'Qligiga ishonch hosil qiling
git status
```

## 3. Commit

```bash
git commit -m "feat(skeleton): Phase 2 — Django project, Docker, CI, i18n foundation

- Django 5.2 + DRF + allauth + Celery + drf-spectacular wired up
- Split settings (base/dev/prod/test) with django-environ
- Custom User model (email as USERNAME_FIELD) + initial migration
- Docker multi-stage (dev/prod) + docker-compose (web/worker/beat/postgres/redis)
- Railway deployment config (railway.toml + Procfile)
- GitHub Actions CI: ruff, black, pytest with coverage, migration drift check
- pre-commit hooks (ruff, black, djlint)
- i18n skeleton for uz/ru/en with LANGUAGE_CODE=uz, Asia/Tashkent TZ
- Security headers for prod (HSTS, secure cookies, CSRF trusted origins)
- Sentry integration (prod only)
- Per-app test folders for accounts + core
- Architecture, deployment, data model, API, onboarding docs"
```

## 4. Remote qo'shib push qilish

GitHub'da repo **bo'sh** yoki **mavjud** — ikki stsenariy:

### 4A. Repo BO'SH (README ham yo'q)

```bash
git remote add origin https://github.com/Sardor2004777/social-media-analytics.git
git push -u origin main
```

### 4B. Repo'da allaqachon kontent bor

Birinchi bu kontentni ko'rib chiqing (balki loyiha qisman bor, balki boshqa narsa). Agar **bilasiz** hozirgi mahalliy versiya to'g'ri va GitHub'dagini almashtiramiz:

```bash
git remote add origin https://github.com/Sardor2004777/social-media-analytics.git
git push -u origin main --force
```

> **⚠️ `--force` ogohlantirish:** GitHub'dagi eski kodni **butunlay o'chiradi**. Faqat shu narsa ehtiyojmi — tasdiqlash.

Agar GitHub'dagi kontentni **saqlamoqchi bo'lsangiz** — menga ayting, strategiya boshqacha bo'ladi (pull + rebase + merge).

## 5. Verifikatsiya

```bash
git log --oneline -5
git remote -v
# Brauzerda: https://github.com/Sardor2004777/social-media-analytics
```

CI Actions avtomatik ishga tushadi — Actions tabida holatni ko'rishingiz mumkin.

---

## Tez-tez uchrab turadigan muammolar

**"Support for password authentication was removed"** — HTTPS'ga password o'rniga Personal Access Token kerak (bo'lim 0).

**"Permission denied (publickey)"** — SSH key sozlanmagan. `gh auth login` yoki HTTPS ishlating.

**"failed to push some refs"** — remote'da yangiroq commit bor. Force push (ehtiyot) yoki pull-rebase.

**`makemigrations` drift** — Agar lokalda `python manage.py makemigrations --check` xato bersa — `makemigrations accounts` chaqiring. Yangi migration fayli yaratiladi; eski `0001_initial.py` + yangi `0002_*.py` birga commit qiling.
