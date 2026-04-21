"""Keyword extraction for comment bodies, grouped by sentiment.

Pure function — returns a list of :class:`WordcloudEntry` suitable for rendering
as a CSS-sized tag cloud in the template (no image generation, no extra
dependencies). Handles multilingual text (Uzbek Latin + Cyrillic, Russian,
English) via a small inline stopword list.

For a production tool we'd pull stopwords from ``spacy`` / ``nltk``; for a
diploma demo this module is intentionally self-contained.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

# Minimal multilingual stopword set. Size kept ~120 entries — enough to knock
# out the noisiest tokens without requiring a per-language lexicon download.
STOPWORDS: frozenset[str] = frozenset({
    # English
    "the", "and", "for", "are", "was", "were", "been", "being", "have",
    "has", "had", "not", "but", "this", "that", "these", "those", "with",
    "from", "they", "them", "their", "there", "here", "what", "which",
    "when", "where", "why", "how", "can", "will", "would", "could",
    "should", "just", "like", "more", "most", "some", "any", "all", "one",
    "very", "also", "then", "than", "only", "into", "out", "your", "you",
    "our", "ours", "its", "his", "her", "him", "she", "too", "yes", "off",
    # Russian
    "это", "что", "как", "для", "еще", "уже", "или", "так", "там", "тут",
    "все", "всё", "меня", "тебя", "его", "нас", "вас", "них", "мне",
    "тебе", "ему", "ей", "нам", "вам", "им", "себя", "себе", "тоже",
    "ведь", "даже", "очень", "только", "если", "пока", "потому", "чтобы",
    # Uzbek (Latin)
    "bilan", "uchun", "shunday", "lekin", "ammo", "ham", "yoki", "agar",
    "chunki", "qachon", "qayer", "nima", "qanday", "barcha", "hamma",
    "juda", "ba'zi", "yana", "emas", "bor", "yoq", "endi", "hali", "ko'p",
    "men", "sen", "biz", "siz", "ular", "meni", "seni", "uni", "bizni",
    "sizni", "ularni",
    # Uzbek (Cyrillic)
    "билан", "учун", "шундай", "лекин", "аммо", "ҳам", "ёки", "агар",
    "чунки", "қачон", "нима", "қандай", "барча", "ҳамма", "жуда",
    "яна", "эмас", "бор", "йўқ", "энди", "ҳали", "кўп", "мен", "сен",
    "биз", "сиз", "улар",
})

_TOKEN_RE = re.compile(r"[\wʼ’'-]+", re.UNICODE)
_MIN_LEN = 3
_DEFAULT_N = 30


@dataclass(frozen=True)
class WordcloudEntry:
    text: str
    count: int
    weight: float  # 0.0 (smallest) .. 1.0 (largest), for proportional sizing


def _tokenize(text: str) -> Iterable[str]:
    for m in _TOKEN_RE.findall(text.lower()):
        tok = m.strip("'ʼ’-")
        if len(tok) < _MIN_LEN:
            continue
        if tok.isdigit():
            continue
        if tok in STOPWORDS:
            continue
        yield tok


def top_words(bodies: Iterable[str], n: int = _DEFAULT_N) -> list[WordcloudEntry]:
    """Return the top-``n`` tokens across all given comment bodies.

    Tokens are lowercased, filtered to length ≥ 3, non-numeric, and not in
    the multilingual stopword list. The returned ``weight`` is a 0..1
    linear scale based on frequency — max-count token gets 1.0, lowest gets
    ~0.15 so even the tail stays visible.
    """
    counter: Counter[str] = Counter()
    for body in bodies:
        counter.update(_tokenize(body))

    most = counter.most_common(n)
    if not most:
        return []

    max_count = most[0][1]
    min_count = most[-1][1] if len(most) > 1 else max_count
    span = max(max_count - min_count, 1)
    return [
        WordcloudEntry(
            text=word,
            count=count,
            weight=round(0.15 + 0.85 * (count - min_count) / span, 3),
        )
        for word, count in most
    ]
