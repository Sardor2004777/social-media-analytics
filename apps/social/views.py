"""Connected-account management views."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import ConnectedAccount, Platform


PLATFORM_META = {
    Platform.INSTAGRAM: {
        "label": "Instagram",
        "tint":  "from-fuchsia-500 to-orange-400",
        "icon":  "IG",
        "desc":  "Instagram Business API orqali postlar, reels va kommentlarni tahlil qiling.",
    },
    Platform.TELEGRAM: {
        "label": "Telegram",
        "tint":  "from-sky-500 to-blue-600",
        "icon":  "TG",
        "desc":  "Kanal yoki guruh statistikasi — views, forwards va reaksiyalar.",
    },
    Platform.YOUTUBE: {
        "label": "YouTube",
        "tint":  "from-red-500 to-rose-600",
        "icon":  "YT",
        "desc":  "Videolar, watch time, kommentlar va obunachilarning o'sishi.",
    },
    Platform.X: {
        "label": "X (Twitter)",
        "tint":  "from-slate-800 to-slate-900",
        "icon":  "X",
        "desc":  "Tweet impressions, retweetlar va followers dinamikasi.",
    },
}


@login_required
def accounts_list(request: HttpRequest) -> HttpResponse:
    """Show every connected account for the current user + CTAs for new connections."""
    qs = (
        ConnectedAccount.objects.filter(user=request.user)
        .annotate(
            posts_total=Count("posts"),
            likes_total=Sum("posts__likes"),
            avg_eng=Avg("posts__engagement_rate"),
        )
        .order_by("platform")
    )
    accounts = list(qs)

    connected_platforms = {a.platform for a in accounts}
    available = [
        {"code": code, **meta, "connected": code in connected_platforms}
        for code, meta in PLATFORM_META.items()
    ]

    return render(request, "dashboard/accounts.html", {
        "active_nav": "accounts",
        "accounts":  accounts,
        "available": available,
    })


@login_required
def account_disconnect(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a single connected account (demo accounts included)."""
    if request.method != "POST":
        return render(request, "405.html", status=405)
    acct = ConnectedAccount.objects.filter(user=request.user, pk=pk).first()
    if acct:
        label = f"@{acct.handle} ({acct.get_platform_display()})"
        acct.delete()
        messages.success(request, f"{label} o'chirildi.")
    else:
        messages.error(request, "Akkaunt topilmadi.")
    from django.shortcuts import redirect
    return redirect("social:accounts")
