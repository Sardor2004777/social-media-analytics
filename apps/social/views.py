"""Connected-account management views."""
from __future__ import annotations

import logging
import random
from datetime import timedelta, timezone as dt_timezone

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.collectors.services.mock_generator import DemoDataGenerator
from apps.collectors.services.telegram import (
    TelegramCollector,
    TelegramNotConfigured,
    run_sync,
)
from apps.collectors.services.instagram import (
    InstagramCollector,
    InstagramNoBusinessAccount,
    InstagramNotConfigured,
)
from apps.collectors.services.youtube import (
    YouTubeCollector,
    YouTubeNotConfigured,
)
from apps.collectors.tasks import (
    sync_instagram_account,
    sync_telegram_account,
    sync_youtube_account,
)

from .models import ConnectedAccount, Platform, Post, PublicShareLink

logger = logging.getLogger(__name__)


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
        .prefetch_related("share_links")
        .order_by("platform")
    )
    accounts = list(qs)

    # Resolve each account's active share link from the prefetched rows so the
    # template can render a single "Share" toggle + copyable URL without extra
    # queries per row.
    for a in accounts:
        active = next((l for l in a.share_links.all() if l.is_active), None)
        a.active_share_link = active
        a.public_share_url = request.build_absolute_uri(
            reverse("social:public_share", kwargs={"token": active.token})
        ) if active else ""

    connected_platforms = {a.platform for a in accounts}
    available = []
    for code, meta in PLATFORM_META.items():
        # Real OAuth flow for platforms with configured credentials; everything
        # else (unconfigured Google-/Meta-backed platforms, X, Telegram without
        # MTProto session) falls through to the demo connect form.
        if code == Platform.YOUTUBE.value and YouTubeCollector.is_configured():
            connect_url = reverse("social:youtube_connect_start")
            real_mode = True
        elif code == Platform.INSTAGRAM.value and InstagramCollector.is_configured():
            connect_url = reverse("social:instagram_connect_start")
            real_mode = True
        else:
            connect_url = reverse("social:connect", kwargs={"platform": code})
            real_mode = (
                code == Platform.TELEGRAM.value and TelegramCollector.is_configured()
            )
        available.append({
            "code": code,
            **meta,
            "connected": code in connected_platforms,
            "connect_url": connect_url,
            "real_mode": real_mode,
        })

    return render(request, "dashboard/accounts.html", {
        "active_nav": "accounts",
        "accounts":  accounts,
        "available": available,
    })


@login_required
@require_POST
def account_refresh(request: HttpRequest, pk: int) -> HttpResponse:
    """Trigger an immediate re-sync of a real-mode account.

    Runs the platform collector synchronously (via ``.apply()``) so the user
    gets updated KPIs on the very next page load instead of waiting for the
    periodic Celery Beat tick.
    """
    account = get_object_or_404(ConnectedAccount, pk=pk, user=request.user)
    if account.is_demo:
        messages.info(request, "Demo akkauntni yangilab bo'lmaydi.")
        return redirect("social:accounts")

    try:
        if account.platform == Platform.YOUTUBE:
            result = sync_youtube_account.apply(args=[account.id]).get()
            messages.success(
                request,
                f"@{account.handle} yangilandi — +{result.get('created', 0)} yangi video, "
                f"{result.get('updated', 0)} yangilandi, "
                f"{result.get('follower_count', 0):,} obunachi.",
            )
        elif account.platform == Platform.INSTAGRAM:
            result = sync_instagram_account.apply(args=[account.id]).get()
            messages.success(
                request,
                f"@{account.handle} yangilandi — +{result.get('created', 0)} yangi post, "
                f"{result.get('updated', 0)} yangilandi, "
                f"{result.get('follower_count', 0):,} obunachi.",
            )
        elif account.platform == Platform.TELEGRAM:
            result = sync_telegram_account.apply(args=[account.id]).get()
            messages.success(
                request,
                f"@{account.handle} yangilandi — +{result.get('created', 0)} yangi post, "
                f"{result.get('updated', 0)} yangilandi.",
            )
        else:
            messages.info(
                request,
                f"{account.get_platform_display()} uchun avtomatik yangilash hali mavjud emas.",
            )
    except Exception as e:
        logger.warning("Refresh failed for account %s: %s", account.id, e)
        messages.error(request, f"Yangilash muvaffaqiyatsiz: {e}")
    return redirect("social:accounts")


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
        max_value=5000,
        initial=60,
        widget=forms.NumberInput(attrs={"class": "field-input !w-32"}),
        help_text="Demo uchun necha ta post seed qilinsin",
    )
    # Real-mode only: pull every available post instead of the slider value.
    # Backed by Telethon's iter_messages(limit=None); takes longer for big channels.
    fetch_all = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            "class": "h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500",
        }),
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

            # Real-mode: Telegram MTProto is the only backend implemented so far.
            # All other platforms (and un-configured Telegram) fall through to
            # the demo seeder in the ``else`` branch below.
            if (
                platform == Platform.TELEGRAM.value
                and TelegramCollector.is_configured()
            ):
                try:
                    info = run_sync(
                        TelegramCollector().fetch_channel_info(handle)
                    )
                except TelegramNotConfigured as e:
                    form.add_error(None, str(e))
                except Exception as e:
                    logger.warning("Telegram connect failed for @%s: %s", handle, e)
                    form.add_error("handle", f"Kanal ochilmadi: {e}")
                else:
                    account, _ = ConnectedAccount.objects.get_or_create(
                        user=request.user,
                        platform=platform,
                        external_id=info.external_id,
                        defaults={
                            "handle": info.handle,
                            "display_name": info.display_name,
                            "follower_count": info.follower_count,
                            "is_demo": False,
                        },
                    )
                    # ``post_limit=0`` is our sentinel for "fetch every post"
                    # (Telethon iter_messages will paginate until exhausted).
                    effective_limit = 0 if form.cleaned_data.get("fetch_all") else posts
                    sync_telegram_account.delay(account.id, post_limit=effective_limit)
                    extra = (
                        " Hamma postlar yig'ilmoqda — katta kanal uchun "
                        "bir necha daqiqa kutish mumkin."
                        if effective_limit == 0 else
                        " Postlar fonda yig'ilmoqda."
                    )
                    messages.success(
                        request,
                        f"@{info.handle} ({platform_meta['label']}) ulandi — "
                        f"{info.follower_count:,} obunachi.{extra}",
                    )
                    return redirect("social:accounts")
            else:
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
        "real_mode": (
            platform == Platform.TELEGRAM.value
            and TelegramCollector.is_configured()
        ),
    })


@login_required
@require_POST
def toggle_share_link(request: HttpRequest, pk: int) -> HttpResponse:
    """Create a public share link for an account, or revoke the active one.

    Ownership is enforced — users may only toggle links on their own accounts.
    """
    account = get_object_or_404(ConnectedAccount, pk=pk, user=request.user)
    active = account.share_links.filter(is_active=True).first()
    if active:
        active.is_active = False
        active.save(update_fields=["is_active", "updated_at"])
        messages.success(
            request,
            f"@{account.handle} uchun public ulashish bekor qilindi.",
        )
    else:
        link = PublicShareLink.create_for(account)
        share_url = request.build_absolute_uri(
            reverse("social:public_share", kwargs={"token": link.token})
        )
        messages.success(request, f"Public link yaratildi: {share_url}")
    return redirect("social:accounts")


# ---------------------------------------------------------------- YouTube OAuth


def _youtube_redirect_uri(request: HttpRequest) -> str:
    """Absolute URI of the YouTube OAuth callback, as seen from outside.

    Must match exactly what's registered in Google Cloud Console →
    OAuth client → Authorized redirect URIs.
    """
    return request.build_absolute_uri(reverse("social:youtube_connect_callback"))


@login_required
def youtube_connect_start(request: HttpRequest) -> HttpResponse:
    """Kick off the Google OAuth flow that grants youtube.readonly."""
    import os
    import secrets as _secrets

    # google-auth-oauthlib refuses http:// redirect_uri by default; allow it in dev.
    if settings.DEBUG:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    # Google silently adds the profile scope + reorders the list on return —
    # oauthlib otherwise raises "Scope has changed". Relaxing is standard practice.
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

    if not YouTubeCollector.is_configured():
        messages.error(
            request,
            "YouTube integratsiyasi sozlanmagan — .env faylga "
            "YOUTUBE_OAUTH_CLIENT_ID va YOUTUBE_OAUTH_SECRET qo'shing.",
        )
        return redirect("social:accounts")

    state = _secrets.token_urlsafe(24)
    redirect_uri = _youtube_redirect_uri(request)
    try:
        auth_url, code_verifier = YouTubeCollector.build_auth_url(redirect_uri, state)
    except YouTubeNotConfigured as e:
        messages.error(request, str(e))
        return redirect("social:accounts")
    # Persist state + PKCE verifier to session — both are required on callback.
    request.session["youtube_oauth_state"] = state
    request.session["youtube_oauth_code_verifier"] = code_verifier
    return redirect(auth_url)


@login_required
def youtube_connect_callback(request: HttpRequest) -> HttpResponse:
    """Handle Google's redirect back: exchange code → tokens → ConnectedAccount."""
    import os

    if settings.DEBUG:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

    err = request.GET.get("error")
    if err:
        messages.error(request, f"YouTube ulash bekor qilindi: {err}")
        return redirect("social:accounts")

    code = request.GET.get("code")
    state = request.GET.get("state")
    expected_state = request.session.pop("youtube_oauth_state", None)
    if not code or not state or state != expected_state:
        messages.error(request, "YouTube ulash: noto'g'ri yoki eskirgan so'rov.")
        return redirect("social:accounts")

    redirect_uri = _youtube_redirect_uri(request)
    code_verifier = request.session.pop("youtube_oauth_code_verifier", "")
    try:
        creds = YouTubeCollector.exchange_code(code, redirect_uri, code_verifier)
        info = YouTubeCollector.fetch_mine_channel(
            access_token=creds.token,
            refresh_token=creds.refresh_token or "",
        )
    except YouTubeNotConfigured as e:
        messages.error(request, str(e))
        return redirect("social:accounts")
    except Exception as e:
        logger.warning("YouTube connect failed: %s", e)
        messages.error(request, f"YouTube ulash muvaffaqiyatsiz: {e}")
        return redirect("social:accounts")

    account, _ = ConnectedAccount.objects.update_or_create(
        platform=Platform.YOUTUBE,
        external_id=info.external_id,
        defaults={
            "user":           request.user,
            "handle":         info.handle,
            "display_name":   info.display_name,
            "avatar_url":     info.avatar_url,
            "follower_count": info.follower_count,
            "access_token":   creds.token or "",
            "refresh_token":  creds.refresh_token or "",
            "token_expires_at": creds.expiry.replace(tzinfo=dt_timezone.utc) if creds.expiry else None,
            "scopes":         " ".join(creds.scopes or []),
            "is_demo":        False,
        },
    )
    sync_youtube_account.delay(account.id)
    messages.success(
        request,
        f"YouTube kanali @{info.handle} ulandi — {info.follower_count:,} obunachi. "
        f"Videolar fonda yig'ilmoqda.",
    )
    return redirect("social:accounts")


# --------------------------------------------------------------- Instagram OAuth


def _instagram_redirect_uri(request: HttpRequest) -> str:
    """Absolute URI of the Instagram OAuth callback — must match exactly
    what's set in Meta App Dashboard → Facebook Login → Valid OAuth Redirect URIs."""
    return request.build_absolute_uri(reverse("social:instagram_connect_callback"))


@login_required
def instagram_connect_start(request: HttpRequest) -> HttpResponse:
    """Kick off the Meta Graph API OAuth flow (Instagram Business)."""
    import secrets as _secrets

    if not InstagramCollector.is_configured():
        messages.error(
            request,
            "Instagram integratsiyasi sozlanmagan — .env faylga "
            "META_APP_ID va META_APP_SECRET qo'shing.",
        )
        return redirect("social:accounts")

    state = _secrets.token_urlsafe(24)
    request.session["instagram_oauth_state"] = state
    redirect_uri = _instagram_redirect_uri(request)
    try:
        auth_url = InstagramCollector.build_auth_url(redirect_uri, state)
    except InstagramNotConfigured as e:
        messages.error(request, str(e))
        return redirect("social:accounts")
    return redirect(auth_url)


@login_required
def instagram_connect_callback(request: HttpRequest) -> HttpResponse:
    """Handle Meta's redirect: code → long-lived token → IG Business acct."""
    err = request.GET.get("error_description") or request.GET.get("error")
    if err:
        messages.error(request, f"Instagram ulash bekor qilindi: {err}")
        return redirect("social:accounts")

    code = request.GET.get("code")
    state = request.GET.get("state")
    expected_state = request.session.pop("instagram_oauth_state", None)
    if not code or not state or state != expected_state:
        messages.error(request, "Instagram ulash: noto'g'ri yoki eskirgan so'rov.")
        return redirect("social:accounts")

    redirect_uri = _instagram_redirect_uri(request)
    try:
        access_token, expires_in = InstagramCollector.exchange_code(code, redirect_uri)
        ig_user_id, page_token = InstagramCollector.find_ig_business_account(access_token)
        info = InstagramCollector.fetch_account_info(ig_user_id, page_token)
    except InstagramNotConfigured as e:
        messages.error(request, str(e))
        return redirect("social:accounts")
    except InstagramNoBusinessAccount as e:
        messages.error(request, str(e))
        return redirect("social:accounts")
    except Exception as e:
        logger.warning("Instagram connect failed: %s", e)
        messages.error(request, f"Instagram ulash muvaffaqiyatsiz: {e}")
        return redirect("social:accounts")

    # Page token is what we need for all downstream IG calls, not the user token.
    expires_at = timezone.now() + timedelta(seconds=expires_in)
    account, _ = ConnectedAccount.objects.update_or_create(
        platform=Platform.INSTAGRAM,
        external_id=info.external_id,
        defaults={
            "user":             request.user,
            "handle":           info.handle,
            "display_name":     info.display_name,
            "avatar_url":       info.avatar_url,
            "follower_count":   info.follower_count,
            "access_token":     page_token,    # store the Page token
            "refresh_token":    "",            # Meta doesn't issue refresh tokens
            "token_expires_at": expires_at,
            "scopes":           ",".join(["instagram_basic", "pages_show_list"]),
            "is_demo":          False,
        },
    )
    sync_instagram_account.delay(account.id)
    messages.success(
        request,
        f"Instagram @{info.handle} ulandi — {info.follower_count:,} obunachi. "
        f"Postlar fonda yig'ilmoqda.",
    )
    return redirect("social:accounts")


def public_share(request: HttpRequest, token: str) -> HttpResponse:
    """Read-only public dashboard snapshot for a shared account — no auth."""
    link = get_object_or_404(PublicShareLink, token=token, is_active=True)
    account = link.account
    now = timezone.now()

    posts_qs = Post.objects.filter(account=account)

    window_days = 30
    start = now - timedelta(days=window_days - 1)
    buckets = [0] * window_days
    for p in posts_qs.filter(published_at__gte=start).values("published_at", "likes"):
        idx = (p["published_at"].date() - start.date()).days
        if 0 <= idx < window_days:
            buckets[idx] += p["likes"]
    labels = [(start + timedelta(days=i)).strftime("%d %b") for i in range(window_days)]

    agg = posts_qs.aggregate(
        total_likes=Sum("likes"),
        total_views=Sum("views"),
        total_comments=Sum("comments_count"),
        avg_eng=Avg("engagement_rate"),
    )

    top_posts = [
        {
            "caption":  (p.caption or "—").strip()[:140],
            "likes":    p.likes,
            "views":    p.views,
            "comments": p.comments_count,
            "when":     p.published_at,
            "url":      p.url,
        }
        for p in posts_qs.order_by("-likes")[:10]
    ]

    return render(request, "dashboard/public_share.html", {
        "account": account,
        "kpis": {
            "followers":  account.follower_count,
            "posts":      posts_qs.count(),
            "likes":      agg["total_likes"] or 0,
            "views":      agg["total_views"] or 0,
            "comments":   agg["total_comments"] or 0,
            "engagement": round((agg["avg_eng"] or 0) * 100, 2),
        },
        "chart": {"labels": labels, "series": buckets},
        "top_posts": top_posts,
    })
