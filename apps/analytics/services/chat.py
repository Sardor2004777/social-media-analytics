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


def _openai_client():
    """Lazy import + construct the OpenAI client, or raise ChatNotConfigured."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ChatNotConfigured(
            "'openai' package is not installed. "
            "Add `openai>=1.30,<2.0` to requirements and `pip install`."
        ) from e

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise ChatNotConfigured("OPENAI_API_KEY env var is not set.")

    kwargs = {"api_key": api_key}
    base_url = getattr(settings, "OPENAI_BASE_URL", "")
    if base_url:
        kwargs["base_url"] = base_url
    organization = getattr(settings, "OPENAI_ORGANIZATION", "")
    if organization:
        kwargs["organization"] = organization

    return OpenAI(**kwargs)


def _chat_completion(system: str, user_msg: str, max_tokens: int) -> ChatResponse:
    """Single OpenAI chat completion with our standard params."""
    client = _openai_client()
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

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
