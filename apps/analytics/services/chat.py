"""LLM-powered Q&A over the user's analytics data (via OpenAI).

The public API is :func:`ask` — it takes a user + a question, pulls a 30-day
analytics snapshot for all their connected accounts, and sends the snapshot
plus the question to OpenAI's Chat Completions API with a system prompt that
forbids invented numbers. Returns a :class:`ChatResponse` with the answer text
and token usage stats.

The ``openai`` SDK is imported lazily so Django startup doesn't require it —
that way the feature can be shipped without forcing every deploy to install
the package upfront.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from apps.analytics.models import SentimentLabel, SentimentResult
from apps.social.models import ConnectedAccount, Post

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a concise analytics assistant for a social-media
analytics platform. The user owns the accounts below and asks questions about
their performance. Rules:

- Answer strictly from the provided data; never invent numbers or accounts.
- Be direct: 2-4 short paragraphs, use bullet points for lists.
- When citing a number, say the time window ("last 30 days").
- If a question can't be answered with the data available, say so and
  suggest what data would help.
- Respond in the same language as the user's question
  (Uzbek / Russian / English).
"""


class ChatNotConfigured(RuntimeError):
    """Raised when OPENAI_API_KEY is missing or the SDK is not installed."""


@dataclass(frozen=True)
class ChatResponse:
    answer: str
    model: str
    tokens_in: int
    tokens_out: int


def is_configured() -> bool:
    return bool(getattr(settings, "OPENAI_API_KEY", ""))


def _build_user_context(user) -> str:
    """Serialize the user's analytics state as a compact markdown summary.

    The result is injected into the system prompt, so keep it tight (~500
    tokens) — every extra token costs money on every call.
    """
    now = timezone.now()
    window_start = now - timedelta(days=30)

    accounts = list(
        ConnectedAccount.objects.filter(user=user).order_by("platform")
    )
    if not accounts:
        return "The user has no connected accounts yet — no data to reason over."

    lines = ["## Connected accounts (last 30 days)", ""]

    for acct in accounts:
        posts_qs = Post.objects.filter(
            account=acct, published_at__gte=window_start
        )
        agg = posts_qs.aggregate(
            total=Count("id"),
            likes=Sum("likes"),
            views=Sum("views"),
            comments=Sum("comments_count"),
            avg_eng=Avg("engagement_rate"),
        )

        sent = Counter(
            SentimentResult.objects.filter(
                comment__post__account=acct,
                created_at__gte=window_start,
            ).values_list("label", flat=True)
        )
        sent_total = sum(sent.values()) or 1

        top_post = posts_qs.order_by("-likes").first()

        lines.append(f"### @{acct.handle} ({acct.get_platform_display()})")
        lines.append(f"- Followers: {acct.follower_count:,}")
        lines.append(f"- Posts: {agg['total'] or 0}")
        lines.append(f"- Total likes: {agg['likes'] or 0:,}")
        lines.append(f"- Total views: {agg['views'] or 0:,}")
        lines.append(f"- Avg engagement: {(agg['avg_eng'] or 0) * 100:.2f}%")
        lines.append(
            f"- Sentiment: "
            f"{sent.get(SentimentLabel.POSITIVE, 0) * 100 / sent_total:.0f}% positive / "
            f"{sent.get(SentimentLabel.NEGATIVE, 0) * 100 / sent_total:.0f}% negative "
            f"({sum(sent.values())} comments analysed)"
        )
        if top_post:
            caption = (top_post.caption or "—").strip().replace("\n", " ")[:80]
            lines.append(f"- Top post: \"{caption}\" — {top_post.likes} likes")
        lines.append("")

    return "\n".join(lines)


def _openai_client(*, backup: bool = False):
    """Lazy import + construct the OpenAI client, or raise ChatNotConfigured.

    When ``backup=True`` use the OPENAI_BACKUP_* env vars instead — used by
    :func:`_chat_completion` to fall through to a second provider (e.g. Groq)
    if the primary one (e.g. Gemini) errors out. Raises ChatNotConfigured if
    the requested key set isn't set.
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ChatNotConfigured(
            "'openai' package is not installed. "
            "Add `openai>=1.30,<2.0` to requirements and `pip install`."
        ) from e

    if backup:
        api_key      = getattr(settings, "OPENAI_BACKUP_API_KEY", "")
        base_url     = getattr(settings, "OPENAI_BACKUP_BASE_URL", "")
        if not api_key:
            raise ChatNotConfigured("OPENAI_BACKUP_API_KEY env var is not set.")
    else:
        api_key      = getattr(settings, "OPENAI_API_KEY", "")
        base_url     = getattr(settings, "OPENAI_BASE_URL", "")
        if not api_key:
            raise ChatNotConfigured("OPENAI_API_KEY env var is not set.")

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    organization = getattr(settings, "OPENAI_ORGANIZATION", "")
    if organization and not backup:
        kwargs["organization"] = organization

    return OpenAI(**kwargs)


def _model_for(backup: bool) -> str:
    if backup:
        return (
            getattr(settings, "OPENAI_BACKUP_MODEL", "")
            or "llama-3.3-70b-versatile"   # Groq default
        )
    return getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")


def _chat_completion(system: str, user_msg: str, max_tokens: int) -> ChatResponse:
    """Single OpenAI chat completion with our standard params.

    Tries the primary provider first; on any exception (auth, rate-limit,
    network, region block) falls through to the backup provider when
    OPENAI_BACKUP_API_KEY is set. The backup attempt's exception bubbles
    up unchanged when both providers fail, so the caller's existing
    error-handling path stays valid.
    """
    def _call(*, backup: bool) -> ChatResponse:
        client = _openai_client(backup=backup)
        model = _model_for(backup)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
        )
        choice = response.choices[0]
        answer = (choice.message.content or "").strip()
        usage = response.usage
        return ChatResponse(
            answer=answer,
            model=response.model,
            tokens_in=getattr(usage, "prompt_tokens", 0) if usage else 0,
            tokens_out=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    try:
        return _call(backup=False)
    except ChatNotConfigured:
        # Primary not configured — try backup outright.
        return _call(backup=True)
    except Exception as primary_err:
        # Primary errored mid-call. If a backup is configured, try it; otherwise
        # bubble the original exception so the user-visible error stays accurate.
        if getattr(settings, "OPENAI_BACKUP_API_KEY", ""):
            try:
                logger.warning("Primary AI failed (%s); falling back to backup.", primary_err)
                return _call(backup=True)
            except Exception:
                logger.exception("Backup AI also failed")
        raise


def ask(user, question: str) -> ChatResponse:
    """Send ``question`` + ``user``'s analytics context to OpenAI; return the reply.

    Raises :class:`ChatNotConfigured` if the openai SDK is missing or
    ``OPENAI_API_KEY`` is unset — callers should surface that as a
    user-visible notice, not a crash.
    """
    max_tokens = int(getattr(settings, "OPENAI_MAX_TOKENS", 1024))
    context = _build_user_context(user)
    return _chat_completion(
        system=SYSTEM_PROMPT + "\n## Data\n\n" + context,
        user_msg=question,
        max_tokens=max_tokens,
    )


DIGEST_PROMPT = """Generate a weekly analytics digest for the user based on the
data below. Output in the user's primary language (infer from account handles
and comment samples — default to Uzbek). Structure:

1. One-sentence headline: the single most important change this week.
2. "Nimalar yaxshi bo'ldi" — 2-4 bullet points of wins.
3. "E'tibor bering" — 2-4 bullet points of concerns or drops.
4. "Tavsiya" — one concrete, specific next action.

Rules:
- Use ONLY the provided numbers. No invented stats.
- Be specific: cite the account handle and the metric delta.
- Keep the whole digest under 250 words.
- Plain text with simple markdown (## headings, - bullets). No emojis.
"""


def translate_text(text: str, target_lang: str = "uz") -> ChatResponse:
    """Translate ``text`` into ``target_lang`` (uz / ru / en).

    Reuses the OpenAI client + ChatNotConfigured plumbing the analytics chat
    already has — no separate translation service / API key. Capped at 400
    output tokens (one short comment is plenty)."""
    LANG_NAMES = {
        "uz": "Uzbek (Latin script)",
        "ru": "Russian",
        "en": "English",
    }
    target_name = LANG_NAMES.get(target_lang, "Uzbek (Latin script)")
    system = (
        "You are a translation assistant. Translate the user-provided text "
        f"into {target_name}. Output ONLY the translated text — no quotes, "
        "no explanations, no language label. Preserve emojis and punctuation."
    )
    return _chat_completion(system=system, user_msg=text[:1000], max_tokens=400)


def generate_weekly_digest(user) -> ChatResponse:
    """Generate a short AI-written weekly summary for ``user``'s accounts.

    Raises :class:`ChatNotConfigured` same as :func:`ask`.
    """
    max_tokens = int(getattr(settings, "OPENAI_DIGEST_MAX_TOKENS", 800))
    context = _build_user_context(user)
    return _chat_completion(
        system=DIGEST_PROMPT + "\n## Data\n\n" + context,
        user_msg="Write the weekly digest now.",
        max_tokens=max_tokens,
    )


POST_GEN_PROMPT = """You are a social-media copywriter. Below are the user's
TOP-performing posts (most likes / engagement). Generate THREE NEW post
caption drafts that match their style — same tone, length range, emoji
usage, hashtag pattern. Each draft should feel like it could have been
written by them.

Output strictly this format (no extra commentary, no JSON):

---
1. <first caption>

2. <second caption>

3. <third caption>
---

Rules:
- Match the dominant language (Uzbek / Russian / English) of the top posts.
- Keep length similar to their average top-post length.
- Use 1-3 hashtags max if their top posts use hashtags; otherwise none.
- Don't copy phrases verbatim — generate fresh variations.
- Topic: keep it broadly aligned (e.g. if they post motivation, suggest motivation).
"""


def _top_posts_context(user, limit: int = 5) -> str:
    """Build a compact prompt fragment listing the user's top posts.

    Used by the post-draft generator. Keeps captions truncated to 220 chars
    each so we don't burn tokens on long posts.
    """
    posts = (
        Post.objects
        .filter(account__user=user)
        .order_by("-likes")[:limit]
    )
    if not posts:
        return "The user has no posts yet — generate generic but high-quality drafts."

    lines = ["## Top posts (by likes)", ""]
    for i, p in enumerate(posts, 1):
        caption = (p.caption or "—").strip().replace("\n", " ")[:220]
        lines.append(
            f"{i}. [{p.account.get_platform_display()} @{p.account.handle}] "
            f"likes={p.likes} views={p.views} | {caption}"
        )
    return "\n".join(lines)


def generate_post_drafts(user) -> ChatResponse:
    """Generate 3 new post-caption drafts in the user's style.

    Reads their top 5 posts as a style reference and asks the AI to produce
    three fresh captions that match. Raises :class:`ChatNotConfigured` same
    as :func:`ask`.
    """
    max_tokens = int(getattr(settings, "OPENAI_POSTGEN_MAX_TOKENS", 600))
    context = _top_posts_context(user)
    return _chat_completion(
        system=POST_GEN_PROMPT + "\n" + context,
        user_msg="Generate the three drafts now.",
        max_tokens=max_tokens,
    )
