"""Unit tests for the wordcloud keyword extraction service (pure function)."""
from __future__ import annotations

import pytest

from apps.analytics.services.wordcloud import (
    WordcloudEntry,
    _tokenize,
    top_words,
)


def test_empty_input() -> None:
    assert top_words([]) == []


def test_filters_short_tokens() -> None:
    result = top_words(["is on at absolutely"])
    assert [w.text for w in result] == ["absolutely"]


def test_filters_stopwords() -> None:
    result = top_words(["and for but absolutely"])
    assert [w.text for w in result] == ["absolutely"]


def test_filters_digits() -> None:
    result = top_words(["123 absolutely 456"])
    assert [w.text for w in result] == ["absolutely"]


def test_case_insensitive() -> None:
    result = top_words(["Hello HELLO hello"])
    assert result[0].text == "hello"
    assert result[0].count == 3


def test_ranks_by_frequency() -> None:
    bodies = [
        "python rocks great",
        "python framework great",
        "django web framework python",
    ]
    result = top_words(bodies)
    counts = {w.text: w.count for w in result}
    assert counts["python"] == 3
    assert counts["framework"] == 2
    assert counts["great"] == 2


def test_respects_n_limit() -> None:
    bodies = [f"word{i:03d} " for i in range(50)]
    result = top_words(bodies, n=10)
    assert len(result) == 10


def test_weight_span() -> None:
    bodies = [
        "python " * 5,
        "django " * 3,
        "flask " * 1,
    ]
    result = top_words(bodies)
    weights = [w.weight for w in result]
    assert max(weights) == pytest.approx(1.0)
    assert min(weights) >= 0.15
    assert all(0 <= w <= 1 for w in weights)


def test_handles_uzbek_latin() -> None:
    bodies = [
        "rahmat video chiqibdi",
        "klass video rahmat",
    ]
    result = top_words(bodies)
    words = {w.text for w in result}
    assert "rahmat" in words
    assert "video" in words


def test_filters_russian_stopwords() -> None:
    bodies = ["это очень классное видео спасибо"]
    result = top_words(bodies)
    words = {w.text for w in result}
    assert "это" not in words
    assert "очень" not in words
    assert "классное" in words
    assert "видео" in words
    assert "спасибо" in words


def test_entry_is_frozen() -> None:
    entry = WordcloudEntry(text="foo", count=10, weight=0.5)
    with pytest.raises((AttributeError, TypeError)):
        entry.text = "bar"  # type: ignore[misc]


def test_tokenize_yields_individually() -> None:
    tokens = list(_tokenize("hello WORLD python"))
    assert tokens == ["hello", "world", "python"]
