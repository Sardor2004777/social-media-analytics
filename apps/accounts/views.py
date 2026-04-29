"""Profile / settings views."""
from __future__ import annotations

import json
from datetime import datetime

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

User = get_user_model()


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "field-input", "placeholder": "Ism"}),
            "last_name":  forms.TextInput(attrs={"class": "field-input", "placeholder": "Familiya"}),
            "email":      forms.EmailInput(attrs={"class": "field-input"}),
        }


@login_required
def settings_page(request: HttpRequest) -> HttpResponse:
    """Profile form + links to password change / data export."""
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil yangilandi.")
            return redirect("accounts:settings")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "dashboard/settings.html", {
        "active_nav": "settings",
        "form": form,
    })


@login_required
def export_my_data(request: HttpRequest) -> HttpResponse:
    """GDPR: return the current user's data as a JSON download.

    Includes profile, connected accounts, posts + comments + sentiment —
    everything the platform stores about this user. Streamed as an
    attachment so the user can archive it locally.
    """
    user = request.user

    from apps.analytics.models import SentimentResult
    from apps.collectors.models import Comment
    from apps.social.models import ConnectedAccount, Post

    accounts = []
    for a in ConnectedAccount.objects.filter(user=user):
        posts = []
        for p in a.posts.all():
            comments = []
            for c in p.comments.all().select_related("sentiment"):
                sent = getattr(c, "sentiment", None)
                comments.append({
                    "external_id": c.external_id,
                    "author_handle": c.author_handle,
                    "body": c.body,
                    "language": c.language,
                    "likes": c.likes,
                    "published_at": c.published_at.isoformat(),
                    "sentiment": {
                        "label": sent.label, "score": sent.score, "model": sent.model_name,
                    } if sent else None,
                })
            posts.append({
                "external_id": p.external_id,
                "post_type": p.post_type,
                "caption": p.caption,
                "url": p.url,
                "published_at": p.published_at.isoformat(),
                "metrics": {
                    "views": p.views, "likes": p.likes,
                    "comments_count": p.comments_count, "shares": p.shares,
                    "engagement_rate": p.engagement_rate,
                },
                "comments": comments,
            })
        accounts.append({
            "platform": a.platform,
            "handle": a.handle,
            "display_name": a.display_name,
            "follower_count": a.follower_count,
            "following_count": a.following_count,
            "is_demo": a.is_demo,
            "connected_at": a.created_at.isoformat(),
            "posts": posts,
        })

    payload = {
        "export_version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "connected_accounts": accounts,
    }

    resp = JsonResponse(payload, json_dumps_params={"ensure_ascii": False, "indent": 2})
    filename = f"social-analytics-export-{user.id}-{datetime.utcnow():%Y%m%d-%H%M}.json"
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@login_required
def delete_account(request: HttpRequest) -> HttpResponse:
    """Permanently delete the user's account and every cascaded row.

    Requires the user to type their email on a confirmation form; anything
    else is a no-op with a warning.
    """
    if request.method == "POST":
        typed = (request.POST.get("confirm_email") or "").strip().lower()
        if typed != (request.user.email or "").lower():
            messages.error(
                request,
                "Tasdiqlash uchun email manzilingizni aniq kiriting.",
            )
            return redirect("accounts:delete_account")

        user = request.user
        email = user.email
        logout(request)
        user.delete()
        messages.success(request, f"Akkaunt {email} o'chirildi. Xayr!")
        return redirect("dashboard:home")

    return render(request, "dashboard/delete_account.html", {
        "active_nav": "settings",
    })


@login_required
def activity_log_view(request: HttpRequest) -> HttpResponse:
    """Show the current user's activity log (last 100 events).

    Per-user audit trail — login, account connect, sync, AI request,
    export, 2FA changes. Used to give the user transparency into "what
    happened on my account".
    """
    from apps.core.models import ActivityLog

    rows = (
        ActivityLog.objects
        .filter(user=request.user)
        .order_by("-created_at")[:100]
    )
    return render(request, "dashboard/activity_log.html", {
        "active_nav": "settings",
        "rows":       rows,
    })


@login_required
def two_factor_setup(request: HttpRequest) -> HttpResponse:
    """Enable / disable / verify TOTP-based two-factor auth.

    GET   — shows current state. If 2FA is OFF and no secret exists yet,
            generates one and stashes it on the user (still disabled).
            Renders the otpauth URI for client-side QR rendering.
    POST  — branches on ``action``:
              * ``enable`` + ``code`` → verify the 6-digit code; on success
                flip ``totp_enabled`` to True.
              * ``disable``           → clear the secret + flag.
              * ``regenerate``        → ditch the existing secret, create a
                fresh one (still disabled until verified).
    """
    from apps.accounts.totp import new_secret, provisioning_uri, verify

    user = request.user
    error: str | None = None
    notice: str | None = None

    if request.method == "POST":
        from apps.core.models import log_activity
        action = (request.POST.get("action") or "").strip()
        if action == "disable":
            user.totp_enabled = False
            user.totp_secret  = ""
            user.save(update_fields=["totp_enabled", "totp_secret"])
            log_activity(user, "2fa", "2FA disabled", request=request)
            notice = "2FA o'chirildi."
        elif action == "regenerate":
            user.totp_enabled = False
            user.totp_secret  = new_secret()
            user.save(update_fields=["totp_enabled", "totp_secret"])
            log_activity(user, "2fa", "2FA secret regenerated", request=request)
            notice = "Yangi maxfiy kod yaratildi. Qayta scan qiling va kodni tasdiqlang."
        elif action == "enable":
            code = (request.POST.get("code") or "").strip()
            if not user.totp_secret:
                error = "Avval QR kodni Authenticatorga qo'shing, keyin tasdiqlang."
            elif verify(user.totp_secret, code):
                user.totp_enabled = True
                user.save(update_fields=["totp_enabled"])
                log_activity(user, "2fa", "2FA enabled", request=request)
                notice = "2FA yoqildi! Endi har safar kirishda kod so'raladi."
            else:
                error = "Kod noto'g'ri yoki muddati o'tgan. Qayta urinib ko'ring."
        else:
            error = "Noma'lum amal."

    # Make sure a secret exists when 2FA is OFF, so the page can show a QR
    # ready for the user to scan without an extra round-trip.
    if not user.totp_enabled and not user.totp_secret:
        user.totp_secret = new_secret()
        user.save(update_fields=["totp_secret"])

    uri = ""
    if user.totp_secret:
        try:
            uri = provisioning_uri(user.totp_secret, user.email or user.username)
        except Exception:
            uri = ""

    return render(request, "dashboard/two_factor.html", {
        "active_nav":  "settings",
        "totp_enabled": user.totp_enabled,
        "totp_secret":  user.totp_secret,
        "totp_uri":     uri,
        "error":        error,
        "notice":       notice,
    })
