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
    "Shaxsiy ma'lumot":   {"en": "Personal data",      "ru": "Личные данные"},
    "Profil ma'lumotlari": {"en": "Profile information", "ru": "Информация профиля"},
    "Profil sozlamalari": {"en": "Profile settings",   "ru": "Настройки профиля"},
    "Mening ma'lumotlarim": {"en": "My data",          "ru": "Мои данные"},
    "Sizning huquqlaringiz": {"en": "Your rights",     "ru": "Ваши права"},
    "Ma'lumot saqlash":   {"en": "Data retention",     "ru": "Хранение данных"},
    "Xavfli zona":        {"en": "Danger zone",        "ru": "Опасная зона"},
    "Xavfsiz OAuth":      {"en": "Secure OAuth",       "ru": "Безопасный OAuth"},
    "Autentifikatsiya":   {"en": "Authentication",     "ru": "Аутентификация"},
    "E2E shifrlangan":    {"en": "E2E encrypted",      "ru": "E2E шифрование"},
    "Interfeys tili":     {"en": "Interface language", "ru": "Язык интерфейса"},
    "Holati":             {"en": "Status",             "ru": "Статус"},
    "Mavzu":              {"en": "Theme",              "ru": "Тема"},
    "Qorong'u":           {"en": "Dark",               "ru": "Тёмная"},
    "Yorug'":             {"en": "Light",              "ru": "Светлая"},
    "Avtomatik":          {"en": "Automatic",          "ru": "Автоматически"},

    # ---- Account / auth flow ----
    "Akkaunt":            {"en": "Account",            "ru": "Аккаунт"},
    "Akkauntlar":         {"en": "Accounts",           "ru": "Аккаунты"},
    "Akkaunt yaratish":   {"en": "Create account",     "ru": "Создать аккаунт"},
    "Akkauntingiz bormi?": {"en": "Have an account?",  "ru": "Уже есть аккаунт?"},
    "Akkauntingiz yo'qmi?": {"en": "Don't have an account?", "ru": "Нет аккаунта?"},
    "Akkauntga kirish":   {"en": "Sign in to your account", "ru": "Войти в аккаунт"},
    "Yangi akkaunt yaratish": {"en": "Create a new account", "ru": "Создать новый аккаунт"},
    "Xush kelibsiz":      {"en": "Welcome",            "ru": "Добро пожаловать"},
    "Ro'yxatdan o'ting":  {"en": "Sign up",            "ru": "Зарегистрируйтесь"},
    "Ro’yxatdan o’tish":  {"en": "Sign up",            "ru": "Регистрация"},
    "Bepul akkaunt yaratish": {"en": "Create free account", "ru": "Создать бесплатный аккаунт"},
    "Bepul boshlash":     {"en": "Start for free",     "ru": "Начать бесплатно"},
    "Google orqali davom etish": {"en": "Continue with Google", "ru": "Продолжить через Google"},
    "Chiqishni tasdiqlaysizmi?": {"en": "Confirm sign out?", "ru": "Подтвердить выход?"},
    "Ha, chiqish":        {"en": "Yes, sign out",      "ru": "Да, выйти"},
    "Kiryapti...":        {"en": "Signing in...",      "ru": "Вход..."},
    "Kirish sahifasiga qaytish": {"en": "Back to sign-in", "ru": "Вернуться ко входу"},
    "Meni eslab qol":     {"en": "Remember me",        "ru": "Запомнить меня"},

    # ---- Password / validation ----
    "Yangi parol":        {"en": "New password",       "ru": "Новый пароль"},
    "Yangi parol o'rnatish": {"en": "Set new password", "ru": "Установить новый пароль"},
    "Parol o'zgartirildi": {"en": "Password changed",  "ru": "Пароль изменён"},
    "Parolni o'zgartirish": {"en": "Change password",  "ru": "Изменить пароль"},
    "Parolni qayta kiriting": {"en": "Re-enter password", "ru": "Введите пароль ещё раз"},
    "Parolni takrorlang": {"en": "Repeat password",    "ru": "Повторите пароль"},
    "Parolni ko’rsatish": {"en": "Show password",      "ru": "Показать пароль"},
    "Parolni yashirish":  {"en": "Hide password",      "ru": "Скрыть пароль"},
    "Parolingiz":         {"en": "Your password",      "ru": "Ваш пароль"},
    "Parollar mos":       {"en": "Passwords match",    "ru": "Пароли совпадают"},
    "Parollar mos emas":  {"en": "Passwords do not match", "ru": "Пароли не совпадают"},
    "Kamida 8 belgi":     {"en": "At least 8 characters", "ru": "Минимум 8 символов"},
    "Kamida 8 ta belgi":  {"en": "At least 8 characters", "ru": "Минимум 8 символов"},
    "Katta harf (A-Z)":   {"en": "Uppercase (A-Z)",    "ru": "Заглавная буква (A-Z)"},
    "Kichik harf (a-z)":  {"en": "Lowercase (a-z)",    "ru": "Строчная буква (a-z)"},
    "Raqam (0-9)":        {"en": "Digit (0-9)",        "ru": "Цифра (0-9)"},
    "Maxsus belgi (!@#$ ...)": {"en": "Special character (!@#$ ...)", "ru": "Спецсимвол (!@#$ ...)"},
    "Juda zaif":          {"en": "Very weak",          "ru": "Очень слабый"},
    "Zaif":               {"en": "Weak",               "ru": "Слабый"},
    "Yetarli":            {"en": "Fair",               "ru": "Достаточный"},
    "Kuchli":             {"en": "Strong",             "ru": "Сильный"},
    "Juda kuchli":        {"en": "Very strong",        "ru": "Очень сильный"},

    # ---- Email verification ----
    "Email manzilni tasdiqlash": {"en": "Confirm email address", "ru": "Подтвердить email"},
    "Email tasdiqlash":   {"en": "Email confirmation", "ru": "Подтверждение email"},
    "Emailni tasdiqlash": {"en": "Email confirmation", "ru": "Подтверждение email"},
    "Emailni tasdiqlang": {"en": "Confirm your email", "ru": "Подтвердите email"},
    "Email yuborildi":    {"en": "Email sent",         "ru": "Email отправлен"},
    "Emailingizni tekshiring": {"en": "Check your email", "ru": "Проверьте вашу почту"},
    "Xat kelmayaptimi?":  {"en": "Didn't get the email?", "ru": "Письмо не пришло?"},
    "Spam papkasini tekshiring": {"en": "Check your spam folder", "ru": "Проверьте папку спам"},
    "Yangi tasdiqlash so'rash": {"en": "Request new confirmation", "ru": "Запросить подтверждение заново"},
    "Yangi havola so'rash": {"en": "Request new link", "ru": "Запросить новую ссылку"},
    "Havola ishlamaydi":  {"en": "Link not working",   "ru": "Ссылка не работает"},

    # ---- Content / analytics widgets ----
    "Postlar":            {"en": "Posts",              "ru": "Посты"},
    "Postlar (30 kun)":   {"en": "Posts (30 days)",    "ru": "Посты (30 дней)"},
    "Kommentlar":         {"en": "Comments",           "ru": "Комментарии"},
    "kommentlar":         {"en": "comments",           "ru": "комментариев"},
    "Layklar":            {"en": "Likes",              "ru": "Лайки"},
    "Likes":              {"en": "Likes",              "ru": "Лайки"},
    "Ko'rishlar":         {"en": "Views",              "ru": "Просмотры"},
    "Obunachilar":        {"en": "Followers",          "ru": "Подписчики"},
    "Jami":               {"en": "Total",              "ru": "Всего"},
    "Jami likes":         {"en": "Total likes",        "ru": "Всего лайков"},
    "Engagement":         {"en": "Engagement",         "ru": "Engagement"},
    "Top post":           {"en": "Top post",           "ru": "Топ пост"},
    "Top post tahlili":   {"en": "Top post analysis",  "ru": "Анализ топ поста"},
    "Asl post":           {"en": "Original post",      "ru": "Оригинальный пост"},
    "Tahlil qilingan postlar": {"en": "Analyzed posts", "ru": "Проанализированные посты"},
    "Tahlilni ko'ring":   {"en": "View analysis",      "ru": "Посмотреть анализ"},
    "Platforma bo'yicha": {"en": "By platform",        "ru": "По платформе"},
    "Faol akkauntlar":    {"en": "Active accounts",    "ru": "Активные аккаунты"},
    "Ulangan akkauntlar": {"en": "Connected accounts", "ru": "Подключённые аккаунты"},
    "Akkauntlarni solishtirish": {"en": "Compare accounts", "ru": "Сравнить аккаунты"},
    "Akkauntlarni ulang": {"en": "Connect your accounts", "ru": "Подключите аккаунты"},
    "akkauntini ulash":   {"en": "connect account",    "ru": "подключить аккаунт"},
    "Yana bitta ulash":   {"en": "Connect one more",   "ru": "Подключить ещё"},
    "Boshqa akkauntni tanlash": {"en": "Choose another account", "ru": "Выбрать другой аккаунт"},
    "Ulangan":            {"en": "Connected",          "ru": "Подключено"},
    "Ulanmagan":          {"en": "Not connected",      "ru": "Не подключено"},
    "Faollik dinamikasi": {"en": "Activity dynamics",  "ru": "Динамика активности"},
    "Faollik ulushi":     {"en": "Activity share",     "ru": "Доля активности"},
    "Umumiy taqsimot":    {"en": "Overall distribution", "ru": "Общее распределение"},

    # ---- Sentiment ----
    "Pozitiv":            {"en": "Positive",           "ru": "Позитивный"},
    "Neytral":            {"en": "Neutral",            "ru": "Нейтральный"},
    "Negativ":            {"en": "Negative",           "ru": "Негативный"},
    "Pozitiv so'zlar":    {"en": "Positive words",     "ru": "Позитивные слова"},
    "Negativ so'zlar":    {"en": "Negative words",     "ru": "Негативные слова"},
    "Eng pozitiv kommentlar": {"en": "Most positive comments", "ru": "Самые позитивные комментарии"},
    "Eng negativ kommentlar": {"en": "Most negative comments", "ru": "Самые негативные комментарии"},
    "Eng pozitiv kontent": {"en": "Most positive content", "ru": "Самый позитивный контент"},
    "Sentiment natijalari": {"en": "Sentiment results", "ru": "Результаты настроений"},
    "Sentiment tahlili":  {"en": "Sentiment analysis", "ru": "Анализ настроений"},
    "Sentiment +3%":      {"en": "Sentiment +3%",      "ru": "Sentiment +3%"},
    "Til bo'yicha sentiment": {"en": "Sentiment by language", "ru": "Настроения по языкам"},

    # ---- Date / period ----
    "Bugun":              {"en": "Today",              "ru": "Сегодня"},
    "Davr:":              {"en": "Period:",            "ru": "Период:"},
    "Oxirgi 7 kun":       {"en": "Last 7 days",        "ru": "Последние 7 дней"},
    "Oxirgi 14 kun":      {"en": "Last 14 days",       "ru": "Последние 14 дней"},
    "Oxirgi yangilanish:": {"en": "Last update:",      "ru": "Последнее обновление:"},
    "o'sish":             {"en": "growth",             "ru": "рост"},

    # ---- Export / reports ----
    "Eksport":            {"en": "Export",             "ru": "Экспорт"},
    "PDF eksport":        {"en": "PDF export",         "ru": "Экспорт PDF"},
    "PDF yuklash":        {"en": "Download PDF",       "ru": "Скачать PDF"},
    "Excel eksport (.xlsx)": {"en": "Excel export (.xlsx)", "ru": "Экспорт Excel (.xlsx)"},
    "Excel yuklash":      {"en": "Download Excel",     "ru": "Скачать Excel"},
    "PDF, Excel, CSV":    {"en": "PDF, Excel, CSV",    "ru": "PDF, Excel, CSV"},
    "Hisobot yuklash":    {"en": "Download report",    "ru": "Скачать отчёт"},

    # ---- Sharing ----
    "Ulash":              {"en": "Share",              "ru": "Поделиться"},
    "Ulashish":           {"en": "Share",              "ru": "Поделиться"},
    "Ulash va ma'lumot yuklash": {"en": "Share and download data", "ru": "Поделиться и скачать данные"},
    "Public dashboard":   {"en": "Public dashboard",   "ru": "Публичная панель"},
    "Public link":        {"en": "Public link",        "ru": "Публичная ссылка"},
    "Public snapshot":    {"en": "Public snapshot",    "ru": "Публичный снимок"},

    # ---- Demo / mode ----
    "Demo":               {"en": "Demo",               "ru": "Демо"},
    "Demo rejim":         {"en": "Demo mode",          "ru": "Демо режим"},
    "Demo ko'rish":       {"en": "View demo",          "ru": "Посмотреть демо"},
    "demo ma'lumot":      {"en": "demo data",          "ru": "демо данные"},
    "Demo post soni":     {"en": "Demo post count",    "ru": "Количество демо постов"},
    "Haqiqiy":            {"en": "Real",               "ru": "Реальный"},

    # ---- Empty / error states ----
    "Hali ma'lumot yo'q.": {"en": "No data yet.",      "ru": "Пока нет данных."},
    "Hali postlar yo'q.": {"en": "No posts yet.",      "ru": "Пока нет постов."},
    "Hali namunalar yo'q.": {"en": "No samples yet.",  "ru": "Пока нет образцов."},
    "Hali tadbirlar yo'q.": {"en": "No events yet.",   "ru": "Пока нет событий."},
    "Hech narsa topilmadi": {"en": "Nothing found",    "ru": "Ничего не найдено"},
    "Sahifa topilmadi":   {"en": "Page not found",     "ru": "Страница не найдена"},
    "Server xatosi":      {"en": "Server error",       "ru": "Ошибка сервера"},
    "Bosh sahifaga qaytish": {"en": "Back to home",    "ru": "Вернуться на главную"},
    "Qayta urinish":      {"en": "Try again",          "ru": "Попробовать снова"},
    "Orqaga":             {"en": "Back",               "ru": "Назад"},
    "Yaratilmoqda...":    {"en": "Creating...",        "ru": "Создание..."},
    "Bir necha daqiqa kuting": {"en": "Wait a few minutes", "ru": "Подождите несколько минут"},
    "Qo'llash":           {"en": "Apply",              "ru": "Применить"},

    # ---- Search / commands ----
    "Nimani qidiryapsiz?": {"en": "What are you looking for?", "ru": "Что вы ищете?"},
    "Komandalar paneli":  {"en": "Command palette",    "ru": "Палитра команд"},
    "Savolingiz...":      {"en": "Your question...",   "ru": "Ваш вопрос..."},

    # ---- Landing / marketing short ----
    "Imkoniyatlar":       {"en": "Features",           "ru": "Возможности"},
    "Mahsulot":           {"en": "Product",            "ru": "Продукт"},
    "Resurslar":          {"en": "Resources",          "ru": "Ресурсы"},
    "Navigatsiya":        {"en": "Navigation",         "ru": "Навигация"},
    "Raqamlarda":         {"en": "By the numbers",     "ru": "В цифрах"},
    "Loyiha holati":      {"en": "Project status",     "ru": "Статус проекта"},
    "Tizim ishlamoqda":   {"en": "System operational", "ru": "Система работает"},
    "Diplom loyihasi":    {"en": "Diploma project",    "ru": "Дипломный проект"},
    "Made with":          {"en": "Made with",          "ru": "Сделано с"},
    "in Tashkent":        {"en": "in Tashkent",        "ru": "в Ташкенте"},
    "Foydalanuvchilarimiz": {"en": "Our users",        "ru": "Наши пользователи"},
    "Bloggerlar":         {"en": "Bloggers",           "ru": "Блогеры"},
    "Marketing agentliklari": {"en": "Marketing agencies", "ru": "Маркетинговые агентства"},
    "Talabalar":          {"en": "Students",           "ru": "Студенты"},
    "Kim uchun":          {"en": "Who it's for",       "ru": "Для кого"},
    "Kodi ochiqmi?":      {"en": "Is it open source?", "ru": "Открытый ли исходный код?"},
    "Bu platforma bepulmi?": {"en": "Is this platform free?", "ru": "Эта платформа бесплатная?"},
    "Engagement pasayishi?": {"en": "Engagement drop?", "ru": "Падение engagement?"},
    "Eng yaxshi platforma?": {"en": "Best platform?",  "ru": "Лучшая платформа?"},
    "Barchasi":           {"en": "All",                "ru": "Все"},
    "Barchasi bir dashboardda.": {"en": "Everything on one dashboard.", "ru": "Всё на одной панели."},
    "Ma'lumotdan qarorga": {"en": "From data to decisions", "ru": "От данных к решениям"},
    "Ma'lumotingizni oldin": {"en": "Your data first", "ru": "Сначала ваши данные"},
    "Ijtimoiy ovozingizni": {"en": "Your social voice", "ru": "Ваш социальный голос"},
    "Interaktiv grafiklar": {"en": "Interactive charts", "ru": "Интерактивные графики"},
    "Real-time analitika": {"en": "Real-time analytics", "ru": "Аналитика в реальном времени"},
    "Real-time statistika": {"en": "Real-time statistics", "ru": "Статистика в реальном времени"},
    "Ko'p tilli interfeys": {"en": "Multi-language UI", "ru": "Многоязычный интерфейс"},
    "Ishonchlilik":       {"en": "Reliability",        "ru": "Надёжность"},
    "Bugun boshlang":     {"en": "Start today",        "ru": "Начните сегодня"},
    "Xususiyatlarni ko'rish": {"en": "View features",  "ru": "Смотреть возможности"},
    "Tadbirlar":          {"en": "Events",             "ru": "События"},
    "Masalan:":           {"en": "For example:",       "ru": "Например:"},
    "Taklif:":            {"en": "Suggestion:",        "ru": "Рекомендация:"},
    "Eslatma":            {"en": "Note",               "ru": "Примечание"},
    "Eslatma:":           {"en": "Note:",              "ru": "Примечание:"},
    "Men":                {"en": "I",                  "ru": "Я"},
    "IG · TG · YT · X":   {"en": "IG · TG · YT · X",   "ru": "IG · TG · YT · X"},
    "GitHub Issues →":    {"en": "GitHub Issues →",    "ru": "GitHub Issues →"},
    "Savollar uchun:":    {"en": "For questions:",     "ru": "По вопросам:"},
    "To'liq tarjima qilingan.": {"en": "Fully translated.", "ru": "Полностью переведено."},

    # ---- Legal pages — short section headings ----
    "Foydalanish shartlari": {"en": "Terms of use",    "ru": "Условия использования"},
    "Maxfiylik siyosati": {"en": "Privacy policy",     "ru": "Политика конфиденциальности"},
    "Huquqiy ma'lumot":   {"en": "Legal information",  "ru": "Юридическая информация"},
    "Cookie'lar":         {"en": "Cookies",            "ru": "Cookie"},
    "2. Xizmatning tavsifi": {"en": "2. Service description", "ru": "2. Описание услуги"},
    "3. Akkaunt va xavfsizlik": {"en": "3. Account and security", "ru": "3. Аккаунт и безопасность"},
    "5. Cheklovlar":      {"en": "5. Limitations",     "ru": "5. Ограничения"},
    "7. Aloqa":           {"en": "7. Contact",         "ru": "7. Контакты"},
    "8. Mualliflik huquqi": {"en": "8. Copyright",     "ru": "8. Авторское право"},
    "9. Javobgarlikni cheklash": {"en": "9. Limitation of liability", "ru": "9. Ограничение ответственности"},
    "10. Nizolarni hal etish": {"en": "10. Dispute resolution", "ru": "10. Разрешение споров"},

    # ---- Misc ----
    "Platform-side account id": {"en": "Platform-side account id", "ru": "ID аккаунта на платформе"},
    "Public @username or channel id": {"en": "Public @username or channel id", "ru": "Публичный @username или ID канала"},
    "True for accounts seeded by the demo generator.": {"en": "True for accounts seeded by the demo generator.", "ru": "True для аккаунтов, созданных демо-генератором."},
    "(likes + comments + shares) / views": {"en": "(likes + comments + shares) / views", "ru": "(лайки + комментарии + репосты) / просмотры"},

    # ---- Landing / marketing — medium phrases ----
    "Ijtimoiy tarmoq analitikasi": {"en": "Social media analytics", "ru": "Аналитика соцсетей"},
    "Ijtimoiy tarmoqlardagi ovozingizni tushuning.": {"en": "Understand your voice on social media.", "ru": "Понимайте свой голос в соцсетях."},
    "Ijtimoiy tarmog'ingizni bir daqiqada kuzatishni boshlang.": {"en": "Start monitoring your social accounts in a minute.", "ru": "Начните отслеживать соцсети за минуту."},
    "Ijtimoiy tarmoq akkauntlaringizni ulab, real ma'lumotni tahlil qiling.": {"en": "Connect your social accounts and analyze real data.", "ru": "Подключите соцсети и анализируйте реальные данные."},
    "Auditoriyani tushuning, qaysi kontent ishlayotganini biling.": {"en": "Understand your audience, learn what content works.", "ru": "Поймите аудиторию и узнайте, какой контент работает."},
    "Biz allaqachon ishlayapmiz": {"en": "We're already running", "ru": "Мы уже работаем"},
    "Hisobotlarni bir bosishda eksport qiling.": {"en": "Export reports in one click.", "ru": "Экспортируйте отчёты в один клик."},
    "Postlaringizning qamrovi va faolligi jonli grafikada.": {"en": "Post reach and engagement in a live chart.", "ru": "Охват и активность постов в живом графике."},
    "Filtrlab, kesib, eksport qilib — ma'lumotni o'z qo'lingizda.": {"en": "Filter, slice, export — data at your fingertips.", "ru": "Фильтруйте, срезайте, экспортируйте — данные у вас в руках."},
    "O'zbek, rus va ingliz tillarida kommentlarni avtomatik baholash.": {"en": "Automatic comment scoring in Uzbek, Russian, and English.", "ru": "Автоматическая оценка комментариев на узбекском, русском и английском."},
    "O'zbek, rus va ingliz tillarida — doim qulay.": {"en": "Uzbek, Russian, and English — always convenient.", "ru": "Узбекский, русский и английский — всегда удобно."},
    "Yorug' yoki qorong'u — tizim sozlamalari bo'yicha avtomatik.": {"en": "Light or dark — automatic from system preferences.", "ru": "Светлая или тёмная — автоматически по системным настройкам."},
    "Yig'ishdan hisobotgacha — barchasi bir joyda, barchasi avtomatlashtirilgan.": {"en": "From collection to report — everything in one place, fully automated.", "ru": "От сбора до отчёта — всё в одном месте, полностью автоматизировано."},
    "Talabalar, tadqiqotchilar va marketologlar uchun": {"en": "For students, researchers, and marketers", "ru": "Для студентов, исследователей и маркетологов"},
    "Diplom va kurs ishlarida real ma'lumot bilan tadqiqot.": {"en": "Research with real data for diploma and course work.", "ru": "Исследования с реальными данными для дипломов и курсовых."},
    "Mijozlarga aniq hisobotlar, kampaniyalar samaradorligi.": {"en": "Clear client reports, campaign performance.", "ru": "Чёткие отчёты для клиентов, эффективность кампаний."},
    "Instagram, Telegram, YouTube yoki X — xavfsiz OAuth orqali.": {"en": "Instagram, Telegram, YouTube, or X — via secure OAuth.", "ru": "Instagram, Telegram, YouTube или X — через безопасный OAuth."},
    "Dashboard va hisobotlar yaratish uchun.": {"en": "To build dashboards and reports.", "ru": "Для создания панелей и отчётов."},
    "Bir necha daqiqada ro'yxatdan o'ting — dashboardingiz tayyor.": {"en": "Sign up in minutes — your dashboard is ready.", "ru": "Зарегистрируйтесь за несколько минут — панель готова."},
    "Kredit karta kerak emas — hoziroq boshlang.": {"en": "No credit card needed — start right now.", "ru": "Карта не нужна — начните прямо сейчас."},
    "Kredit karta kerak emas. Hoziroq boshlang.": {"en": "No credit card needed. Start right now.", "ru": "Карта не нужна. Начните прямо сейчас."},
    "Google va platforma OAuth. Parollar saqlanmaydi.": {"en": "Google and platform OAuth. No passwords stored.", "ru": "Google и платформенный OAuth. Пароли не хранятся."},
    "Birinchi akkauntingizni ulang": {"en": "Connect your first account", "ru": "Подключите первый аккаунт"},
    "Dashboard, sentiment va top postlar. Hisobotni yuklab oling.": {"en": "Dashboard, sentiment, and top posts. Download the report.", "ru": "Панель, настроения и топ посты. Скачайте отчёт."},
    "Oxirgi 30 kunlik dinamika va platforma bo'yicha chuqur tahlil.": {"en": "Last 30-day dynamics and deep per-platform analysis.", "ru": "Динамика за 30 дней и глубокий анализ по платформам."},
    "2–3 ta akkaunt tanlang va KPI'lar bilan 30-kunlik trendni yonma-yon ko'ring.": {"en": "Pick 2–3 accounts and see KPIs + 30-day trend side by side.", "ru": "Выберите 2–3 аккаунта и сравните KPI и 30-дневный тренд рядом."},
    "2 dan 3 tagacha akkaunt tanlang:": {"en": "Pick 2 to 3 accounts:", "ru": "Выберите от 2 до 3 аккаунтов:"},
    "Solishtirish uchun kamida 2 ta akkaunt kerak.": {"en": "At least 2 accounts required for comparison.", "ru": "Для сравнения нужно не менее 2 аккаунтов."},
    "Har akkaunt alohida chiziq bilan": {"en": "Each account as a separate line", "ru": "Каждый аккаунт отдельной линией"},
    "Kunlik yig'ilgan likes soni": {"en": "Daily like totals", "ru": "Суммы лайков по дням"},

    # ---- FAQ headings (medium) ----
    "Tez-tez so'raladigan savollar": {"en": "Frequently asked questions", "ru": "Часто задаваемые вопросы"},
    "Qaysi platformalar qo'llab-quvvatlanadi?": {"en": "Which platforms are supported?", "ru": "Какие платформы поддерживаются?"},
    "Qo'llab-quvvatlanadigan platformalar": {"en": "Supported platforms", "ru": "Поддерживаемые платформы"},
    "Haqiqiy Instagram/YouTube OAuth ishlayaptimi?": {"en": "Does real Instagram/YouTube OAuth work?", "ru": "Работает ли настоящий Instagram/YouTube OAuth?"},
    "Sentiment tahlili qanday ishlaydi?": {"en": "How does sentiment analysis work?", "ru": "Как работает анализ настроений?"},
    "Qanday qilib sentiment aniqligini baholaysiz?": {"en": "How do you measure sentiment accuracy?", "ru": "Как вы оцениваете точность настроений?"},
    "Ma'lumotlar qayerda saqlanadi?": {"en": "Where is data stored?", "ru": "Где хранятся данные?"},
    "PDF hisobot ichida nima bor?": {"en": "What's in the PDF report?", "ru": "Что содержится в PDF отчёте?"},
    "Real rejim — Telegram MTProto": {"en": "Real mode — Telegram MTProto", "ru": "Реальный режим — Telegram MTProto"},
    "Postlar · layklar · ko'rishlar": {"en": "Posts · likes · views", "ru": "Посты · лайки · просмотры"},
    "Pozitiv · neytral · negativ": {"en": "Positive · neutral · negative", "ru": "Позитивные · нейтральные · негативные"},
    "XLM-RoBERTa modeli — o'zbek, rus va ingliz tillarida.": {"en": "XLM-RoBERTa model — in Uzbek, Russian, and English.", "ru": "Модель XLM-RoBERTa — на узбекском, русском и английском."},
    "Eng yaxshi postlar (top 20)": {"en": "Top posts (top 20)", "ru": "Лучшие посты (топ 20)"},
    "Tortib olinadigan post soni": {"en": "Number of posts to fetch", "ru": "Количество постов для загрузки"},
    "5 sahifa · brend cover · to'liq tahlil": {"en": "5 pages · branded cover · full analysis", "ru": "5 страниц · брендированная обложка · полный анализ"},
    "5 ta sheet · chart'lar · table style": {"en": "5 sheets · charts · table style", "ru": "5 листов · графики · табличный стиль"},
    "Savollar — GitHub issue orqali yuborish.": {"en": "Questions — submit via GitHub issue.", "ru": "Вопросы — через GitHub issues."},

    # ---- Sentiment / analytics medium ----
    "Pozitiv komment yetarli emas.": {"en": "Not enough positive comments.", "ru": "Недостаточно позитивных комментариев."},
    "Negativ komment yetarli emas.": {"en": "Not enough negative comments.", "ru": "Недостаточно негативных комментариев."},
    "Hali sentiment natijalari yo'q.": {"en": "No sentiment results yet.", "ru": "Пока нет результатов настроений."},
    "{{ n }} ta komment tahlil qilindi · model: {{ m }}": {"en": "{{ n }} comments analyzed · model: {{ m }}", "ru": "Проанализировано {{ n }} комментариев · модель: {{ m }}"},

    # ---- Settings / account — medium ----
    "Akkauntingiz, til va xavfsizlik sozlamalari.": {"en": "Account, language, and security settings.", "ru": "Настройки аккаунта, языка и безопасности."},
    "Ism, familiya va email manzili.": {"en": "First name, last name, and email address.", "ru": "Имя, фамилия и email."},
    "Email manzilingiz va parolingiz (shifrlangan hash).": {"en": "Your email and password (encrypted hash).", "ru": "Ваш email и пароль (зашифрованный хеш)."},
    "Sizning akkauntingizdagi postlar va kommentlar tahlil uchun.": {"en": "Posts and comments from your account, for analysis.", "ru": "Посты и комментарии вашего аккаунта — для анализа."},
    "OAuth orqali ulanganda platformalarning token'lari shifrlangan holda saqlanadi.": {"en": "When connected via OAuth, platform tokens are stored encrypted.", "ru": "При подключении через OAuth токены платформ хранятся зашифрованно."},
    "Xizmat sifati va xatolarni aniqlash uchun (anonim).": {"en": "For service quality and error tracking (anonymous).", "ru": "Для качества сервиса и отслеживания ошибок (анонимно)."},
    "Sahifadagi yuqori paneldan tilni istagan vaqtda o'zgartirishingiz mumkin.": {"en": "You can change the language any time from the top bar.", "ru": "Язык можно изменить в любое время через верхнюю панель."},
    "Xavfsizlik uchun parolni muntazam yangilab turing.": {"en": "Update your password regularly for security.", "ru": "Регулярно обновляйте пароль для безопасности."},
    "Parol maxfiyligi uchun siz javobgarsiz.": {"en": "You are responsible for keeping your password secret.", "ru": "Вы отвечаете за конфиденциальность пароля."},

    # ---- Sign out / deletion ----
    "Akkauntingizdan chiqmoqchimisiz?": {"en": "Do you want to sign out?", "ru": "Хотите выйти из аккаунта?"},
    "Akkauntingizga kirib, tahlilni davom ettiring.": {"en": "Sign in and continue your analysis.", "ru": "Войдите и продолжите анализ."},
    "Akkauntimni butunlay o'chirish": {"en": "Permanently delete my account", "ru": "Полностью удалить мой аккаунт"},
    "Ushbu akkauntni o’chirishni xohlaysizmi?": {"en": "Do you want to delete this account?", "ru": "Вы хотите удалить этот аккаунт?"},
    "Bu amalni ortga qaytarib bo'lmaydi": {"en": "This action cannot be undone", "ru": "Это действие нельзя отменить"},
    "Bu yerdagi amallar orqaga qaytarilmaydi.": {"en": "Actions here cannot be reverted.", "ru": "Действия здесь необратимы."},
    "Akkauntingizni o'chirsangiz quyidagilar doimo yo'qoladi:": {"en": "If you delete your account the following are lost permanently:", "ru": "При удалении аккаунта безвозвратно будут утеряны:"},
    "Akkauntni o'chirish (barcha ma'lumot yo'q qilinadi).": {"en": "Delete account (all data is destroyed).", "ru": "Удалить аккаунт (все данные удаляются)."},
    "Davom etish uchun <strong>{{ email }}</strong> email manzilini aniq kiriting:": {"en": "To continue, enter exactly <strong>{{ email }}</strong>:", "ru": "Чтобы продолжить, точно введите <strong>{{ email }}</strong>:"},
    "Barcha ulangan akkauntlar (Instagram, Telegram, YouTube, X)": {"en": "All connected accounts (Instagram, Telegram, YouTube, X)", "ru": "Все подключённые аккаунты (Instagram, Telegram, YouTube, X)"},
    "Barcha postlar va kommentlar": {"en": "All posts and comments", "ru": "Все посты и комментарии"},
    "Barcha sentiment tahlili natijalari": {"en": "All sentiment analysis results", "ru": "Все результаты анализа настроений"},
    "Yaratilgan hisobotlar tarixi": {"en": "Generated reports history", "ru": "История созданных отчётов"},
    "— keyin o'chirish xavfsiz bo'ladi.": {"en": "— then deletion is safe.", "ru": "— после этого удаление безопасно."},
    "Ma'lumotimni yuklab olish (JSON)": {"en": "Download my data (JSON)", "ru": "Скачать мои данные (JSON)"},
    "JSON sifatida yuklab oling": {"en": "Download as JSON", "ru": "Скачать как JSON"},
    "Ma'lumotingizni istalgan vaqtda ko'chirib olish (Settings → Export my data).": {"en": "Export your data any time (Settings → Export my data).", "ru": "Экспортируйте данные в любое время (Настройки → Экспорт)."},
    "Ma'lumotdan qanday foydalanamiz": {"en": "How we use your data", "ru": "Как мы используем данные"},
    "Qanday ma'lumot to'playmiz": {"en": "What data we collect", "ru": "Какие данные мы собираем"},

    # ---- Email verification medium ----
    "Email manzilingizni tasdiqlang": {"en": "Confirm your email address", "ru": "Подтвердите ваш email"},
    "Email manzilingizni kiriting — parolni tiklash havolasini yuboramiz.": {"en": "Enter your email — we'll send a password reset link.", "ru": "Введите email — мы отправим ссылку для сброса пароля."},
    "Email manzilingizning to'g'riligiga ishonch hosil qiling": {"en": "Make sure your email address is correct", "ru": "Убедитесь, что email верный"},
    "Email manzilni to'g'ri kiritganingizga ishonch hosil qiling": {"en": "Make sure you entered the email correctly", "ru": "Убедитесь, что вы ввели email правильно"},
    "Email va parol yoki Google orqali — bir daqiqada.": {"en": "Email + password or Google — in a minute.", "ru": "Email + пароль или Google — за минуту."},
    "Sizga tasdiqlash xati yubordik. Iltimos, emailingizdagi havolaga o'ting.": {"en": "We sent you a confirmation email. Please follow the link inside.", "ru": "Мы отправили письмо с подтверждением. Перейдите по ссылке в письме."},
    "Agar tugma ishlamasa, quyidagi havolani brauzeringizga nusxalang:": {"en": "If the button doesn't work, copy the link below into your browser:", "ru": "Если кнопка не работает, скопируйте ссылку в браузер:"},
    "Bu xat avtomatik yuborildi. Javob bermang.": {"en": "This email was sent automatically. Please do not reply.", "ru": "Это автоматическое письмо. Не отвечайте на него."},
    "Bu email manzil boshqa akkauntda tasdiqlangan.": {"en": "This email is already confirmed on another account.", "ru": "Этот email уже подтверждён в другом аккаунте."},
    "Bu havola yaroqsiz yoki muddati o'tgan.": {"en": "This link is invalid or has expired.", "ru": "Ссылка недействительна или устарела."},
    "Ushbu xatni siz so'ramagan bo'lsangiz, e'tiborsiz qoldiring.": {"en": "If you didn't request this, please ignore it.", "ru": "Если вы этого не запрашивали, просто проигнорируйте письмо."},
    "Spam yoki Promotions papkasini tekshiring": {"en": "Check your Spam or Promotions folder", "ru": "Проверьте папку Спам или Промоакции"},
    "Bir necha daqiqa kuting va yangilang": {"en": "Wait a few minutes and refresh", "ru": "Подождите несколько минут и обновите"},
    "Siz ro'yxatdan o'tganda haqiqiy email manzilingizni kiritishingiz kerak.": {"en": "You must enter a real email address when signing up.", "ru": "При регистрации нужно указать реальный email."},
    "Salom, <strong>{{ user_display }}</strong>!": {"en": "Hello, <strong>{{ user_display }}</strong>!", "ru": "Здравствуйте, <strong>{{ user_display }}</strong>!"},
    "Salom, <strong>{{ username }}</strong>!": {"en": "Hello, <strong>{{ username }}</strong>!", "ru": "Здравствуйте, <strong>{{ username }}</strong>!"},
    "bilan tanishdim va roziman.": {"en": "I have read and agree.", "ru": "Я ознакомлен(а) и согласен(на)."},

    # ---- Password reset ----
    "Parol muvaffaqiyatli o'zgartirildi": {"en": "Password successfully changed", "ru": "Пароль успешно изменён"},
    "Parolni tiklash havolasi yaroqsiz, muddati o'tgan yoki allaqachon ishlatilgan.": {"en": "Password reset link is invalid, expired, or already used.", "ru": "Ссылка для сброса пароля недействительна, устарела или уже использована."},
    "Parolni tiklash so'rovingiz": {"en": "Your password reset request", "ru": "Ваш запрос на сброс пароля"},
    "Parolni tiklash xati yuborish": {"en": "Send password reset email", "ru": "Отправить письмо для сброса"},
    "Yangi parolingiz bilan endi akkauntga kirishingiz mumkin.": {"en": "You can now sign in with your new password.", "ru": "Теперь вы можете войти с новым паролем."},
    "Yangi parolni kiriting va uni takrorlang.": {"en": "Enter a new password and confirm it.", "ru": "Введите новый пароль и подтвердите его."},
    "Tiklash havolasini yuborish": {"en": "Send reset link", "ru": "Отправить ссылку"},

    # ---- Legal: numbered sections (medium) ----
    "1. Shartlarning qabul qilinishi": {"en": "1. Acceptance of terms", "ru": "1. Принятие условий"},
    "4. Ma'lumotlardan foydalanish": {"en": "4. Use of data",        "ru": "4. Использование данных"},
    "6. Shartlarning o'zgarishi": {"en": "6. Changes to the terms", "ru": "6. Изменения в условиях"},
    "Quyidagi harakatlar taqiqlanadi:": {"en": "The following actions are prohibited:", "ru": "Запрещены следующие действия:"},
    "Boshqa foydalanuvchilarning akkauntlariga ruxsatsiz kirish.": {"en": "Unauthorized access to other users' accounts.", "ru": "Несанкционированный доступ к аккаунтам других пользователей."},
    "Xizmatga zarar yetkazishga urinish (DDoS, injection, bot spam).": {"en": "Attempts to harm the service (DDoS, injection, bot spam).", "ru": "Попытки нанести вред сервису (DDoS, инъекции, бот-спам)."},
    "Mualliflik huquqi yoki qonun himoyalangan ma'lumotlarni noqonuniy to'plash.": {"en": "Unlawful collection of copyrighted or legally protected data.", "ru": "Незаконный сбор данных, защищённых авторским правом или законом."},
    "Sentiment tahlili (AI model orqali).": {"en": "Sentiment analysis (via AI model).", "ru": "Анализ настроений (с помощью AI-модели)."},

    # ---- Empty state messages ----
    "Hali hech qanday akkaunt ulanmagan": {"en": "No accounts connected yet", "ru": "Пока не подключено ни одного аккаунта"},
    "Hali postlar yo'q. Akkauntingizni ulang yoki demo data'ni seed qiling.": {"en": "No posts yet. Connect an account or seed the demo data.", "ru": "Пока нет постов. Подключите аккаунт или заполните демо-данными."},

    # ---- Error page medium ----
    "Serverda kutilmagan xato yuz berdi. Bir oz kuting va qayta urinib ko'ring.": {"en": "An unexpected server error occurred. Please wait a moment and try again.", "ru": "Произошла непредвиденная ошибка сервера. Подождите и попробуйте снова."},

    # ---- Chat placeholder ----
    "env var'ni sozlashi kerak. Kalitni": {"en": "must set the env var. You can obtain the key at", "ru": "должен настроить env-переменную. Ключ можно получить на"},

    # ---- Long descriptive strings (landing, legal, FAQ, email) ----
    "Siz tomonidan ulagan ijtimoiy tarmoq akkaunt ma'lumotlari (handle, follower count).":
        {"en": "Social account metadata you connect (handle, follower count).",
         "ru": "Метаданные подключённых вами соцсетей (handle, количество подписчиков)."},
    "Parolni tiklash havolasini yubordik. Emailingizdagi xatni oching va havolaga o'ting.":
        {"en": "We sent the password reset link. Open your email and follow the link.",
         "ru": "Мы отправили ссылку для сброса пароля. Откройте письмо и перейдите по ссылке."},
    "Barcha ma'lumotingizni bir bosishda yuklab oling — diplom, prezentatsiya yoki mijozga.":
        {"en": "Download all your data in one click — for a thesis, presentation, or client.",
         "ru": "Скачайте все ваши данные в один клик — для диплома, презентации или клиента."},
    "Ha, loyiha to'liq bepul — diplom ishi sifatida ishlab chiqilgan. Kredit karta kerak emas.":
        {"en": "Yes, the project is fully free — built as a diploma work. No credit card required.",
         "ru": "Да, проект полностью бесплатный — создан как дипломная работа. Карта не нужна."},
    "10 dan 300 gacha. Har post uchun 3–14 komment + AI sentiment tahlili avtomatik yaratiladi.":
        {"en": "10 to 300. For each post 3–14 comments + AI sentiment analysis are auto-generated.",
         "ru": "От 10 до 300. Для каждого поста 3–14 комментариев + AI-анализ настроений создаются автоматически."},
    "Platforma sizning akkauntingiz bo'yicha to'playdigan barcha ma'lumotlarni yuklab oling (GDPR-mos).":
        {"en": "Download all data the platform collects about your account (GDPR-compliant).",
         "ru": "Скачайте все данные, собираемые платформой по вашему аккаунту (соответствие GDPR)."},
    "Siz qidirgan sahifa mavjud emas yoki ko'chirilgan. URL'ni tekshirib ko'ring yoki bosh sahifaga qayting.":
        {"en": "The page you're looking for does not exist or has moved. Check the URL or return home.",
         "ru": "Страница, которую вы ищете, не существует или перемещена. Проверьте URL или вернитесь на главную."},
    "Tabiiy tilda yozing — AI siz'ning real ma'lumotingiz asosida javob beradi. OpenAI (gpt-4o-mini) orqali.":
        {"en": "Write in natural language — AI answers based on your real data. Powered by OpenAI (gpt-4o-mini).",
         "ru": "Пишите на обычном языке — AI отвечает на основе ваших реальных данных. Через OpenAI (gpt-4o-mini)."},
    "10 dan 300 gacha. Kanaldan so'nggi shuncha postni — views, reaksiyalar, forwardlar bilan — tortib olamiz.":
        {"en": "10 to 300. We fetch the most recent posts from the channel — with views, reactions, forwards.",
         "ru": "От 10 до 300. Мы загружаем последние посты канала — с просмотрами, реакциями, пересылками."},
    "Jonli grafiklar, interaktiv filtrlash va platformalar bo'yicha solishtirish. Har soniyada yangi ma'lumot.":
        {"en": "Live charts, interactive filtering, and cross-platform comparison. Fresh data every second.",
         "ru": "Живые графики, интерактивная фильтрация и сравнение по платформам. Новые данные каждую секунду."},
    "Ushbu hujjat akademik diplom loyihasi uchun shaklda tayyorlangan va yuridik maslahat sifatida qaralmaydi.":
        {"en": "This document is drafted for an academic diploma project and should not be treated as legal advice.",
         "ru": "Этот документ подготовлен в рамках академического дипломного проекта и не является юридической консультацией."},
    "Summary, Posts, Comments, Sentiment, Platforms — openpyxl bilan formatlangan, filter va donut chart bilan.":
        {"en": "Summary, Posts, Comments, Sentiment, Platforms — formatted with openpyxl, with filter and donut chart.",
         "ru": "Summary, Posts, Comments, Sentiment, Platforms — оформлено через openpyxl, с фильтром и круговой диаграммой."},
    "Gradient cover sahifasi, KPI xulosasi, platforma jadvali, sentiment namunalari, top postlar — ReportLab orqali.":
        {"en": "Gradient cover page, KPI summary, platform table, sentiment samples, top posts — via ReportLab.",
         "ru": "Градиентная обложка, сводка KPI, таблица платформ, образцы настроений, топ постов — через ReportLab."},
    "Yuqoridagi platformalardan birini tanlab, demo ma'lumot yuklang yoki OAuth orqali haqiqiy akkauntingizni ulang.":
        {"en": "Pick one of the platforms above and load demo data, or connect a real account via OAuth.",
         "ru": "Выберите одну из платформ выше и загрузите демо-данные, или подключите настоящий аккаунт через OAuth."},
    "Ijtimoiy tarmoq ma'lumotlarini yig'ish va tahlil qilish platformasi. Talabalar, tadqiqotchilar va marketologlar uchun.":
        {"en": "A social-media data collection and analytics platform. For students, researchers, and marketers.",
         "ru": "Платформа сбора и анализа данных соцсетей. Для студентов, исследователей и маркетологов."},
    "ushbu havola 3 kun ichida amal qiladi. Agar siz\n    so'ramagan bo'lsangiz, xatni o'chirib tashlang — parolingiz o'zgarmaydi.":
        {"en": "this link is valid for 3 days. If you did not request this, just delete the email — your password will not change.",
         "ru": "эта ссылка действует 3 дня. Если вы не запрашивали её, просто удалите письмо — пароль не изменится."},
    "Ha, loyiha MIT litsenziyasi ostida GitHub'da ochiq. Hissa qo'shishingiz yoki o'z ehtiyojlaringizga moslashtirishingiz mumkin.":
        {"en": "Yes, the project is open-source on GitHub under the MIT license. You can contribute or adapt it to your needs.",
         "ru": "Да, проект открыт на GitHub под лицензией MIT. Вы можете внести вклад или адаптировать его под свои нужды."},
    "Social Analytics platformasiga ro'yxatdan o'tganingiz uchun rahmat.\n  Akkauntni faollashtirish uchun quyidagi tugmani bosing:":
        {"en": "Thanks for signing up to the Social Analytics platform.\n  Click the button below to activate your account:",
         "ru": "Спасибо за регистрацию на платформе Social Analytics.\n  Нажмите кнопку ниже, чтобы активировать аккаунт:"},
    "Telegram, YouTube va Instagram ma'lumotlarini yig'ib, sentiment tahlil va interaktiv dashboardlar bilan qarorlar qabul qiling.":
        {"en": "Collect Telegram, YouTube, and Instagram data, then make decisions with sentiment analysis and interactive dashboards.",
         "ru": "Собирайте данные Telegram, YouTube и Instagram, принимайте решения с анализом настроений и интерактивными панелями."},
    "Ushbu siyosat GDPR prinsiplariga asoslanib tayyorlangan, lekin yuridik ekspert tomonidan imzolanmagan. Diplom loyihasi shaklida.":
        {"en": "This policy is drafted on GDPR principles but has not been signed off by a legal expert. Diploma-project format.",
         "ru": "Эта политика подготовлена на основе принципов GDPR, но не подписана юридическим экспертом. Оформление дипломного проекта."},
    "Biz ushbu shartlarni istalgan vaqtda yangilash huquqini\n    saqlab qolamiz. Muhim o'zgarishlar haqida email orqali xabar beriladi.":
        {"en": "We reserve the right to update these terms at any time.\n    Significant changes are announced by email.",
         "ru": "Мы оставляем за собой право обновлять эти условия в любое время.\n    О существенных изменениях мы сообщаем по email."},
    "Siz Social Analytics akkauntingiz uchun parolni tiklash so'rovini\n  yubordingiz. Yangi parol o'rnatish uchun quyidagi tugmani bosing:":
        {"en": "You requested a password reset for your Social Analytics account.\n  Click the button below to set a new password:",
         "ru": "Вы запросили сброс пароля для аккаунта Social Analytics.\n  Нажмите кнопку ниже, чтобы установить новый пароль:"},
    "PostgreSQL (prod) yoki SQLite (dev) ma'lumotlar bazasida. OAuth tokenlari shifrlangan holda saqlanadi, parollar hech qachon saqlanmaydi.":
        {"en": "In PostgreSQL (prod) or SQLite (dev) databases. OAuth tokens are stored encrypted; passwords are never stored.",
         "ru": "В базах данных PostgreSQL (prod) или SQLite (dev). OAuth-токены хранятся зашифрованно, пароли никогда не сохраняются."},
    "Dashboard quyida demo ma'lumotlar bilan ko'rsatilmoqda. Instagram, Telegram, YouTube yoki X akkauntini ulab, haqiqiy statistikani ko'ring.":
        {"en": "The dashboard below is showing demo data. Connect an Instagram, Telegram, YouTube, or X account to see real stats.",
         "ru": "Панель ниже показывает демо-данные. Подключите Instagram, Telegram, YouTube или X, чтобы увидеть реальную статистику."},
    "Biz sizni tizimda ushlab turish uchun zarur session cookie'laridan foydalanamiz. Tahlil (Google Analytics kabi) cookie'lari qo'llanilmaydi.":
        {"en": "We use session cookies required to keep you signed in. We do not use analytics (e.g. Google Analytics) cookies.",
         "ru": "Мы используем сессионные cookie, необходимые для поддержания входа. Аналитические cookie (например Google Analytics) не применяются."},
    "Instagram, Telegram, YouTube va X ma'lumotlarini bir joyda. AI sentiment tahlil, real-time grafiklar, avtomatik hisobotlar — bir necha bosishda.":
        {"en": "Instagram, Telegram, YouTube, and X data in one place. AI sentiment analysis, real-time charts, automatic reports — in a few clicks.",
         "ru": "Данные Instagram, Telegram, YouTube и X в одном месте. AI-анализ настроений, графики в реальном времени, автоотчёты — в несколько кликов."},
    "XLM-RoBERTa (ko'p tilli transformer modeli) kommentlarni pozitiv, neytral va negativ kategoriyalarga ajratadi — o'zbek, rus va ingliz tillarida.":
        {"en": "XLM-RoBERTa (multilingual transformer model) classifies comments as positive, neutral, or negative — in Uzbek, Russian, and English.",
         "ru": "XLM-RoBERTa (мультиязычная трансформер-модель) классифицирует комментарии как позитивные, нейтральные или негативные — на узбекском, русском и английском."},
    "Ayni paytda: Instagram (Graph API), Telegram (Bot API), YouTube (Data API v3), X (v2 API). Keyingi bosqichda TikTok va LinkedIn rejalashtirilgan.":
        {"en": "Currently: Instagram (Graph API), Telegram (Bot API), YouTube (Data API v3), X (v2 API). TikTok and LinkedIn planned for the next phase.",
         "ru": "Сейчас: Instagram (Graph API), Telegram (Bot API), YouTube (Data API v3), X (v2 API). TikTok и LinkedIn запланированы на следующем этапе."},
    "Public Telegram kanalidan haqiqiy maʼlumot tortib olinadi: views, reaksiyalar, forwardlar va komment soni. Postlar fonda Celery task orqali yigʻiladi.":
        {"en": "Real data is pulled from a public Telegram channel: views, reactions, forwards, and comment counts. Posts are collected in the background via a Celery task.",
         "ru": "Реальные данные загружаются из публичного Telegram-канала: просмотры, реакции, пересылки и количество комментариев. Посты собираются в фоне через задачу Celery."},
    "Assalomu alaykum! Dashboard ma'lumotingiz haqida savol bering — masalan, eng yaxshi ishlayotgan platforma, postlaringiz haqida tahlil, yoki engagement trendlari.":
        {"en": "Hello! Ask questions about your dashboard data — e.g. the best-performing platform, analysis of your posts, or engagement trends.",
         "ru": "Здравствуйте! Задайте вопрос о данных панели — например, лучшая платформа, анализ постов или тренды engagement."},
    "{{ n }} ta post topildi — filter va saralashni o'zgartirib ko'ring.\n        {% plural %}\n          {{ n }} ta post topildi — filter va saralashni o'zgartirib ko'ring.":
        {"en": "{{ n }} post found — try changing the filters and sort order.\n        {% plural %}\n          {{ n }} posts found — try changing the filters and sort order.",
         "ru": "Найден {{ n }} пост — попробуйте изменить фильтры и сортировку.\n        {% plural %}\n          Найдено {{ n }} постов — попробуйте изменить фильтры и сортировку."},
    "Ma'lumotlar shifrlangan ulanish orqali uzatiladi (HTTPS/TLS 1.3) va ma'lumotlar bazasida xavfsiz saqlanadi. OAuth tokenlari alohida shifrlash kaliti bilan himoyalanadi.":
        {"en": "Data is transmitted over an encrypted connection (HTTPS/TLS 1.3) and stored securely in the database. OAuth tokens are protected by a separate encryption key.",
         "ru": "Данные передаются по зашифрованному соединению (HTTPS/TLS 1.3) и хранятся безопасно в базе. OAuth-токены защищены отдельным ключом шифрования."},
    "Hisobotlar sizning akkauntingizdagi barcha postlar va kommentlarni o'z ichiga oladi. Agar akkaunt ulanmagan bo'lsa, demo ma'lumotdan foydalaning yoki faqat sarlavha bilan bo'sh hisobot yaratiladi.":
        {"en": "Reports include all posts and comments from your account. If no account is connected, use the demo data or an empty report with only the title is generated.",
         "ru": "Отчёты включают все посты и комментарии вашего аккаунта. Если аккаунт не подключён, используйте демо-данные или будет создан пустой отчёт с одним заголовком."},
    "Social Analytics — ijtimoiy tarmoqlarda (Instagram, Telegram,\n    YouTube, X) postlar va kommentlarni tahlil qilish platformasi. Xizmat\n    ta'lim va tadqiqot maqsadlarida yaratilgan diplom loyihasi.":
        {"en": "Social Analytics — a platform for analysing posts and comments on social networks (Instagram, Telegram,\n    YouTube, X). The service is a diploma project built for educational and research purposes.",
         "ru": "Social Analytics — платформа для анализа постов и комментариев в соцсетях (Instagram, Telegram,\n    YouTube, X). Сервис — дипломный проект, созданный для образования и исследований."},
    "Haqiqiy OAuth integratsiyasi API credentials'larini talab qiladi (Facebook Developer, Google Cloud, Bot tokens). Hozir demo ma'lumot bilan ulanadi — real vaqtda grafiklar va sentiment tahlili ishlaydi.":
        {"en": "Real OAuth integration requires API credentials (Facebook Developer, Google Cloud, bot tokens). For now it connects with demo data — real-time charts and sentiment analysis still work.",
         "ru": "Настоящая OAuth-интеграция требует API credentials (Facebook Developer, Google Cloud, токены ботов). Сейчас подключается с демо-данными — графики и анализ настроений работают в реальном времени."},
    "Siz ulagan ijtimoiy tarmoq akkauntlaringizdagi post va\n    kommentlar faqat sizning shaxsiy dashboardingiz uchun tahlil qilinadi.\n    Biz ma'lumotingizni uchinchi tomonlarga sotmaymiz yoki ulashmaymiz.":
        {"en": "Posts and comments from the social accounts you connect are\n    analysed only for your private dashboard.\n    We never sell or share your data with third parties.",
         "ru": "Посты и комментарии из подключённых вами соцсетей\n    анализируются только для вашей личной панели.\n    Мы не продаём и не передаём ваши данные третьим сторонам."},
    "Har qanday texnik muammo, feature so'rovi yoki shartlar bo'yicha savol —\n    GitHub Issues tracker orqali hal qilinadi. Biz 48 soat ichida javob\n    berishga harakat qilamiz (best effort, kafolat emas).":
        {"en": "Any technical issue, feature request, or question about the terms —\n    is handled through the GitHub Issues tracker. We aim to respond within\n    48 hours (best effort, no guarantee).",
         "ru": "Любые технические проблемы, запросы на функции или вопросы по условиям —\n    решаются через GitHub Issues. Мы стараемся отвечать в течение 48 часов\n    (best effort, без гарантии)."},
    '<strong class="text-slate-900 dark:text-white">{{ email }}</strong> manzili\n          <strong class="text-slate-900 dark:text-white">{{ user_display }}</strong> foydalanuvchiga tegishli ekanligini tasdiqlang.':
        {"en": 'Confirm that <strong class="text-slate-900 dark:text-white">{{ email }}</strong>\n          belongs to user <strong class="text-slate-900 dark:text-white">{{ user_display }}</strong>.',
         "ru": 'Подтвердите, что <strong class="text-slate-900 dark:text-white">{{ email }}</strong>\n          принадлежит пользователю <strong class="text-slate-900 dark:text-white">{{ user_display }}</strong>.'},
    "Social Analytics saytidan (keyinchalik \"Xizmat\") foydalanib,\n    siz quyidagi shartlar va qoidalarga rozilik bildirasiz. Agar siz\n    ushbu shartlarning biror qismiga rozi bo'lmasangiz, Xizmatdan\n    foydalanmang.":
        {"en": 'By using the Social Analytics site (hereinafter the "Service"),\n    you agree to the following terms and conditions. If you do not\n    agree with any part of these terms, do not use the Service.',
         "ru": "Используя сайт Social Analytics (далее «Сервис»),\n    вы соглашаетесь с изложенными условиями и правилами. Если вы\n    не согласны с какой-либо частью этих условий, не пользуйтесь\n    Сервисом."},
    "Platformaning butun manba kodi va dizayni MIT litsenziyasi ostida\n    taqdim etilgan. Siz kodni o'zingizning ehtiyojlaringizga moslashtirishingiz,\n    tarqatishingiz va ta'limdan foydalanishingiz mumkin. Mualliflikni saqlash —\n    MIT litsenziyasi matnini kopiya bilan birga yuborish kifoya.":
        {"en": "The full source code and design of the platform are released\n    under the MIT license. You may adapt the code to your needs,\n    redistribute it, and use it for education. Attribution —\n    shipping the MIT license text with the copy is sufficient.",
         "ru": "Весь исходный код и дизайн платформы распространяются\n    под лицензией MIT. Вы можете адаптировать код под свои нужды,\n    распространять его и использовать в образовании. Атрибуция —\n    достаточно передавать текст лицензии MIT вместе с копией."},
    "5 ta sahifa: brend gradient cover, 9 qatorli executive summary (akkauntlar, postlar, kommentlar, layklar, engagement, sentiment foizlari), platforma bo'yicha metrikalar jadvali, pozitiv va negativ sentiment namunalari (har biridan 5 ta), top 15 post layklar bo'yicha. Ishlab chiqarilgan: ReportLab (pure-Python).":
        {"en": "5 pages: branded gradient cover, a 9-line executive summary (accounts, posts, comments, likes, engagement, sentiment percentages), a per-platform metrics table, positive and negative sentiment samples (5 of each), top 15 posts by likes. Built with ReportLab (pure Python).",
         "ru": "5 страниц: брендированная градиентная обложка, executive summary из 9 строк (аккаунты, посты, комментарии, лайки, engagement, проценты настроений), таблица метрик по платформам, образцы позитивных и негативных настроений (по 5), топ-15 постов по лайкам. Создано на ReportLab (чистый Python)."},
    "Uch darajali tiered engine: (1) XLM-RoBERTa transformer (opt-in, cardiffnlp tomonidan Twitter korpusida o'qitilgan, ~82% F1), (2) VADER lexicon O'zbek/Rus keyword kengaytmasi bilan (~75% F1 ikki tilda), (3) fallback keyword engine. Har komment uchun model nomi DB'da saqlanadi, natijalarni modellar aro solishtirish mumkin.":
        {"en": "Three-tier engine: (1) XLM-RoBERTa transformer (opt-in, trained by cardiffnlp on the Twitter corpus, ~82% F1), (2) VADER lexicon extended with Uzbek/Russian keywords (~75% F1 on the two languages), (3) fallback keyword engine. The model name is stored in the DB per comment, so results can be compared across models.",
         "ru": "Трёхуровневый движок: (1) трансформер XLM-RoBERTa (по желанию, обучен cardiffnlp на корпусе Twitter, ~82% F1), (2) лексикон VADER с расширением узбекских/русских ключевых слов (~75% F1 на двух языках), (3) резервный движок по ключевым словам. Имя модели сохраняется в БД для каждого комментария — результаты можно сравнивать между моделями."},
    "Ushbu xizmat akademik diplom loyihasi sifatida yaratilgan. Biz\n    platformaning uzluksiz ishlashi, ma'lumotlarning yo'qolmasligi yoki\n    uchinchi tomon API'lari (Instagram, Telegram, YouTube, X) bilan uzluksiz\n    aloqa bo'yicha kafolat bermaymiz. Siz xizmatdan \"as-is\" foydalanasiz.\n    Biznes maqsadida foydalanish uchun o'zingiz tekshiring.":
        {"en": "This service is created as an academic diploma project. We\n    make no guarantees about uninterrupted availability, data durability,\n    or continuous connectivity with third-party APIs (Instagram, Telegram,\n    YouTube, X). You use the service \"as is\".\n    Verify suitability yourself before using it for business purposes.",
         "ru": "Этот сервис создан как академический дипломный проект. Мы\n    не гарантируем бесперебойную работу платформы, сохранность данных\n    или непрерывную связь со сторонними API (Instagram, Telegram, YouTube, X).\n    Вы используете сервис «как есть».\n    Для коммерческого использования проверяйте пригодность самостоятельно."},
    "Schema va OAuth callback infrastrukturasi tayyor. Haqiqiy ulanish uchun Meta Business Verification (7-14 kun review), Google Cloud OAuth client va Telegram Bot Token kerak. Hozirda loyiha demo rejimda ishlaydi — realistik ma'lumot, haqiqiy sentiment modeli, haqiqiy PDF/Excel eksport. API credentials qo'yilgach kod o'zgarmaydi, avtomatik haqiqiy rejimga o'tadi.":
        {"en": "The schema and OAuth callback infrastructure are ready. Real connections need Meta Business Verification (7–14 day review), a Google Cloud OAuth client, and a Telegram Bot Token. The project currently runs in demo mode — realistic data, real sentiment model, real PDF/Excel export. Once API credentials are provided, no code changes are required — it switches to real mode automatically.",
         "ru": "Инфраструктура схемы и OAuth-колбэков готова. Для настоящего подключения нужны Meta Business Verification (проверка 7–14 дней), Google Cloud OAuth-клиент и Telegram Bot Token. Сейчас проект работает в демо-режиме — реалистичные данные, настоящая модель настроений, настоящий экспорт PDF/Excel. Как только API credentials предоставлены, код не меняется — автоматически переходит в реальный режим."},

    # ---- Phase-15: new analytics + ML pages (bulk-added 2026-04) ----
    "AI Xulosa":                       {"en": "AI Summary",            "ru": "AI Сводка"},
    "AI Haftalik Xulosa":              {"en": "AI Weekly Summary",     "ru": "AI Недельная сводка"},
    "ML Bashorat":                     {"en": "ML Forecast",           "ru": "ML Прогноз"},
    "Bashorat qilish":                 {"en": "Predict",               "ru": "Прогноз"},
    "Bashorat tayyor emas":            {"en": "No forecast yet",       "ru": "Прогноз ещё не готов"},
    "Engagement bashorati":            {"en": "Engagement forecast",   "ru": "Прогноз вовлечённости"},
    "Hisobotni yaratish":              {"en": "Generate report",       "ru": "Создать отчёт"},
    "Qaytadan yaratish":               {"en": "Regenerate",            "ru": "Создать заново"},
    "Yangi xulosa yaratish":           {"en": "Generate new summary",  "ru": "Создать новую сводку"},
    "Haftalik xulosa":                 {"en": "Weekly summary",        "ru": "Недельная сводка"},
    "Mavzu klasterlari":               {"en": "Topic clusters",        "ru": "Кластеры тем"},
    "Klasterlar":                      {"en": "Clusters",              "ru": "Кластеры"},
    "Klaster":                         {"en": "Cluster",               "ru": "Кластер"},
    "Eng yaxshi namuna":               {"en": "Best example",          "ru": "Лучший пример"},
    "Eng samarali klaster:":           {"en": "Top cluster:",          "ru": "Лучший кластер:"},
    "Korrelyatsiya":                   {"en": "Correlation",           "ru": "Корреляция"},
    "Sentiment × Engagement":          {"en": "Sentiment × Engagement","ru": "Тональность × Вовлечённость"},
    "Scatter plot":                    {"en": "Scatter plot",          "ru": "Точечный график"},
    "Pearson r":                       {"en": "Pearson r",             "ru": "Pearson r"},
    "Bildirishnomalar":                {"en": "Notifications",         "ru": "Уведомления"},
    "yangi":                           {"en": "new",                   "ru": "новых"},
    "Yopish":                          {"en": "Dismiss",               "ru": "Закрыть"},
    "API kirish kaliti":               {"en": "API access key",        "ru": "Ключ доступа API"},
    "Yashirish":                       {"en": "Hide",                  "ru": "Скрыть"},
    "Korsatish":                       {"en": "Show",                  "ru": "Показать"},
    "Nusxalash":                       {"en": "Copy",                  "ru": "Копировать"},
    "Nusxalandi":                      {"en": "Copied",                "ru": "Скопировано"},
    "API hujjati:":                    {"en": "API docs:",             "ru": "API документация:"},
    "Foydalanish misoli:":             {"en": "Usage example:",        "ru": "Пример использования:"},
    "Sizning JWT tokeningiz:":         {"en": "Your JWT token:",       "ru": "Ваш JWT-токен:"},
    "Raqobatchilar":                   {"en": "Competitors",           "ru": "Конкуренты"},
    "Raqobatchilarni kuzatish":        {"en": "Competitor tracking",   "ru": "Отслеживание конкурентов"},
    "Raqobatchi o'chirildi.":          {"en": "Competitor removed.",   "ru": "Конкурент удалён."},
    "Yangi raqobatchi qo'shish":       {"en": "Add new competitor",    "ru": "Добавить конкурента"},
    "Solishtirma jadval":              {"en": "Comparison table",      "ru": "Сравнительная таблица"},
    "Sizniki":                         {"en": "Yours",                 "ru": "Ваш"},
    "Eslatma (ixtiyoriy)":             {"en": "Note (optional)",       "ru": "Заметка (опционально)"},
    "Eslatma / sizniki":               {"en": "Note / yours",          "ru": "Заметка / ваш"},
    "Auditoriya o'sishi":              {"en": "Audience growth",       "ru": "Рост аудитории"},
    "30 kunlik obunachi soni dinamikasi":
        {"en": "30-day follower-count dynamics", "ru": "Динамика подписчиков за 30 дней"},
    "o'zgarmagan":                     {"en": "no change",             "ru": "без изменений"},
    "Engagement funnel":               {"en": "Engagement funnel",     "ru": "Воронка вовлечённости"},
    "Auditoriya postdan oxirgi harakatga qadar qanday qisqaradi":
        {"en": "How the audience narrows from view to share", "ru": "Как аудитория сужается от просмотра к репосту"},
    "Repostlar":                       {"en": "Reposts",               "ru": "Репосты"},
    "Post uzunligi tahlili":           {"en": "Post-length analysis",  "ru": "Анализ длины поста"},
    "Caption uzunligi vs engagement (so'nggi 30 kun)":
        {"en": "Caption length vs engagement (last 30 days)", "ru": "Длина подписи vs вовлечённость (30 дней)"},
    "Eng yaxshisi:":                   {"en": "Best:",                 "ru": "Лучший:"},
    "belgi":                           {"en": "chars",                 "ru": "симв."},
    "Tavsiya:":                        {"en": "Tip:",                  "ru": "Совет:"},
    "Eng yaxshi vaqt":                 {"en": "Best time",             "ru": "Лучшее время"},
    "Hafta kuni × soat — engagement bo'yicha (so'nggi 30 kun)":
        {"en": "Weekday × hour — by engagement (last 30 days)",
         "ru": "День недели × час — по вовлечённости (30 дней)"},
    "Top mavzular":                    {"en": "Top topics",            "ru": "Топ темы"},
    "Postlaringizdagi eng faol so'zlar":
        {"en": "Most-used words in your posts", "ru": "Самые частые слова в постах"},
    "Top hashtaglar":                  {"en": "Top hashtags",          "ru": "Топ хэштеги"},
    "Eng ko'p ishlatilgan #teglar":    {"en": "Most-used #tags",       "ru": "Чаще всего используемые #теги"},
    "Post chastotasi":                 {"en": "Post frequency",        "ru": "Частота постов"},
    "Engagement (hozirgi)":            {"en": "Engagement (current)",  "ru": "Вовлечённость (текущая)"},
    "Engagement o'zgarishi":           {"en": "Engagement change",     "ru": "Изменение вовлечённости"},
    "30 kunlik o'rtacha engagement":   {"en": "30-day average engagement","ru":"Средняя вовлечённость за 30 дней"},
    "Oldingi 30 kunga nisbatan":       {"en": "Compared to previous 30 days","ru":"По сравнению с прошлыми 30 днями"},
    "o'sdi":                           {"en": "up",                    "ru": "выросло"},
    "kamaydi":                         {"en": "down",                  "ru": "снизилось"},
    "Sentiment dinamikasi":            {"en": "Sentiment dynamics",    "ru": "Динамика настроений"},
    "So'nggi 30 kun — kommentlardagi pozitiv / neytral / negativ sonlari":
        {"en": "Last 30 days — positive / neutral / negative comment counts",
         "ru": "30 дней — позитивных / нейтральных / негативных комментариев"},
    "Mavzu × Sentiment matritsasi":    {"en": "Topic × Sentiment matrix","ru":"Матрица Тема × Настроение"},
    "Qaysi mavzudagi postlaringizga qanday reaktsiya keladi":
        {"en": "Which topics get which reactions", "ru": "Какие темы вызывают какую реакцию"},
    "Pozitiv":                         {"en": "Positive",              "ru": "Позитивная"},
    "Neytral":                         {"en": "Neutral",               "ru": "Нейтральная"},
    "Negativ":                         {"en": "Negative",              "ru": "Негативная"},
    "Sizga tavsiyalar":                {"en": "Recommendations",       "ru": "Рекомендации"},
    "Real ma'lumotlardan kelib chiqib avtomatik yaratildi":
        {"en": "Auto-generated from your real data", "ru": "Автоматически создано из ваших данных"},
    "Post turlari bo'yicha":           {"en": "By post type",          "ru": "По типу поста"},
    "Rasm, video, matn va boshqa kontent ulushlari":
        {"en": "Photos, videos, text and other content shares", "ru": "Фото, видео, текст и другие типы"},
    "Hozir demo ma'lumot ko'rsatilyapti":
        {"en": "Showing demo data right now", "ru": "Сейчас показаны демо-данные"},
    "Telegram, YouTube yoki VK akkauntingizni ulab, real grafiklar va tavsiyalarni oling.":
        {"en": "Connect your Telegram, YouTube or VK account to get real charts and recommendations.",
         "ru": "Подключите Telegram, YouTube или VK, чтобы получить реальные графики и рекомендации."},
    "Real akkaunt ulash":              {"en": "Connect a real account","ru": "Подключить реальный аккаунт"},
    "Optimal Posting AI":              {"en": "Optimal Posting AI",    "ru": "Optimal Posting AI"},
    "ML model bilan o'ynash":          {"en": "Play with ML model",    "ru": "Настроить ML-модель"},
    "Like rate":                       {"en": "Like rate",             "ru": "Доля лайков"},
    "Discussion rate":                 {"en": "Discussion rate",       "ru": "Доля комментариев"},
    "Virality":                        {"en": "Virality",              "ru": "Вирусность"},
    "Likes / Views":                   {"en": "Likes / Views",         "ru": "Лайки / Просмотры"},
    "Kommentlar / Views":              {"en": "Comments / Views",      "ru": "Комментарии / Просмотры"},
    "Shares / Views":                  {"en": "Shares / Views",        "ru": "Репосты / Просмотры"},
    "Platforma engagement solishtiruvi":{"en":"Platform engagement comparison","ru":"Сравнение вовлечённости платформ"},
    "Sizning ulangan tarmoqlaringiz qaysisida ish yaxshiroq":
        {"en":"Which of your connected networks performs best","ru":"Какая из подключённых сетей работает лучше"},
    "Yetakchi:":                       {"en": "Leader:",               "ru": "Лидер:"},
    "Top postlardagi naqshlar":        {"en": "Top-post patterns",     "ru": "Закономерности топ-постов"},
    "Eng yaxshi 25% post o'rtasidagi qiymatlar (qolganlariga nisbatan)":
        {"en":"Average values in the top 25% of posts (vs the rest)","ru":"Средние в топ-25% постов (vs остальных)"},
    "Emojilar":                        {"en":"Emojis",                 "ru":"Эмодзи"},
    "Savol belgilari":                 {"en":"Question marks",         "ru":"Вопросительные знаки"},
    "Hashtaglar":                      {"en":"Hashtags",               "ru":"Хэштеги"},
    "Linklar":                         {"en":"Links",                  "ru":"Ссылки"},
    "Caption belgi":                   {"en":"Caption chars",          "ru":"Симв. подписи"},
    "Yordam":                          {"en":"Help",                   "ru":"Помощь"},
    "Yordam markazi":                  {"en":"Help center",            "ru":"Центр помощи"},
    "Boshlash":                        {"en":"Get started",            "ru":"Начало"},
    "Imkoniyatlar":                    {"en":"Features",               "ru":"Возможности"},
    "Klaviatura yorliqlari":           {"en":"Keyboard shortcuts",     "ru":"Горячие клавиши"},
    "Texnik stek":                     {"en":"Tech stack",             "ru":"Технологический стек"},
    "Platforma integratsiyalari":      {"en":"Platform integrations",  "ru":"Интеграции платформ"},
    "Tez-tez beriladigan savollar":    {"en":"FAQ",                    "ru":"Часто задаваемые вопросы"},
    "Buyruqlar paneli":                {"en":"Command palette",        "ru":"Командная палитра"},
    "Sahifani chop etish":             {"en":"Print page",             "ru":"Печать страницы"},
    "Dark/light":                      {"en":"Dark/light",             "ru":"Тёмная/светлая"},
    "Real OAuth":                      {"en":"Real OAuth",             "ru":"Реальный OAuth"},
    "Demo rejim":                      {"en":"Demo mode",              "ru":"Демо-режим"},
    "Sozlamalar":                      {"en":"Settings",               "ru":"Настройки"},
    "Tushundim!":                      {"en":"Got it!",                "ru":"Понял!"},
    "Keyingi":                         {"en":"Next",                   "ru":"Далее"},
    "Orqaga":                          {"en":"Back",                   "ru":"Назад"},
    "Tahlil qilish":                   {"en":"Analyze",                "ru":"Анализировать"},
    "Tanlanganda barcha postlar yig'iladi — katta kanallarda bir necha daqiqa kutish mumkin.":
        {"en":"All posts will be collected after selection — large channels may take a few minutes.",
         "ru":"После выбора собираются все посты — для больших каналов это может занять несколько минут."},
    "Mening kanallarim":               {"en":"My channels",            "ru":"Мои каналы"},
    "Kanallar":                        {"en":"Channels",               "ru":"Каналы"},
    "Guruhlar":                        {"en":"Groups",                 "ru":"Группы"},
    "Hammasi":                         {"en":"All",                    "ru":"Все"},
    "Egasi":                           {"en":"Owner",                  "ru":"Владелец"},
    "Admin":                           {"en":"Admin",                  "ru":"Админ"},
    "obunachi":                        {"en":"subscribers",            "ru":"подписчиков"},
    "a'zo":                            {"en":"members",                "ru":"участников"},
    "Qidirish...":                     {"en":"Search...",              "ru":"Поиск..."},
    "Hamma postlarni olish (sekinroq, lekin to'liq tarix)":
        {"en":"Pull all posts (slower, but full history)",
         "ru":"Загрузить все посты (медленнее, но полная история)"},
    "Yangilash":                       {"en":"Refresh",                "ru":"Обновить"},
    "Hozir yangilash":                 {"en":"Refresh now",            "ru":"Обновить сейчас"},
    "Oxirgi sync":                     {"en":"Last sync",              "ru":"Посл. синх."},
    "Akkauntlar":                      {"en":"Accounts",               "ru":"Аккаунты"},
    "Jami obunachilar":                {"en":"Total followers",        "ru":"Всего подписчиков"},
    "Jami postlar":                    {"en":"Total posts",            "ru":"Всего постов"},
    "Real ulangan":                    {"en":"Really connected",       "ru":"Подключено реально"},

    # ---- Phase-15 batch 2: descriptions and short paragraphs ----
    "Past — engagement tasodifiy. Ko'proq post yoki o'xshash ma'lumot kerak.":
        {"en": "Low — engagement is random. More posts or richer data are needed.",
         "ru": "Низкое — вовлечённость случайна. Нужно больше постов или подобных данных."},
    "Dashboard'da KPI'lar, AI tavsiyalar va eng yaxshi posting AI ko'rinadi.":
        {"en": "The dashboard shows KPIs, AI recommendations and the Optimal Posting AI.",
         "ru": "На дашборде отображаются KPI, AI-рекомендации и Optimal Posting AI."},
    "Tabiiy tilda savol bering, AI sizning ma'lumotingiz haqida javob beradi":
        {"en": "Ask in natural language, AI replies based on your data",
         "ru": "Спросите на естественном языке, AI ответит по вашим данным"},
    "Siz ro'yxatdan o'tganda haqiqiy email manzilingizni kiritishingiz kerak.":
        {"en": "You must provide a real email address when signing up.",
         "ru": "При регистрации нужно указать настоящий email."},
    "Sizga tasdiqlash xati yubordik. Iltimos, emailingizdagi havolaga o'ting.":
        {"en": "We sent you a confirmation email. Please follow the link in your inbox.",
         "ru": "Мы отправили письмо подтверждения. Перейдите по ссылке в почте."},
    "Sahifadagi yuqori paneldan tilni istagan vaqtda o'zgartirishingiz mumkin.":
        {"en": "You can switch the language any time from the top bar.",
         "ru": "Язык можно сменить в любой момент через верхнюю панель."},
    "Anomaliya aniqlash tizimi tomonidan avtomatik yaratilgan ogohlantirishlar.":
        {"en": "Alerts auto-generated by the anomaly-detection system.",
         "ru": "Уведомления, автоматически создаваемые системой обнаружения аномалий."},
    "Loyihaning barcha imkoniyatlari, qanday foydalanish va texnik tafsilotlar.":
        {"en": "All project features, how to use them, and the technical details.",
         "ru": "Все возможности проекта, как ими пользоваться, и технические детали."},
    "Serverda kutilmagan xato yuz berdi. Bir oz kuting va qayta urinib ko'ring.":
        {"en": "An unexpected server error occurred. Please wait a moment and try again.",
         "ru": "Произошла непредвиденная ошибка сервера. Подождите и попробуйте снова."},
    "Yig'ishdan hisobotgacha — barchasi bir joyda, barchasi avtomatlashtirilgan.":
        {"en": "From collection to reporting — all in one place, all automated.",
         "ru": "От сбора до отчётов — всё в одном месте, всё автоматизировано."},
    "Mualliflik huquqi yoki qonun himoyalangan ma'lumotlarni noqonuniy to'plash.":
        {"en": "Illegal collection of copyrighted or legally protected data.",
         "ru": "Незаконный сбор данных, защищённых авторским правом или законом."},
    "VK OAuth bilan kirib, devor postlari (likes, kommentlar, repostlar) yig'ish.":
        {"en": "Sign in with VK OAuth and collect wall posts (likes, comments, reposts).",
         "ru": "Вход через VK OAuth и сбор постов со стены (лайки, комментарии, репосты)."},
    "Ma'lumotingizni istalgan vaqtda ko'chirib olish (Settings → Export my data).":
        {"en": "Export your data any time (Settings → Export my data).",
         "ru": "Экспортируйте свои данные в любой момент (Настройки → Экспорт)."},
    "2–3 ta akkaunt tanlang va KPI'lar bilan 30-kunlik trendni yonma-yon ko'ring.":
        {"en": "Pick 2–3 accounts and view their KPIs and 30-day trend side by side.",
         "ru": "Выберите 2–3 аккаунта и сравните KPI и 30-дневный тренд."},
    "Bildirishnomalar yo'q. Anomaliya tizimi ish boshlasa, bu yerda paydo bo'ladi.":
        {"en": "No notifications yet. They appear here once the anomaly system is active.",
         "ru": "Уведомлений пока нет. Они появятся здесь, когда заработает система аномалий."},
    "Davom etish uchun <strong>{{ email }}</strong> email manzilini aniq kiriting:":
        {"en": "To continue, type the exact email <strong>{{ email }}</strong>:",
         "ru": "Чтобы продолжить, введите точно email <strong>{{ email }}</strong>:"},
    "Parolni tiklash havolasi yaroqsiz, muddati o'tgan yoki allaqachon ishlatilgan.":
        {"en": "The password reset link is invalid, expired, or already used.",
         "ru": "Ссылка для сброса пароля недействительна, истекла или уже использована."},
    "OAuth orqali ulanganda platformalarning token'lari shifrlangan holda saqlanadi.":
        {"en": "When connecting via OAuth, platform tokens are stored encrypted.",
         "ru": "При подключении через OAuth токены платформ хранятся в зашифрованном виде."},
    "Google OAuth bilan kirib, video, watch time, kommentlar va obunachilarni yig'ish.":
        {"en": "Sign in with Google OAuth and collect videos, watch time, comments, and subscribers.",
         "ru": "Вход через Google OAuth — сбор видео, watch time, комментариев и подписчиков."},
    "Akkauntlarim sahifasiga o'ting va Telegram, YouTube yoki VK akkauntingizni ulang.":
        {"en": "Open the My Accounts page and connect your Telegram, YouTube, or VK account.",
         "ru": "Откройте Мои аккаунты и подключите Telegram, YouTube или VK."},
    "Analitika sahifalarida chuqur tahlil — heatmap, post turi, sentiment, ML bashorat.":
        {"en": "On the analytics pages — heatmap, post type, sentiment, ML forecasts.",
         "ru": "На страницах аналитики — heatmap, тип поста, тональность, ML-прогноз."},
    "Siz tomonidan ulagan ijtimoiy tarmoq akkaunt ma'lumotlari (handle, follower count).":
        {"en": "Social-network account info you have connected (handle, follower count).",
         "ru": "Данные подключённых соцсетей (handle, число подписчиков)."},
    "Parolni tiklash havolasini yubordik. Emailingizdagi xatni oching va havolaga o'ting.":
        {"en": "We sent a password reset link. Open the email and follow the link.",
         "ru": "Мы отправили ссылку для сброса пароля. Откройте письмо и перейдите по ссылке."},
    "Telegram, YouTube yoki VK akkauntingizni ulab, real grafiklar va tavsiyalarni oling.":
        {"en": "Connect your Telegram, YouTube or VK account to get real charts and recommendations.",
         "ru": "Подключите Telegram, YouTube или VK, чтобы получить реальные графики и рекомендации."},
    "Telegram'ga ro'yxatdan o'tgan raqamingiz, xalqaro formatda. Sizga SMS-kod yuboriladi.":
        {"en": "Your Telegram-registered phone, in international format. We'll send you an SMS code.",
         "ru": "Ваш номер из Telegram в международном формате. Вам отправят SMS-код."},
    "Ha — Settings → Ma'lumotlarni eksport (GDPR JSON), yoki Reports sahifasidan Excel/PDF.":
        {"en": "Yes — Settings → Export my data (GDPR JSON), or Excel/PDF on the Reports page.",
         "ru": "Да — Настройки → Экспорт моих данных (GDPR JSON) или Excel/PDF на странице отчётов."},
    "Barcha ma'lumotingizni bir bosishda yuklab oling — diplom, prezentatsiya yoki mijozga.":
        {"en": "Download all your data in one click — for a thesis, presentation, or client.",
         "ru": "Скачайте все данные одним кликом — для диплома, презентации или клиента."},
    "Pozitiv kommentlar engagement'ni oshiradimi? Pearson korrelyatsiyasi bilan tekshiramiz.":
        {"en": "Do positive comments lift engagement? We check via Pearson correlation.",
         "ru": "Повышают ли положительные комментарии вовлечённость? Проверяем коэффициентом Пирсона."},
    "Ha, loyiha to'liq bepul — diplom ishi sifatida ishlab chiqilgan. Kredit karta kerak emas.":
        {"en": "Yes, the project is fully free — built as a diploma project. No credit card required.",
         "ru": "Да, проект полностью бесплатный — это дипломная работа. Карта не нужна."},
    "Telefon raqam + SMS kod orqali kirish, kanal/guruh tanlash, postlar va kommentlar yig'ish.":
        {"en": "Sign in via phone + SMS code, pick a channel/group, collect posts and comments.",
         "ru": "Вход по телефону + SMS, выбор канала/группы, сбор постов и комментариев."},
    "Public kanallarni ulang va sizning akkauntingiz bilan obunachi soni bo'yicha solishtiring.":
        {"en": "Add public channels and compare them to your account by follower count.",
         "ru": "Добавляйте публичные каналы и сравнивайте их с вашим аккаунтом по подписчикам."},
    "Postlaringiz mavzu bo'yicha avtomatik guruhlanadi va har klaster engagement'i taqqoslanadi.":
        {"en": "Posts are auto-grouped by topic and each cluster's engagement is compared.",
         "ru": "Посты автоматически группируются по теме, и сравнивается вовлечённость каждого кластера."},
    "10 dan 5000 gacha. Har post uchun 3–14 komment + AI sentiment tahlili avtomatik yaratiladi.":
        {"en": "From 10 to 5000. Each post gets 3–14 generated comments + automatic AI sentiment analysis.",
         "ru": "От 10 до 5000. Для каждого поста — 3–14 комментариев + автоматический AI-анализ настроений."},
    "Production: Instagram Business akkaunt + Meta App Review (1-2 hafta) talab qiladi. Hozir demo.":
        {"en": "Production needs an Instagram Business account + Meta App Review (1-2 weeks). Demo for now.",
         "ru": "В продакшне нужен Instagram Business + Meta App Review (1-2 недели). Сейчас демо."},
    "Platforma sizning akkauntingiz bo'yicha to'playdigan barcha ma'lumotlarni yuklab oling (GDPR-mos).":
        {"en": "Download all data the platform collects on your account (GDPR-compliant).",
         "ru": "Скачайте все данные, которые платформа собирает по вашему аккаунту (GDPR)."},

    # ---- AI Post Generator / AI Insight ----
    "AI":                  {"en": "AI",                 "ru": "AI"},
    "AI Post Generator":   {"en": "AI Post Generator",  "ru": "AI Генератор Постов"},
    "Post Generator":      {"en": "Post Generator",     "ru": "Генератор Постов"},
    "AI maslahat":         {"en": "AI advice",          "ru": "AI совет"},
    "Yangi post yarating": {"en": "Create a new post",  "ru": "Создайте новый пост"},
    "Eng yaxshi postlaringiz uslubida 3 ta yangi caption taklifi.":
        {"en": "Three new caption drafts in the style of your top posts.",
         "ru": "Три новых варианта подписи в стиле ваших лучших постов."},
    "AI sizning eng top postlaringizning uslubini, uzunligini va emoji pattern'ini o'rganib, 3 ta yangi caption taklif qiladi.":
        {"en": "AI learns the style, length, and emoji pattern of your top posts and suggests 3 new captions.",
         "ru": "AI изучит стиль, длину и шаблон эмодзи ваших лучших постов и предложит 3 новых варианта."},
    "Sun'iy intellekt 30 kunlik ma'lumotingiz asosida xulosa va keyingi qadamni tavsiya qiladi.":
        {"en": "AI summarises your last 30 days and recommends a next step.",
         "ru": "AI обобщает данные за 30 дней и рекомендует следующий шаг."},
    "3 ta variant yaratish": {"en": "Generate 3 drafts", "ru": "Создать 3 варианта"},
    "Maslahat olish":      {"en": "Get advice",         "ru": "Получить совет"},
    "Tayyor variantlar":   {"en": "Generated drafts",   "ru": "Готовые варианты"},
    "Tayyorlanmoqda...":   {"en": "Generating...",      "ru": "Генерация..."},
    "Nusxa":               {"en": "Copy",               "ru": "Копия"},
    "Nusxa olish":         {"en": "Copy",               "ru": "Скопировать"},
    "Bosib copy oling":    {"en": "Click to copy",      "ru": "Нажмите чтобы скопировать"},
    "Hammasini copy":      {"en": "Copy all",           "ru": "Копировать все"},
    "Olindi":              {"en": "Copied",             "ru": "Скопировано"},
    "AI hali sozlanmagan": {"en": "AI is not configured", "ru": "AI ещё не настроен"},
    "Administrator OPENAI_API_KEY env var'ni sozlashi kerak.":
        {"en": "Administrator must configure the OPENAI_API_KEY env var.",
         "ru": "Администратор должен настроить переменную OPENAI_API_KEY."},

    # ---- Best Time to Post ----
    "Eng yaxshi vaqt":     {"en": "Best time",          "ru": "Лучшее время"},
    "Post qo'yish uchun eng yaxshi vaqt":
        {"en": "Best time to post", "ru": "Лучшее время для публикации"},
    "90 kunlik post tarixingizdan o'rganilgan: kun × soat heatmap'i — engagement intensivligi bo'yicha.":
        {"en": "Learned from your last 90 days: a day × hour heatmap of engagement intensity.",
         "ru": "Вывод из 90 дней постов: тепловая карта день × час по интенсивности вовлечённости."},
    "Heatmap (7 kun × 24 soat)": {"en": "Heatmap (7 days × 24 hours)", "ru": "Тепловая карта (7 дней × 24 часа)"},
    "To'q yashil = yuqori engagement. Oq = postingiz yo'q.":
        {"en": "Dark green = high engagement. White = no posts.",
         "ru": "Тёмно-зелёный = высокая вовлечённость. Белый = нет постов."},
    "Kam":                 {"en": "Low",                "ru": "Мало"},
    "Ko'p":                {"en": "High",               "ru": "Много"},
    "Vaqt foydalanuvchining mahalliy zonasida. Kursorni katakka olib boring — aniq raqamlarni ko'rasiz.":
        {"en": "Times are in your local timezone. Hover a cell for exact numbers.",
         "ru": "Время в вашем часовом поясе. Наведите курсор на ячейку, чтобы увидеть точные цифры."},
    "Hali ma'lumot yetarli emas":
        {"en": "Not enough data yet", "ru": "Пока недостаточно данных"},
    "Heatmap'ni ko'rsatish uchun kamida bir nechta postingiz bo'lishi kerak. Avval akkaunt ulang va sync qiling.":
        {"en": "We need at least a few of your posts to render the heatmap. Connect an account and sync first.",
         "ru": "Для тепловой карты нужно несколько ваших постов. Сначала подключите аккаунт и синхронизируйте."},
    "O'rtacha engagement": {"en": "Avg. engagement",    "ru": "Средняя вовлечённость"},
    "post":                {"en": "post",               "ru": "пост"},

    # ---- Hashtag Analyzer ----
    "Hashtag":             {"en": "Hashtag",            "ru": "Хештег"},
    "Hashtag tahlili":     {"en": "Hashtag analysis",   "ru": "Анализ хештегов"},
    "Qaysi hashtaglaringiz eng yuqori engagement keltirayapti — 90 kunlik ma'lumot.":
        {"en": "Which hashtags drive your highest engagement — last 90 days.",
         "ru": "Какие хештеги дают самую высокую вовлечённость — за 90 дней."},
    "Eslatma: kamida 2 ta postda uchragan hashtaglar ko'rsatiladi (bitta post statistikasi shovqin bo'ladi).":
        {"en": "Note: only hashtags used in 2+ posts are shown (single-post averages are too noisy).",
         "ru": "Показаны хештеги из 2+ постов (статистика по одному посту — слишком шумная)."},
    "Hozircha hashtag yo'q":
        {"en": "No hashtags yet", "ru": "Хештегов пока нет"},
    "Postlaringiz captionida hashtag bo'lmagan yoki hech bir tag 2+ marta ishlatilmagan. Hashtag qo'shib post yozgach, bu sahifa tahlilni ko'rsatadi.":
        {"en": "Either your captions have no hashtags or none was used 2+ times. Add hashtags and publish more — this page will fill up.",
         "ru": "Либо в подписях нет хештегов, либо ни один не был использован 2+ раз. Добавьте хештеги и публикуйте чаще — страница заполнится."},
    "Keyingi post uchun AI tavsiya":
        {"en": "AI recommendation for your next post", "ru": "AI рекомендация для следующего поста"},
    "Statistikangiz asosida 5-7 ta optimal hashtag kombinatsiyasi.":
        {"en": "An optimal combo of 5-7 hashtags based on your stats.",
         "ru": "Оптимальная комбинация из 5-7 хештегов на основе вашей статистики."},
    "Hashtag tavsiya olish": {"en": "Get hashtag suggestions", "ru": "Получить рекомендации по хештегам"},
    "Tavsiya yaratilmadi":   {"en": "Could not generate a suggestion", "ru": "Не удалось создать рекомендацию"},

    # ---- 2FA ----
    "2FA":                 {"en": "2FA",                "ru": "2FA"},
    "Ikki bosqichli autentifikatsiya":
        {"en": "Two-factor authentication", "ru": "Двухфакторная аутентификация"},
    "Ikki bosqichli autentifikatsiya (2FA)":
        {"en": "Two-factor authentication (2FA)", "ru": "Двухфакторная аутентификация (2FA)"},
    "Akkauntingizni TOTP kodlari bilan himoyalang — Google Authenticator, Authy, 1Password va boshqalarda ishlaydi.":
        {"en": "Protect your account with TOTP codes — works with Google Authenticator, Authy, 1Password, and more.",
         "ru": "Защитите аккаунт TOTP-кодами — работает с Google Authenticator, Authy, 1Password и др."},
    "TOTP kodlari (Google Authenticator, Authy, 1Password) bilan qo'shimcha himoya.":
        {"en": "Extra protection with TOTP codes (Google Authenticator, Authy, 1Password).",
         "ru": "Дополнительная защита через TOTP-коды (Google Authenticator, Authy, 1Password)."},
    "Yoqilgan":            {"en": "Enabled",            "ru": "Включено"},
    "O'chirilgan":         {"en": "Disabled",           "ru": "Выключено"},
    "Yoqish":              {"en": "Enable",             "ru": "Включить"},
    "Boshqarish":          {"en": "Manage",             "ru": "Управлять"},
    "Har safar kirishda kod talab qilinadi.":
        {"en": "A code will be required every time you sign in.",
         "ru": "При каждом входе будет требоваться код."},
    "Quyidagi QR kodni Authenticator ilovangizga qo'shing va 6 raqamli kodni kiriting.":
        {"en": "Add the QR code to your Authenticator app, then enter the 6-digit code.",
         "ru": "Добавьте QR-код в приложение-аутентификатор и введите 6-значный код."},
    "1-qadam: QR kodni scan qiling": {"en": "Step 1: Scan the QR", "ru": "Шаг 1: Отсканируйте QR"},
    "2-qadam: 6 raqamli kodni tasdiqlang": {"en": "Step 2: Confirm the 6-digit code", "ru": "Шаг 2: Подтвердите 6-значный код"},
    "QR ishlamayaptimi? Kodni qo'lda kiriting":
        {"en": "QR not working? Enter the code manually", "ru": "QR не работает? Введите код вручную"},
    "Yangi maxfiy kod yaratish": {"en": "Generate a new secret", "ru": "Создать новый секрет"},
    "2FA ni o'chirish":    {"en": "Disable 2FA",        "ru": "Отключить 2FA"},
    "Tavsiya etilgan ilovalar": {"en": "Recommended apps", "ru": "Рекомендуемые приложения"},

    # ---- Activity log ----
    "Faollik tarixi":      {"en": "Activity log",       "ru": "История активности"},
    "Tarixni ko'rish":     {"en": "View history",       "ru": "Посмотреть историю"},
    "Akkauntingizdagi oxirgi 100 ta harakat — kirish, akkaunt ulash, AI so'rovlari, eksportlar va boshqalar.":
        {"en": "Last 100 events on your account — sign-ins, account connects, AI requests, exports, and more.",
         "ru": "Последние 100 событий по аккаунту — входы, подключения, AI-запросы, экспорты и пр."},
    "Akkauntingiz bilan bog'liq oxirgi 100 ta hodisa — kirish, akkaunt ulash, AI so'rovlari, eksportlar.":
        {"en": "Last 100 events linked to your account — sign-ins, connects, AI requests, exports.",
         "ru": "Последние 100 событий аккаунта — входы, подключения, AI, экспорты."},
    "Hali faollik yo'q":   {"en": "No activity yet",    "ru": "Активности пока нет"},
    "Saytda harakat qila boshlaganingizda — kirish, akkaunt ulash, AI ishlatish — bu yerda yoziladi.":
        {"en": "Once you start using the site — signing in, connecting accounts, asking AI — it shows up here.",
         "ru": "Как только начнёте пользоваться — входить, подключать, спрашивать AI — события появятся тут."},

    # ---- Saved views ----
    "Saqlangan filterlar": {"en": "Saved views",        "ru": "Сохранённые фильтры"},
    "Joriy filterni saqlash": {"en": "Save current filter", "ru": "Сохранить текущий фильтр"},
    "Filterga nom bering:": {"en": "Name this filter:", "ru": "Назовите фильтр:"},
    "Olib tashlash":       {"en": "Remove",             "ru": "Удалить"},

    # ---- Onboarding tour update / dashboard #}
    "Bosh":                {"en": "Home",               "ru": "Главная"},
    "Postlar · Likes · Kommentlar · Ko'rishlar":
        {"en": "Posts · Likes · Comments · Views",
         "ru": "Посты · Лайки · Комментарии · Просмотры"},
    "30 kunlik faollik dinamikasi":
        {"en": "30-day activity dynamics", "ru": "Динамика активности за 30 дней"},
    "Engagement bo'yicha eng yaxshi 10 ta":
        {"en": "Top 10 by engagement", "ru": "Топ-10 по вовлечённости"},
    "Post turlari":        {"en": "Post types",         "ru": "Типы постов"},
    "Kontent ulushi":      {"en": "Content share",      "ru": "Доля контента"},
    "Jami views":          {"en": "Total views",        "ru": "Всего просмотров"},
    "Ko'rishlardan repostgacha bo'lgan zanjirning konversiyasi":
        {"en": "Conversion from views down to reshares",
         "ru": "Конверсия от просмотров до репостов"},

    # ---- Telegram connect flow ----
    "1 / 3 — telefon raqamingiz":
        {"en": "1 / 3 — your phone number", "ru": "1 / 3 — ваш номер телефона"},
    "3 / 3 — 2-bosqichli tasdiqlash paroli":
        {"en": "3 / 3 — two-step verification password", "ru": "3 / 3 — пароль двухэтапной проверки"},
    "Telefon raqami":      {"en": "Phone number",        "ru": "Номер телефона"},
    "Telegram 2FA paroli": {"en": "Telegram 2FA password","ru": "Пароль 2FA Telegram"},
    "Telegram cloud paroli":{"en":"Telegram cloud password","ru":"Облачный пароль Telegram"},
    "Telegram kanali tanlash":{"en":"Pick a Telegram channel","ru":"Выберите Telegram-канал"},
    "Telegram kodi":       {"en": "Telegram code",       "ru": "Код Telegram"},
    "Telegram'dan kelgan kod":{"en":"Code from Telegram","ru":"Код из Telegram"},
    "Telegram'ga kirish":  {"en": "Sign in to Telegram", "ru": "Войти в Telegram"},
    "Telegram'ga ulanish": {"en": "Connect Telegram",    "ru": "Подключить Telegram"},
    "Tasdiqlash kodi":     {"en": "Confirmation code",   "ru": "Код подтверждения"},
    "Cloud parolingiz":    {"en": "Your cloud password", "ru": "Ваш облачный пароль"},
    "Kod":                 {"en": "Code",                "ru": "Код"},
    "Kod yuborish":        {"en": "Send code",           "ru": "Отправить код"},
    "Kanal tanlash":       {"en": "Pick a channel",      "ru": "Выбрать канал"},
    "Boshqa raqam":        {"en": "Different number",    "ru": "Другой номер"},
    "Boshqa akkaunt":      {"en": "Different account",   "ru": "Другой аккаунт"},
    "Raqamni o'zgartirish":{"en": "Change number",       "ru": "Сменить номер"},
    "Hamma postlarni olish":{"en": "Fetch all posts",    "ru": "Получить все посты"},
    "Yuqoridagi limitni e'tiborsiz qoldirib, kanaldagi barcha mavjud postlarni yig'adi. Katta kanallarda bir necha daqiqa vaqt olishi mumkin.":
        {"en": "Ignores the limit above and pulls every available post from the channel. May take a few minutes for large channels.",
         "ru": "Игнорирует лимит выше и собирает все доступные посты канала. На крупных каналах может занять несколько минут."},
    "10 dan 5000 gacha. Kanaldan so'nggi shuncha postni — views, reaksiyalar, forwardlar bilan — tortib olamiz.":
        {"en": "From 10 to 5000. Pulls that many recent posts — with views, reactions, forwards.",
         "ru": "От 10 до 5000. Подтянем столько свежих постов — с просмотрами, реакциями, репостами."},
    "Bu Telegram'ning Settings → Privacy → Two-Step Verification bo'limida o'zingiz o'rnatgan parol. Saytda saqlanmaydi — faqat sessiya yaratish uchun ishlatiladi.":
        {"en": "This is the password you set in Telegram → Settings → Privacy → Two-Step Verification. It is never stored — used only to create the session.",
         "ru": "Это пароль, установленный вами в Telegram → Настройки → Конфиденциальность → Двухэтапная проверка. Не сохраняется — используется только для создания сессии."},
    "Kod Telegram ilovangizga (boshqa qurilmadagi sessiyaga) keladi — ba'zida SMS sifatida ham yuboriladi.":
        {"en": "The code arrives in your Telegram app (another device's session) — sometimes also via SMS.",
         "ru": "Код приходит в приложение Telegram (на другом устройстве) — иногда и SMS-ом."},
    "Sizning Telegram akkauntingizda kanal yoki guruh topilmadi.":
        {"en": "No channels or groups found in your Telegram account.",
         "ru": "В вашем аккаунте Telegram не найдено каналов или групп."},
    "Sizning Telegram sessiyangiz shifrlangan holda saqlanadi va faqat sizning kanal/guruh ma'lumotlaringizni o'qish uchun ishlatiladi. Saytdan istalgan vaqt o'chirib tashlashingiz mumkin.":
        {"en": "Your Telegram session is stored encrypted and used only to read data from your channels/groups. You can disconnect anytime.",
         "ru": "Ваша сессия Telegram хранится в зашифрованном виде и используется только для чтения данных ваших каналов/групп. Отключить можно в любой момент."},
    "Telegram public kanallar avtomatik tortib olinadi (sizning Telegram session'ingiz orqali). YouTube uchun handle saqlanadi, statistika keyinroq qo'lda yangilanadi.":
        {"en": "Public Telegram channels are pulled automatically (via your Telegram session). For YouTube the handle is saved; stats are refreshed manually later.",
         "ru": "Публичные Telegram-каналы тянутся автоматически (через вашу сессию Telegram). Для YouTube сохраняется handle; статистика обновляется вручную позже."},
    "Postlar avtomatik fonda yig'iladi (10-30 soniya).":
        {"en": "Posts are collected automatically in the background (10-30s).",
         "ru": "Посты собираются автоматически в фоне (10-30 сек)."},

    # ---- Engagement Predict ----
    "Engagement Bashorati": {"en": "Engagement Forecast", "ru": "Прогноз вовлечённости"},
    "Engagementga eng ko'p ta'sir qiluvchi xususiyatlar":
        {"en": "Features with the biggest impact on engagement",
         "ru": "Признаки с наибольшим влиянием на вовлечённость"},
    "Linear Regression sizning postlaringiz tarixini o'rganib, kelgusi post engagement'ini bashorat qiladi.":
        {"en": "Linear Regression learns your post history and forecasts the engagement of the next post.",
         "ru": "Линейная регрессия обучается на ваших постах и прогнозирует вовлечённость следующего."},
    "Caption uzunligi":    {"en": "Caption length",      "ru": "Длина подписи"},
    "Hashtag soni":        {"en": "Hashtag count",       "ru": "Кол-во хештегов"},
    "Hafta kuni":          {"en": "Day of week",         "ru": "День недели"},
    "Soat":                {"en": "Hour",                "ru": "Час"},
    "Media bormi?":        {"en": "Has media?",          "ru": "Есть медиа?"},
    "Post xususiyatlari":  {"en": "Post features",       "ru": "Признаки поста"},
    "Qanday post yozmoqchisiz?":
        {"en": "What kind of post will you write?",
         "ru": "Какой пост вы напишете?"},
    "Kutilgan natija":     {"en": "Expected result",     "ru": "Ожидаемый результат"},
    "ML model qancha aniq?":{"en": "How accurate is the ML model?", "ru": "Насколько точна ML-модель?"},
    "R² (model sifati) sizning ma'lumotingizga bog'liq. 100+ post bo'lsa odatda 0.4-0.7 oralig'ida — bashorat taxminiy, lekin trend to'g'ri.":
        {"en": "R² (model quality) depends on your data. With 100+ posts it usually lands in 0.4-0.7 — the prediction is approximate but the trend is right.",
         "ru": "R² (качество модели) зависит от данных. На 100+ постах обычно 0.4-0.7 — прогноз приблизительный, но тренд верный."},
    "Texnik tafsilot:":    {"en": "Technical detail:",   "ru": "Технические детали:"},
    "Model — sklearn.linear_model.LinearRegression. Target — log1p(likes). Inputlar: hafta kuni, soat, caption uzunligi, hashtag soni, media mavjudligi. Real-time, har so'rovda qayta o'qitadi (~50ms).":
        {"en": "Model — sklearn.linear_model.LinearRegression. Target — log1p(likes). Inputs: weekday, hour, caption length, hashtag count, has-media. Real-time, refits per request (~50ms).",
         "ru": "Модель — sklearn.linear_model.LinearRegression. Таргет — log1p(likes). Входы: день недели, час, длина подписи, количество хештегов, наличие медиа. Real-time, переобучается на каждый запрос (~50мс)."},
    "Chap tomondagi formani to'ldirib 'Bashorat qilish' tugmasini bosing.":
        {"en": "Fill out the form on the left and press 'Predict'.",
         "ru": "Заполните форму слева и нажмите 'Прогноз'."},
    "Maslahat:":           {"en": "Tip:",                "ru": "Совет:"},
    "Xato:":               {"en": "Error:",              "ru": "Ошибка:"},
    "Xavfsizlik:":         {"en": "Security:",           "ru": "Безопасность:"},
    "Tahlilda":            {"en": "Analyzing",           "ru": "Анализ"},
    "Eng yaxshi":          {"en": "Best",                "ru": "Лучший"},
    "Model:":              {"en": "Model:",              "ru": "Модель:"},
    "O'rganilgan postlar:":{"en": "Trained on posts:",   "ru": "Обучено на постах:"},
    "Model sifati (R²)":   {"en": "Model quality (R²)",  "ru": "Качество модели (R²)"},
    "O'rt. engagement":    {"en": "Avg. engagement",     "ru": "Сред. вовлечённость"},
    "O'rt. likes":         {"en": "Avg. likes",          "ru": "Сред. лайки"},
    "O'rtacha — bashorat taxminiy. Ko'proq post yiglinsa aniqlik oshadi.":
        {"en": "Moderate — predictions are approximate. Accuracy improves with more posts.",
         "ru": "Средний — прогноз приблизительный. С большим числом постов точность выше."},
    "Yuqori — model ma'lumotlaringizni yaxshi tushunadi.":
        {"en": "High — the model understands your data well.",
         "ru": "Высокий — модель хорошо понимает ваши данные."},
    "ta layk":             {"en": "likes",               "ru": "лайков"},
    "~{{ n }} layk kutiladi":{"en": "~{{ n }} likes expected", "ru": "~{{ n }} лайков ожидается"},
    "{{ day }} kuni soat {{ hr }}:00 da post chiqaring":
        {"en": "Post on {{ day }} at {{ hr }}:00",
         "ru": "Публикуйте в {{ day }} в {{ hr }}:00"},
    "{{ len }} belgi atrofida yozilgan postlaringiz o'rtacha {{ avg }}% engagement berdi — ushbu uzunlikda yozishga harakat qiling.":
        {"en": "Posts around {{ len }} characters got an average {{ avg }}% engagement — try this length.",
         "ru": "Посты около {{ len }} символов давали в среднем {{ avg }}% вовлечённости — старайтесь этой длины."},
    "{{ sz }} ta post o'rtacha engagement {{ eng }}%. Shu mavzudagi postlarni ko'paytirish maqsadga muvofiq.":
        {"en": "{{ sz }} posts averaged {{ eng }}% engagement. Producing more on this topic is a good move.",
         "ru": "{{ sz }} постов в среднем дали {{ eng }}% вовлечённости. Публикуйте больше на эту тему."},
    "~{{ cl }} belgili caption · {{ hc }} ta hashtag":
        {"en": "~{{ cl }}-character caption · {{ hc }} hashtags",
         "ru": "~{{ cl }} символов · {{ hc }} хештегов"},
    "faqat matn":          {"en": "text only",           "ru": "только текст"},
    "media (rasm/video) bilan":{"en": "with media (image/video)", "ru": "с медиа (фото/видео)"},
    "scikit-learn modeli engagement bashorat qiladi":
        {"en": "scikit-learn model forecasts engagement",
         "ru": "scikit-learn модель прогнозирует вовлечённость"},

    # ---- Correlation / clustering ----
    "Korrelyatsiya hisoblash uchun kommentli postlardan kamida 5 ta kerak.":
        {"en": "Need at least 5 posts with comments to compute correlation.",
         "ru": "Для расчёта корреляции нужно минимум 5 постов с комментариями."},
    "Kuchli pozitiv korrelyatsiya":{"en": "Strong positive correlation", "ru": "Сильная положительная корреляция"},
    "Kuchli salbiy korrelyatsiya": {"en": "Strong negative correlation", "ru": "Сильная отрицательная корреляция"},
    "O'rtacha pozitiv korrelyatsiya":{"en": "Moderate positive correlation","ru": "Умеренная положительная корреляция"},
    "Salbiy korrelyatsiya":  {"en": "Negative correlation",  "ru": "Отрицательная корреляция"},
    "X = pozitiv komment %, Y = engagement %":
        {"en": "X = positive comment %, Y = engagement %",
         "ru": "X = % положительных комментариев, Y = % вовлечённости"},
    "r = 1.0 mukammal pozitiv · r = 0 aloqa yo'q · r = -1.0 mukammal salbiy":
        {"en": "r = 1.0 perfect positive · r = 0 no correlation · r = -1.0 perfect negative",
         "ru": "r = 1.0 идеальная положительная · r = 0 нет связи · r = -1.0 идеальная отрицательная"},
    "ta post ishtirok etdi.":{"en": "posts contributed.",  "ru": "постов учтено."},
    "TfidfVectorizer (max_features=300, min_df=2, max_df=0.85) bilan postlar vektorlashtiriladi, KMeans (n_init='auto', random_state=42) klasterlaydi. Klaster nomi — markaz vektorining top-3 tokenidan olingan.":
        {"en": "Posts are vectorised with TfidfVectorizer (max_features=300, min_df=2, max_df=0.85) and clustered by KMeans (n_init='auto', random_state=42). Cluster names come from the centroid's top-3 tokens.",
         "ru": "Посты векторизуются TfidfVectorizer (max_features=300, min_df=2, max_df=0.85) и кластеризуются KMeans (n_init='auto', random_state=42). Название кластера — топ-3 токена центроида."},

    # ---- Compare / Competitors ----
    "2-3 akkauntni yonma-yon solishtirish":
        {"en": "Compare 2-3 accounts side by side",
         "ru": "Сравнить 2-3 аккаунта рядом"},
    "Sizning akkauntlaringiz va kuzatuvdagi raqobatchilar yonma-yon":
        {"en": "Your accounts and tracked competitors side by side",
         "ru": "Ваши аккаунты и отслеживаемые конкуренты рядом"},
    "Hali raqobatchi qo'shilmagan.":
        {"en": "No competitors added yet.",
         "ru": "Конкуренты ещё не добавлены."},
    "Eslatma — nima uchun kuzatasiz":
        {"en": "Note — why are you tracking",
         "ru": "Заметка — зачем отслеживаете"},
    "Public @username yoki kanal id":
        {"en": "Public @username or channel id",
         "ru": "Публичный @username или id канала"},
    "Qo'shish":            {"en": "Add",                 "ru": "Добавить"},

    # ---- Reports / Digest ----
    "Bir bosish bilan haftalik AI hisobot":
        {"en": "Weekly AI report at one click",
         "ru": "Еженедельный AI-отчёт в один клик"},
    "Bir bosish bilan AI sizning postlaringiz, kommentlaringiz va engagement'ingizni o'qib, qisqa va aniq haftalik tahlil yozadi (Markdown formatda).":
        {"en": "One click and AI reads your posts, comments and engagement to write a short, sharp weekly review (in Markdown).",
         "ru": "Один клик — и AI прочитает ваши посты, комментарии и вовлечённость и напишет короткий, чёткий еженедельный обзор (в Markdown)."},
    "OpenAI sizning real ma'lumotingiz asosida haftalik tahlil yozadi: nima yaxshi ishladi, nima yomon, keyingi hafta nima qilish kerak.":
        {"en": "OpenAI writes a weekly review from your real data: what worked, what didn't, what to do next week.",
         "ru": "OpenAI на основе ваших реальных данных пишет еженедельный обзор: что сработало, что нет, что делать на следующей неделе."},
    "AI hisobotlar nima uchun pulli?":
        {"en": "Why are AI reports paid?",
         "ru": "Почему AI-отчёты платные?"},
    "OpenAI API har so'rovga to'lov oladi (~$0.001 har so'rovga). Bizdа rate limit (6/soat, 20/soat) — token sarflashni cheklash uchun.":
        {"en": "The OpenAI API charges per request (~$0.001 each). We rate-limit (6/h, 20/h) to keep token spend bounded.",
         "ru": "OpenAI API берёт плату за запрос (~$0.001 каждый). У нас rate-limit (6/ч, 20/ч), чтобы ограничить расход токенов."},
    "Limit: 6 ta so'rov / soatda · ~3-5 soniya kutish":
        {"en": "Limit: 6 requests / hour · ~3-5 second wait",
         "ru": "Лимит: 6 запросов / час · ~3-5 сек ожидания"},
    "tezkor hisobot":      {"en": "instant report",      "ru": "мгновенный отчёт"},
    "AI sozlanmagan":      {"en": "AI not configured",   "ru": "AI не настроен"},
    "OPENAI_API_KEY env var sozlanishi kerak.":
        {"en": "OPENAI_API_KEY env var must be configured.",
         "ru": "Должна быть настроена переменная OPENAI_API_KEY."},

    # ---- Connect feature lists ----
    "30 kunlik trend, eng yaxshi vaqt heatmap, post turlari, hashtag":
        {"en": "30-day trend, best-time heatmap, post types, hashtags",
         "ru": "Тренд за 30 дней, тепловая карта времени, типы постов, хештеги"},
    "KPI'lar, faollik dinamikasi, top postlar, tavsiyalar":
        {"en": "KPIs, activity dynamics, top posts, recommendations",
         "ru": "KPI, динамика активности, топ-посты, рекомендации"},
    "Pozitiv/negativ kommentlar, mavzu × sentiment matritsa":
        {"en": "Positive/negative comments, topic × sentiment matrix",
         "ru": "Положительные/отрицательные комментарии, матрица темы × настроение"},
    "Akkauntni public link orqali ulashish":
        {"en": "Share an account via public link",
         "ru": "Поделиться аккаунтом через публичную ссылку"},
    "Real OAuth · API v5.131":{"en": "Real OAuth · API v5.131", "ru": "Real OAuth · API v5.131"},
    "Real OAuth · Data API v3":{"en":"Real OAuth · Data API v3","ru": "Real OAuth · Data API v3"},
    "Real OAuth · MTProto":  {"en": "Real OAuth · MTProto",  "ru": "Real OAuth · MTProto"},
    "Excel + PDF eksport":  {"en": "Excel + PDF export",   "ru": "Excel + PDF экспорт"},
    "Production: X API Basic tariffi ($100/oy). Hozir demo.":
        {"en": "Production: X API Basic plan ($100/mo). Demo for now.",
         "ru": "Прод: тариф X API Basic ($100/мес). Сейчас демо."},
    "Haqiqiy ma'lumot":     {"en": "Real data",            "ru": "Реальные данные"},
    "Aloqa kuchsiz":        {"en": "Weak correlation",     "ru": "Слабая корреляция"},

    # ---- Settings + misc ----
    "Telegram, YouTube va VK ma'lumotlaringizni real ulang; Instagram va X demo rejimda ko'ring. AI sentiment tahlil, real-time grafiklar, avtomatik tavsiyalar — bir necha bosishda.":
        {"en": "Connect real data from Telegram, YouTube and VK; see Instagram and X in demo mode. AI sentiment analysis, real-time charts, automatic recommendations — in just a few clicks.",
         "ru": "Подключите реальные данные Telegram, YouTube и VK; Instagram и X — в демо-режиме. AI-анализ настроений, графики в реальном времени, автоматические рекомендации — в пару кликов."},
    "Ayni paytda real ulashda: Telegram (MTProto), YouTube (Data API v3), VKontakte (API v5). Demo rejimda: Instagram (Business akkaunt + Meta App Review talab qiladi), X (Basic tariff $100/oy).":
        {"en": "Currently real: Telegram (MTProto), YouTube (Data API v3), VKontakte (API v5). Demo: Instagram (requires Business account + Meta App Review), X (Basic plan $100/mo).",
         "ru": "Сейчас по-настоящему подключены: Telegram (MTProto), YouTube (Data API v3), VKontakte (API v5). Демо: Instagram (нужен Business + Meta App Review), X (Basic $100/мес)."},
    "Ma'lumotim eksport qila olamanmi?":
        {"en": "Can I export my data?", "ru": "Могу ли я экспортировать свои данные?"},
    "Ma'lumotlarim qayerda saqlanadi?":
        {"en": "Where is my data stored?", "ru": "Где хранятся мои данные?"},
    "PostgreSQL bazada (Render). Sizning OAuth tokenlaringiz Fernet shifrlash bilan saqlanadi. Akkauntni o'chirsangiz hammasi cascade bilan o'chadi.":
        {"en": "In a PostgreSQL database (Render). Your OAuth tokens are stored Fernet-encrypted. Deleting your account cascades and removes everything.",
         "ru": "В базе PostgreSQL (Render). OAuth-токены хранятся с Fernet-шифрованием. При удалении аккаунта всё удаляется каскадно."},
    "Skriptingiz yoki ilovangizdan REST API'ga kirish uchun JWT token. Barcha so'rovlarda Authorization sarlavhasiga qo'shing.":
        {"en": "JWT token to access the REST API from your script or app. Add to the Authorization header on every request.",
         "ru": "JWT-токен для доступа к REST API из скрипта или приложения. Добавляйте в заголовок Authorization в каждом запросе."},
    "Yuqoridagi 'Korsatish' tugmasini bosing — token serverdan olinadi.":
        {"en": "Click the 'Show' button above — the token is fetched from the server.",
         "ru": "Нажмите кнопку 'Показать' выше — токен получится с сервера."},
    "Qaysi kanalni tahlil qilamiz?":
        {"en": "Which channel should we analyse?", "ru": "Какой канал анализируем?"},
    "Telegram'ingizda jami {{ total }} ta kanal/guruh.{% plural %}Telegram'ingizda jami {{ total }} ta kanal/guruh.":
        {"en": "{{ total }} channels/groups in your Telegram.{% plural %}{{ total }} channels/groups in your Telegram.",
         "ru": "Всего {{ total }} каналов/групп в Telegram.{% plural %}Всего {{ total }} каналов/групп в Telegram."},

    # ---- Misc tiny words ----
    "Ha":                 {"en": "Yes",                 "ru": "Да"},
    "Yoq":                {"en": "No",                  "ru": "Нет"},
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
