"""One-time: generate a Telethon StringSession for real-mode Telegram collection.

Run this once per environment, then paste the printed string into
``TELEGRAM_SESSION_STRING`` in ``.env``. The session is bound to the Telegram
account that answers the phone/OTP prompt — treat it like a password.

Usage::

    python manage.py telegram_generate_session
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from telethon.sessions import StringSession
from telethon.sync import TelegramClient


class Command(BaseCommand):
    help = "Interactively generate a Telethon StringSession for TELEGRAM_SESSION_STRING."

    def handle(self, *args, **options):
        api_id = settings.TELEGRAM_API_ID
        api_hash = settings.TELEGRAM_API_HASH
        if not (api_id and api_hash):
            raise CommandError(
                "TELEGRAM_API_ID va TELEGRAM_API_HASH .env fayliga yozilmagan. "
                "https://my.telegram.org/apps dan olib, .env ga kiriting."
            )

        self.stdout.write("Telegram login: telefon raqamingiz va SMS-kod so'raladi.\n")

        with TelegramClient(StringSession(), int(api_id), str(api_hash)) as client:
            session_string = client.session.save()

        bar = "=" * 72
        self.stdout.write("\n" + self.style.SUCCESS(bar))
        self.stdout.write("SESSION STRING — .env dagi TELEGRAM_SESSION_STRING ga yozing:")
        self.stdout.write(self.style.SUCCESS(bar))
        self.stdout.write(session_string)
        self.stdout.write(self.style.SUCCESS(bar) + "\n")
        self.stdout.write(self.style.WARNING(
            "Ogohlantirish: ushbu string Telegram akkauntingizga to'liq kirish "
            "beradi — public joyga qo'ymang, git'ga commit qilmang."
        ))
