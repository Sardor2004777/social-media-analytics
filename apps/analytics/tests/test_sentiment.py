"""Unit tests for the sentiment analyzer."""
from __future__ import annotations

import pytest

from apps.analytics.services.sentiment import (
    LABEL_NEGATIVE,
    LABEL_NEUTRAL,
    LABEL_POSITIVE,
    SentimentAnalyzer,
    detect_language,
)


@pytest.fixture
def analyzer() -> SentimentAnalyzer:
    # prefer_transformer=False keeps the test fast & offline
    return SentimentAnalyzer(prefer_transformer=False)


def test_detect_language_uzbek_latin() -> None:
    assert detect_language("Yaxshi ish, rahmat uchun") == "uz"


def test_detect_language_uzbek_cyrillic() -> None:
    assert detect_language("Яхши иш, раҳмат") == "uz"


def test_detect_language_russian() -> None:
    assert detect_language("Это очень хороший пост") in {"ru"}


def test_detect_language_english() -> None:
    assert detect_language("This is a great post") == "en"


def test_detect_language_empty() -> None:
    assert detect_language("") == "xx"
    assert detect_language("   ") == "xx"


def test_analyze_positive_english(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("I love this post, amazing work!")
    assert result.label == LABEL_POSITIVE
    assert 0.0 <= result.score <= 1.0


def test_analyze_negative_english(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("This is absolutely terrible, worst thing I have seen")
    assert result.label == LABEL_NEGATIVE


def test_analyze_positive_russian(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("Супер отлично спасибо за такой красивый пост")
    assert result.label == LABEL_POSITIVE


def test_analyze_negative_russian(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("Ужасно плохо, ненавижу такие посты")
    assert result.label == LABEL_NEGATIVE


def test_analyze_positive_uzbek(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("Zo'r post, ajoyib ish, rahmat!")
    assert result.label == LABEL_POSITIVE


def test_analyze_batch_preserves_order(analyzer: SentimentAnalyzer) -> None:
    texts = [
        "I love this",
        "This is terrible",
        "",
        "ok",
    ]
    results = analyzer.analyze_batch(texts)
    assert len(results) == 4
    assert results[0].label == LABEL_POSITIVE
    assert results[1].label == LABEL_NEGATIVE


def test_analyze_empty_text_is_neutral(analyzer: SentimentAnalyzer) -> None:
    result = analyzer.analyze("")
    assert result.label == LABEL_NEUTRAL


def test_languages_argument_length_validated(analyzer: SentimentAnalyzer) -> None:
    with pytest.raises(ValueError):
        analyzer.analyze_batch(["a", "b"], languages=["en"])


def test_model_name_populates_after_inference(analyzer: SentimentAnalyzer) -> None:
    analyzer.analyze("hello")
    assert analyzer.model_name in {"vader", "keyword"}
