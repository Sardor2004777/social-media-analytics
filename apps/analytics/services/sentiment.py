"""Sentiment analysis service.

Selects the best available engine at runtime:

1. **Transformer** (cardiffnlp/twitter-xlm-roberta-base-sentiment) — if the
   ``transformers`` and ``torch`` packages are both importable. Highest quality
   for multilingual social text; lazy-loaded so startup stays fast.
2. **VADER** — always available (``vaderSentiment`` is in base.txt). Light,
   English-tuned; we give Cyrillic text a neutral-bias adjustment via
   language detection.
3. **Keyword fallback** — last-resort rule engine that never fails.

Public surface:

    analyzer = get_analyzer()
    result = analyzer.analyze("love this!")
    results = analyzer.analyze_batch(["love it", "nafratlanaman", "..."])

``SentimentResult`` is a plain dataclass — DB persistence is the caller's
responsibility (see ``apps.analytics.services.persist``).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

logger = logging.getLogger(__name__)

LABEL_POSITIVE = "positive"
LABEL_NEUTRAL  = "neutral"
LABEL_NEGATIVE = "negative"


@dataclass(frozen=True, slots=True)
class SentimentPrediction:
    label: str              # "positive" | "neutral" | "negative"
    score: float            # confidence, 0..1
    language: str           # 2-letter code (best-effort)
    model_name: str         # "transformer:xlm-roberta" / "vader" / "keyword"


# ---------------------------------------------------------------------------
# Language detection (cheap, cached)
# ---------------------------------------------------------------------------

_UZ_LATIN_MARKERS = re.compile(r"\b(va|ham|lekin|emas|bilan|uchun|yaxshi|yomon|rahmat)\b", re.I)
_UZ_CYRILLIC_MARKERS = re.compile(r"\b(ва|ҳам|лекин|эмас|билан|учун|яхши|ёмон|раҳмат)\b", re.I)


def detect_language(text: str) -> str:
    """Return a 2-letter language code; 'xx' when unknown.

    Falls back to regex markers before invoking ``langdetect`` because
    langdetect is slow on 1-2 word strings and misclassifies uzbek latin as
    turkish/indonesian frequently.
    """
    t = (text or "").strip()
    if not t:
        return "xx"

    if _UZ_CYRILLIC_MARKERS.search(t):
        return "uz"
    if _UZ_LATIN_MARKERS.search(t):
        return "uz"

    try:
        from langdetect import DetectorFactory, detect
        DetectorFactory.seed = 0
        code = detect(t)
        if code in {"uz", "ru", "en"}:
            return code
        if code == "tr":      # langdetect often guesses uz->tr
            return "uz"
        return code[:2]
    except Exception:
        return "xx"


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

class _KeywordEngine:
    """Ultra-simple positive/negative keyword list. Always available."""

    POSITIVE = {
        # uz (latin + cyrillic)
        "zo'r", "ajoyib", "yaxshi", "zoʻr", "klass", "rahmat", "gullash", "mukammal",
        "chiroyli", "sevaman", "baxtli", "omad", "foydali", "tabrik", "qoyil",
        "супер", "отлично", "лучший", "хорошо", "класс", "спасибо", "красиво",
        # en
        "good", "great", "love", "awesome", "amazing", "excellent", "wow",
        "thanks", "perfect", "best", "cool", "nice", "beautiful", "fire",
    }
    NEGATIVE = {
        "yomon", "afsus", "xafa", "dahshat", "jirkanch", "yolg'on",
        "nafrat", "nafratlanaman", "nafratli", "achchiq", "foydasiz",
        "noto'g'ri", "xato", "ахлоқсиз",
        "плохо", "ужас", "фу", "ненавижу", "злость", "бесит", "отвратительно",
        "bad", "hate", "terrible", "awful", "worst", "disgust", "scam", "fake",
    }

    def score_text(self, text: str) -> tuple[str, float]:
        tokens = re.findall(r"[\w'ʻ-]+", (text or "").lower())
        pos = sum(1 for t in tokens if t in self.POSITIVE)
        neg = sum(1 for t in tokens if t in self.NEGATIVE)
        if pos == 0 and neg == 0:
            return LABEL_NEUTRAL, 0.5
        if pos >= neg:
            return LABEL_POSITIVE, min(1.0, 0.55 + 0.1 * (pos - neg))
        return LABEL_NEGATIVE, min(1.0, 0.55 + 0.1 * (neg - pos))


class _VaderEngine:
    """Lexicon + rule-based (English-tuned but holds up on short social text)."""

    def __init__(self) -> None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        self._sia = SentimentIntensityAnalyzer()
        self._kw = _KeywordEngine()

    def score_text(self, text: str, language: str) -> tuple[str, float]:
        # VADER was trained on English. For UZ/RU we blend VADER's compound
        # score with the keyword engine to avoid mislabeling cyrillic text
        # as neutral just because VADER doesn't know the words.
        scores = self._sia.polarity_scores(text or "")
        compound = scores["compound"]

        if language in ("uz", "ru") or (language == "xx" and re.search(r"[\u0400-\u04FF]", text or "")):
            kw_label, kw_score = self._kw.score_text(text)
            # Blend: if keyword engine is confident, it wins
            if kw_label != LABEL_NEUTRAL:
                return kw_label, max(kw_score, abs(compound))
            # else fall through to VADER compound

        if compound >= 0.15:
            return LABEL_POSITIVE, min(1.0, 0.5 + compound / 2)
        if compound <= -0.15:
            return LABEL_NEGATIVE, min(1.0, 0.5 + abs(compound) / 2)
        return LABEL_NEUTRAL, 1 - abs(compound)


class _TransformerEngine:
    """Lazy-loaded XLM-RoBERTa via HuggingFace pipeline."""

    model_id = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

    def __init__(self) -> None:
        from transformers import pipeline  # noqa — raises ImportError if missing
        logger.info("Loading transformer model %s (first call; may take a while)…", self.model_id)
        self._pipe = pipeline("sentiment-analysis", model=self.model_id, tokenizer=self.model_id)

    def score_texts(self, texts: list[str]) -> list[tuple[str, float]]:
        if not texts:
            return []
        raw = self._pipe(texts, truncation=True, max_length=200, batch_size=32)
        out: list[tuple[str, float]] = []
        for r in raw:
            label = r["label"].lower()   # "Positive" / "Neutral" / "Negative"
            if label.startswith("pos"):  lbl = LABEL_POSITIVE
            elif label.startswith("neg"): lbl = LABEL_NEGATIVE
            else:                         lbl = LABEL_NEUTRAL
            out.append((lbl, float(r["score"])))
        return out


# ---------------------------------------------------------------------------
# Public analyzer
# ---------------------------------------------------------------------------

class SentimentAnalyzer:
    """Top-level analyzer that orchestrates the available engines."""

    def __init__(self, prefer_transformer: bool = True) -> None:
        self._prefer_transformer = prefer_transformer
        self._transformer: _TransformerEngine | None = None
        self._vader: _VaderEngine | None = None
        self._keyword = _KeywordEngine()
        self._transformer_checked = False

    # --- engine resolution ------------------------------------------------

    def _get_transformer(self) -> _TransformerEngine | None:
        if not self._prefer_transformer:
            return None
        if self._transformer_checked:
            return self._transformer
        self._transformer_checked = True
        try:
            self._transformer = _TransformerEngine()
        except Exception as exc:
            logger.info("Transformer engine unavailable (%s); using VADER.", exc.__class__.__name__)
            self._transformer = None
        return self._transformer

    def _get_vader(self) -> _VaderEngine:
        if self._vader is None:
            try:
                self._vader = _VaderEngine()
            except Exception as exc:
                logger.warning("VADER unavailable (%s); falling back to keyword engine.", exc)
                raise
        return self._vader

    @property
    def model_name(self) -> str:
        if self._transformer is not None:
            return f"transformer:{_TransformerEngine.model_id}"
        if self._vader is not None:
            return "vader"
        return "keyword"

    # --- public API -------------------------------------------------------

    def analyze(self, text: str, language: str | None = None) -> SentimentPrediction:
        return self.analyze_batch([text], languages=[language] if language else None)[0]

    def analyze_batch(
        self,
        texts: Iterable[str],
        languages: list[str] | None = None,
    ) -> list[SentimentPrediction]:
        items = list(texts)
        if not items:
            return []

        if languages is not None and len(languages) != len(items):
            raise ValueError("languages must have the same length as texts")
        langs = languages or [detect_language(t) for t in items]

        # 1. Try transformer (batch)
        trans = self._get_transformer()
        if trans is not None:
            try:
                rows = trans.score_texts(items)
                return [
                    SentimentPrediction(
                        label=label,
                        score=score,
                        language=langs[i] or "xx",
                        model_name=f"transformer:{_TransformerEngine.model_id}",
                    )
                    for i, (label, score) in enumerate(rows)
                ]
            except Exception as exc:
                logger.warning("Transformer batch failed (%s); falling back to VADER.", exc)

        # 2. VADER (per-item)
        try:
            vader = self._get_vader()
            out: list[SentimentPrediction] = []
            for text, lang in zip(items, langs):
                label, score = vader.score_text(text, lang or "xx")
                out.append(SentimentPrediction(label=label, score=score, language=lang or "xx", model_name="vader"))
            return out
        except Exception:
            pass

        # 3. Keyword
        out_kw: list[SentimentPrediction] = []
        for text, lang in zip(items, langs):
            label, score = self._keyword.score_text(text)
            out_kw.append(SentimentPrediction(label=label, score=score, language=lang or "xx", model_name="keyword"))
        return out_kw


@lru_cache(maxsize=1)
def get_analyzer(prefer_transformer: bool = True) -> SentimentAnalyzer:
    """Process-wide singleton."""
    return SentimentAnalyzer(prefer_transformer=prefer_transformer)
