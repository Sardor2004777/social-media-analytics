"""Compile locale/strings.json -> locale/<lang>/LC_MESSAGES/django.{po,mo}.

Pure-Python: uses ``polib`` for both .po authoring and .mo binary compilation,
so this works on Windows without gettext being installed.

Source language is Uzbek (``LANGUAGE_CODE = "uz"``). The ``TRANSLATIONS`` map
below supplies Russian and English translations for the strings we want to
expose in the UI's language switcher. Strings not listed fall back to the
original Uzbek — nothing is blanked out, so flipping the switcher never
produces a broken-looking page.

Usage:
    python tools/i18n_extract.py      # refresh strings.json
    python tools/i18n_compile.py      # write .po + .mo files
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import polib

BASE = Path(__file__).resolve().parent.parent
LOCALE = BASE / "locale"


# ---------------------------------------------------------------------------
# Translation table — msgid (Uzbek) -> {"en": "...", "ru": "..."}
#
# Keep entries short and user-facing. Strings absent here fall through to the
# Uzbek source, so it's safe to leave seldom-seen text (legal pages, marketing
# blocks) untranslated — those render in Uzbek no matter which language the
# user picks, and that's clearly preferable to shipping half-English gibberish.
# ---------------------------------------------------------------------------
TRANSLATIONS: dict[str, dict[str, str]] = {
    # ---- Navigation / sidebar ----
    "Bosh sahifa":        {"en": "Home",               "ru": "Главная"},
    "Dashboard":          {"en": "Dashboard",          "ru": "Панель"},
    "Akkauntlarim":       {"en": "My accounts",        "ru": "Мои аккаунты"},
    "Analytics":          {"en": "Analytics",          "ru": "Аналитика"},
    "Sentiment":          {"en": "Sentiment",          "ru": "Настроения"},
    "AI Chat":            {"en": "AI Chat",            "ru": "AI Чат"},
    "Solishtirish":       {"en": "Compare",            "ru": "Сравнение"},
    "Top postlar":        {"en": "Top posts",          "ru": "Топ постов"},
    "Hisobotlar":         {"en": "Reports",            "ru": "Отчёты"},
    "Profil":             {"en": "Profile",            "ru": "Профиль"},
    "Sozlamalar":         {"en": "Settings",           "ru": "Настройки"},
    "Asosiy":             {"en": "Main",               "ru": "Основное"},
    "Chiqish":            {"en": "Sign out",           "ru": "Выйти"},
    "Kirish":             {"en": "Sign in",            "ru": "Войти"},
    "Kirgan sifatida":    {"en": "Signed in as",       "ru": "Вход выполнен как"},
    "Boshlash":           {"en": "Get started",        "ru": "Начать"},
    "Menyu":              {"en": "Menu",               "ru": "Меню"},
    "Mobil menyu":        {"en": "Mobile menu",        "ru": "Мобильное меню"},
    "Til":                {"en": "Language",           "ru": "Язык"},
    "Mavzuni almashtirish": {"en": "Toggle theme",     "ru": "Переключить тему"},
    "Qidiruv va komandalar": {"en": "Search and commands", "ru": "Поиск и команды"},
    "Qidiruv yoki komanda...": {"en": "Search or command...", "ru": "Поиск или команда..."},
    "Qidirish":           {"en": "Search",             "ru": "Поиск"},

    # ---- Landing / marketing headers ----
    "Xususiyatlar":       {"en": "Features",           "ru": "Возможности"},
    "Qanday ishlaydi":    {"en": "How it works",       "ru": "Как это работает"},
    "Raqamlar":           {"en": "Numbers",            "ru": "Цифры"},
    "Yangi":              {"en": "New",                "ru": "Новое"},
    "AI sentiment tahlili": {"en": "AI sentiment analysis", "ru": "AI-анализ настроений"},
    "3 tilli interfeys":  {"en": "3-language UI",      "ru": "3-язычный интерфейс"},
    "4 ta platforma":     {"en": "4 platforms",        "ru": "4 платформы"},
    "3 qadamda boshlang": {"en": "Start in 3 steps",   "ru": "Начните за 3 шага"},
    "tomonidan quvvatlanadi": {"en": "powered by",     "ru": "работает на"},
    "tillar":             {"en": "languages",          "ru": "языки"},
    "platforma":          {"en": "platform",           "ru": "платформа"},
    "postlar":            {"en": "posts",              "ru": "посты"},
    "obunachi":           {"en": "followers",          "ru": "подписчиков"},
    "ochish":             {"en": "open",               "ru": "открыть"},
    "pastga":             {"en": "down",               "ru": "вниз"},
    "ulangan":            {"en": "connected",          "ru": "подключено"},
    "tanlash":            {"en": "select",             "ru": "выбрать"},
    "va":                 {"en": "and",                "ru": "и"},
    "yoki":               {"en": "or",                 "ru": "или"},
    "kun":                {"en": "days",               "ru": "дней"},
    "oxirgi hafta":       {"en": "last week",          "ru": "последняя неделя"},
    "oy/oy":              {"en": "month/month",        "ru": "месяц/месяц"},
    "pozitiv kommentlar": {"en": "positive comments",  "ru": "позитивные комментарии"},
    "professional tushuning": {"en": "understand professionally", "ru": "профессиональное понимание"},

    # ---- Buttons / actions ----
    "Saqlash":            {"en": "Save",               "ru": "Сохранить"},
    "Bekor qilish":       {"en": "Cancel",             "ru": "Отмена"},
    "O'chirish":          {"en": "Delete",             "ru": "Удалить"},
    "Tahrirlash":         {"en": "Edit",               "ru": "Редактировать"},
    "Yopish":             {"en": "Close",              "ru": "Закрыть"},
    "Ochish":             {"en": "Open",               "ru": "Открыть"},
    "Keyingi":            {"en": "Next",               "ru": "Далее"},
    "Oldingi":            {"en": "Previous",           "ru": "Назад"},
    "Yuborish":           {"en": "Submit",             "ru": "Отправить"},
    "Tasdiqlash":         {"en": "Confirm",            "ru": "Подтвердить"},
    "Davom etish":        {"en": "Continue",           "ru": "Продолжить"},
    "Ro'yxatdan o'tish":  {"en": "Sign up",            "ru": "Регистрация"},

    # ---- Top posts page ----
    "Saralash":           {"en": "Sort by",            "ru": "Сортировать"},
    "Davr":               {"en": "Period",             "ru": "Период"},
    "Platforma":          {"en": "Platform",           "ru": "Платформа"},
    "Post turi":          {"en": "Post type",          "ru": "Тип поста"},
    "Hammasi":            {"en": "All",                "ru": "Все"},
    "Barcha davr":        {"en": "All time",           "ru": "За всё время"},
    "Oxirgi":             {"en": "Last",               "ru": "Последние"},
    "Post":               {"en": "Post",               "ru": "Пост"},
    "Like":               {"en": "Likes",              "ru": "Лайки"},
    "Ko'rildi":           {"en": "Views",              "ru": "Просмотры"},
    "Izoh":               {"en": "Comments",           "ru": "Комментарии"},
    "Sana":               {"en": "Date",               "ru": "Дата"},
    "Sahifa":             {"en": "Page",               "ru": "Страница"},
    "Eng ko'p like":      {"en": "Most likes",         "ru": "Больше всего лайков"},
    "Eng ko'p ko'rilgan": {"en": "Most viewed",        "ru": "Больше всего просмотров"},
    "Eng ko'p izoh":      {"en": "Most commented",     "ru": "Больше всего комментариев"},
    "Eng ko'p ulashilgan": {"en": "Most shared",       "ru": "Больше всего репостов"},
    "Eng yuqori engagement": {"en": "Highest engagement", "ru": "Высокий engagement"},
    "Eng yangilari":      {"en": "Most recent",        "ru": "Самые новые"},
    "Post topilmadi":     {"en": "No posts found",     "ru": "Посты не найдены"},
    "Akkaunt ulash":      {"en": "Connect account",    "ru": "Подключить аккаунт"},

    # ---- AI Chat ----
    "AI Chat hali sozlanmagan": {"en": "AI Chat is not configured yet", "ru": "AI Чат ещё не настроен"},
    "Administrator":      {"en": "Administrator",      "ru": "Администратор"},
    "saytidan olish mumkin.": {"en": "key can be obtained.", "ru": "можно получить ключ."},
    "Dashboard haqida savol bering": {"en": "Ask questions about your dashboard", "ru": "Задайте вопрос о панели"},

    # ---- Auth / account pages ----
    "Email":              {"en": "Email",              "ru": "Эл. почта"},
    "Parol":              {"en": "Password",           "ru": "Пароль"},
    "Ism":                {"en": "First name",         "ru": "Имя"},
    "Familiya":           {"en": "Last name",          "ru": "Фамилия"},
    "Foydalanuvchi nomi": {"en": "Username",           "ru": "Имя пользователя"},
    "Parolni tiklash":    {"en": "Reset password",     "ru": "Сбросить пароль"},
    "Parolni unutdingizmi?": {"en": "Forgot password?", "ru": "Забыли пароль?"},
    "Akkauntga kirish":   {"en": "Sign in to your account", "ru": "Войти в аккаунт"},
    "Yangi akkaunt yaratish": {"en": "Create a new account", "ru": "Создать новый аккаунт"},

    # ---- Empty states ----
    "Hali ma'lumot yo'q": {"en": "No data yet",        "ru": "Пока нет данных"},
    "Yuklanmoqda":        {"en": "Loading",            "ru": "Загрузка"},
    "Yuklanmoqda…":       {"en": "Loading…",           "ru": "Загрузка…"},

    # ---- Dashboard widgets ----
    "30 kunlik tendensiya": {"en": "30-day trend",     "ru": "Тренд за 30 дней"},
    "30 kunlik likes dinamikasi": {"en": "30-day likes dynamics", "ru": "Динамика лайков за 30 дней"},
    "30-kunlik likes dinamikasi": {"en": "30-day likes dynamics", "ru": "Динамика лайков за 30 дней"},

    # ---- Settings / account ----
    "Akkauntni o'chirish": {"en": "Delete account",    "ru": "Удалить аккаунт"},
    "Xavfsizlik":         {"en": "Security",           "ru": "Безопасность"},
    "Shaxsiy ma'lumotlar": {"en": "Personal information", "ru": "Личные данные"},
}


def _po_metadata(lang_code: str) -> dict[str, str]:
    return {
        "Project-Id-Version":        "social-analytics 1.0",
        "Report-Msgid-Bugs-To":      "",
        "POT-Creation-Date":         datetime.utcnow().strftime("%Y-%m-%d %H:%M+0000"),
        "PO-Revision-Date":          datetime.utcnow().strftime("%Y-%m-%d %H:%M+0000"),
        "Last-Translator":           "social-analytics i18n_compile.py",
        "Language-Team":             lang_code,
        "Language":                  lang_code,
        "MIME-Version":              "1.0",
        "Content-Type":              "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
        "Plural-Forms":              "nplurals=2; plural=(n != 1);",
    }


def _build_catalog(strings: dict[str, list[str]], lang_code: str) -> polib.POFile:
    po = polib.POFile()
    po.metadata = _po_metadata(lang_code)

    for msgid in sorted(strings, key=str.lower):
        translation = TRANSLATIONS.get(msgid, {}).get(lang_code, "")
        # Fallback: leave msgstr empty so Django falls back to msgid (Uzbek).
        # This keeps the UI consistent rather than blanking untranslated text.
        entry = polib.POEntry(
            msgid=msgid,
            msgstr=translation,
            occurrences=[(p, "") for p in strings[msgid][:10]],
        )
        po.append(entry)
    return po


def main() -> None:
    strings_path = LOCALE / "strings.json"
    if not strings_path.exists():
        raise SystemExit(
            "locale/strings.json not found — run `python tools/i18n_extract.py` first."
        )

    strings: dict[str, list[str]] = json.loads(strings_path.read_text(encoding="utf-8"))

    for lang in ("en", "ru"):
        lang_dir = LOCALE / lang / "LC_MESSAGES"
        lang_dir.mkdir(parents=True, exist_ok=True)

        po = _build_catalog(strings, lang)
        po_path = lang_dir / "django.po"
        mo_path = lang_dir / "django.mo"

        po.save(str(po_path))
        po.save_as_mofile(str(mo_path))

        translated = sum(1 for e in po if e.msgstr)
        total = len(po)
        print(
            f"{lang}: {translated}/{total} translated "
            f"({translated * 100 / total:.0f}%) -> {mo_path.relative_to(BASE)}"
        )


if __name__ == "__main__":
    main()
