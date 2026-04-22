"""Outbound notification channels for ``Alert`` rows.

Two transports are supported:

- ``telegram`` — Telegram Bot API ``sendMessage`` (token from settings)
- ``email``    — Django mail backend (uses the project's SMTP config)

The module is deliberately thin: no retry loops or batching. Celery's
``autoretry_for`` on the calling task handles transient failures.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail

from apps.analytics.models import (
    Alert,
    AnomalyDirection,
    AnomalySeverity,
    NotificationChannel,
    NotificationPref,
)

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

_SEVERITY_EMOJI = {
    AnomalySeverity.INFO:     "ℹ️",
    AnomalySeverity.WARNING:  "⚠️",
    AnomalySeverity.CRITICAL: "🚨",
}


def _format_telegram(alert: Alert) -> str:
    emoji = _SEVERITY_EMOJI.get(alert.severity, "•")
    arrow = "📈" if alert.direction == AnomalyDirection.SPIKE else "📉"
    return (
        f"{emoji} <b>Anomaliya aniqlandi</b>\n"
        f"{arrow} {alert.message}\n\n"
        f"<b>Akkaunt:</b> @{alert.account.handle} ({alert.account.get_platform_display()})\n"
        f"<b>Kun:</b> {alert.detected_for:%d.%m.%Y}\n"
        f"<b>Qiymat:</b> {alert.value:.3f} (o'rtacha {alert.baseline:.3f})\n"
        f"<b>z-score:</b> {alert.z_score:+.2f}"
    )


def _format_email(alert: Alert) -> tuple[str, str]:
    subject = f"[{alert.get_severity_display()}] {alert.message}"
    body = (
        f"{alert.message}\n\n"
        f"Akkaunt:  @{alert.account.handle} ({alert.account.get_platform_display()})\n"
        f"Kun:      {alert.detected_for:%d.%m.%Y}\n"
        f"Qiymat:   {alert.value:.3f} (o'rtacha {alert.baseline:.3f})\n"
        f"z-score:  {alert.z_score:+.2f}\n"
    )
    return subject, body


def send_telegram(chat_id: str, text: str) -> bool:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured; skipping send")
        return False
    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={
                "chat_id":    chat_id,
                "text":       text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error("Telegram sendMessage failed for %s: %s", chat_id, exc)
        return False


def dispatch(alert: Alert) -> dict:
    """Route ``alert`` to the owning user's preferred channel if eligible."""
    user = alert.account.user
    try:
        pref: NotificationPref = user.notification_pref
    except NotificationPref.DoesNotExist:
        return {"delivered": False, "reason": "no_pref"}

    if not pref.accepts(alert):
        return {"delivered": False, "reason": "filtered"}

    if pref.channel == NotificationChannel.TELEGRAM:
        ok = send_telegram(pref.telegram_chat_id, _format_telegram(alert))
        return {"delivered": ok, "channel": "telegram"}

    if pref.channel == NotificationChannel.EMAIL:
        subject, body = _format_email(alert)
        try:
            send_mail(
                subject,
                body,
                getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                [user.email],
                fail_silently=False,
            )
            return {"delivered": True, "channel": "email"}
        except Exception as exc:
            logger.error("Email alert delivery failed for %s: %s", user.email, exc)
            return {"delivered": False, "reason": "smtp_error"}

    return {"delivered": False, "reason": "unknown_channel"}
