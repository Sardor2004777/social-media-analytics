"""Connected-account management views."""
from __future__ import annotations

import random

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import redirect, render

from apps.collectors.services.mock_generator import DemoDataGenerator

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
    return redirect("social:accounts")


class ConnectForm(forms.Form):
    """Minimal 'connect' form for demo mode — just a handle + post volume slider.

    Real OAuth-backed integrations (Instagram Graph, Telegram Bot, YouTube v3,
    X v2) live at the same URL later; for the diploma demo we seed a realistic
    ConnectedAccount with matching posts/comments/sentiment.
    """

    handle = forms.CharField(
        max_length=128,
        widget=forms.TextInput(attrs={
            "class": "field-input",
            "placeholder": "@your_handle",
            "autocomplete": "off",
        }),
    )
    posts = forms.IntegerField(
        min_value=10,
        max_value=300,
        initial=60,
        widget=forms.NumberInput(attrs={"class": "field-input !w-32"}),
        help_text="Demo uchun necha ta post seed qilinsin",
    )

    def clean_handle(self) -> str:
        v = self.cleaned_data["handle"].strip().lstrip("@")
        if not v:
            raise forms.ValidationError("Handle bo'sh bo'lmasligi kerak.")
        if " " in v:
            raise forms.ValidationError("Handle ichida bo'sh joy bo'lmaydi.")
        return v


@login_required
def account_connect(request: HttpRequest, platform: str) -> HttpResponse:
    """Add a ConnectedAccount for the given platform.

    Demo mode: takes a handle + post count and synthesises realistic data on
    the fly. Safe to call repeatedly — each invocation creates a new account
    (different external_id), so the user can compare multiple handles side
    by side on the dashboard.
    """
    if platform not in {p.value for p in Platform}:
        raise Http404("Unknown platform")
    platform_meta = PLATFORM_META[platform]

    if request.method == "POST":
        form = ConnectForm(request.POST)
        if form.is_valid():
            handle = form.cleaned_data["handle"]
            posts = form.cleaned_data["posts"]

            gen = DemoDataGenerator(seed=random.randint(1, 10**6))
            # seed() always creates the full 4-platform set — we only want
            # the single requested platform; run it with a one-element tuple
            # and a per-user-unique handle embedded via the generator's rng.
            stats = gen.seed(
                request.user,
                platforms=(platform,),
                posts_per_platform=posts,
                comments_per_post_range=(3, 14),
                days_back=120,
                analyze_sentiment=True,
                replace=False,
            )

            # The generator picks a random handle from its pool — rewrite the
            # freshly-inserted account with the user's chosen handle so the
            # dashboard reflects what they typed.
            latest = (
                ConnectedAccount.objects.filter(user=request.user, platform=platform)
                .order_by("-id").first()
            )
            if latest:
                latest.handle = handle
                latest.display_name = handle.replace("_", " ").replace(".", " ").title()
                latest.save(update_fields=["handle", "display_name"])

            messages.success(
                request,
                f"@{handle} ({platform_meta['label']}) ulandi — "
                f"{stats.posts} post, {stats.comments} komment.",
            )
            return redirect("social:accounts")
    else:
        form = ConnectForm()

    return render(request, "dashboard/account_connect.html", {
        "active_nav": "accounts",
        "form": form,
        "platform_code": platform,
        "platform": platform_meta,
    })
