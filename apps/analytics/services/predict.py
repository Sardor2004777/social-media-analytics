"""Engagement prediction — sklearn LinearRegression on per-user post data.

Trains a separate model per user on demand. Features extracted from each
post:

* ``weekday``      — 0 (Mon) – 6 (Sun)
* ``hour``         — 0–23
* ``caption_len``  — character count of the caption
* ``hashtag_count``— count of ``#tags`` in caption
* ``has_media``    — 1 if PostType is photo/video/reel/carousel, else 0

Target is ``log1p(likes)`` — log-transform stabilises the long tail (a few
viral posts otherwise dominate the loss). Predictions are reverse-transformed
(``expm1``) before display.

The model is cheap to fit on a few hundred rows (the typical user account
size), so we re-train at request time instead of caching. ``MIN_TRAIN_ROWS``
guards against fitting on too little data — under that threshold the
service raises :class:`NotEnoughData` and the view shows a helpful empty
state instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from django.utils import timezone
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from apps.social.models import Post, PostType

MIN_TRAIN_ROWS = 12
HASHTAG_RE = re.compile(r"#\w{2,30}", flags=re.UNICODE)
MEDIA_TYPES = {PostType.PHOTO, PostType.VIDEO, PostType.REEL, PostType.CAROUSEL}


class NotEnoughData(RuntimeError):
    """Raised when the user has fewer than MIN_TRAIN_ROWS posts to fit on."""


@dataclass(frozen=True)
class Prediction:
    expected_likes: int
    expected_engagement_pct: float
    r2: float            # in-sample fit quality (0..1)
    sample_size: int
    feature_weights: dict[str, float]    # for the "what drives engagement" panel


def _extract_features(post) -> list[float]:
    caption = post.caption or ""
    return [
        float(post.published_at.weekday()),
        float(post.published_at.hour),
        float(len(caption)),
        float(len(HASHTAG_RE.findall(caption))),
        1.0 if post.post_type in MEDIA_TYPES else 0.0,
    ]


def _features_from_inputs(weekday: int, hour: int, caption_len: int,
                          hashtag_count: int, has_media: bool) -> list[float]:
    return [
        float(weekday),
        float(hour),
        float(caption_len),
        float(hashtag_count),
        1.0 if has_media else 0.0,
    ]


FEATURE_LABELS_UZ = {
    0: "Hafta kuni",
    1: "Soat",
    2: "Caption uzunligi",
    3: "Hashtag soni",
    4: "Media bormi",
}


def _train(user) -> tuple[LinearRegression, np.ndarray, np.ndarray, list]:
    """Fetch the user's post history and fit the regression model.

    Returns ``(model, X, y_log, posts)``. ``y_log`` is the log1p-transformed
    target (likes) — the caller reverses the transform via ``expm1`` after
    predicting.
    """
    posts = list(
        Post.objects.filter(account__user=user).only(
            "post_type", "caption", "published_at", "likes",
        )
    )
    if len(posts) < MIN_TRAIN_ROWS:
        raise NotEnoughData(
            f"Bashorat uchun kamida {MIN_TRAIN_ROWS} ta post kerak — "
            f"hozir {len(posts)} ta. Akkauntingizni ulab, sync'ni kuting."
        )
    X = np.array([_extract_features(p) for p in posts], dtype=float)
    y = np.array([p.likes or 0 for p in posts], dtype=float)
    y_log = np.log1p(y)
    model = LinearRegression()
    model.fit(X, y_log)
    return model, X, y_log, posts


def predict_for_inputs(
    user,
    *,
    weekday: int,
    hour: int,
    caption_len: int,
    hashtag_count: int,
    has_media: bool,
) -> Prediction:
    """Predict expected engagement for a hypothetical post defined by inputs."""
    model, X, y_log, posts = _train(user)
    sample = np.array([_features_from_inputs(
        weekday, hour, caption_len, hashtag_count, has_media,
    )], dtype=float)
    pred_log = float(model.predict(sample)[0])
    pred_likes = max(0, int(np.expm1(pred_log)))
    # In-sample R² as a quick "how trustworthy" signal.
    y_pred_log = model.predict(X)
    r2 = max(0.0, float(r2_score(y_log, y_pred_log)))
    # Feature contribution for transparency: |coef| × std(feature) gives
    # a rough "importance" — normalised to sum to 100 for the UI bars.
    importances = np.abs(model.coef_) * X.std(axis=0)
    total = importances.sum() or 1
    weights = {
        FEATURE_LABELS_UZ[i]: round(float(importances[i] / total * 100), 1)
        for i in range(len(model.coef_))
    }
    # Engagement %: rough estimate from likes / median(views).
    avg_views = np.median([p.views or 0 for p in posts]) or 1
    eng_pct = round(pred_likes / max(avg_views, 1) * 100, 2)
    return Prediction(
        expected_likes=pred_likes,
        expected_engagement_pct=eng_pct,
        r2=round(r2, 3),
        sample_size=len(posts),
        feature_weights=weights,
    )


def best_post_recipe(user) -> dict | None:
    """Combine the heatmap's best (weekday, hour) with model search over the
    other features to produce a single concrete "post like this" suggestion.

    Picks the (caption_len, hashtag_count, has_media) combo that maximises
    predicted likes among a small grid — the result is what the dashboard's
    "Optimal Posting AI" card surfaces as a one-line recipe.
    """
    try:
        model, X, y_log, posts = _train(user)
    except NotEnoughData:
        return None
    # Pull best weekday × hour from the same posts (avg engagement_rate).
    from collections import defaultdict
    eng_by = defaultdict(list)
    for p in posts:
        eng_by[(p.published_at.weekday(), p.published_at.hour)].append(
            p.engagement_rate or 0
        )
    if not eng_by:
        return None
    best_slot = max(eng_by.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
    wd, hr = best_slot[0]

    # Grid-search remaining 3 features. Caption length grid centres around
    # bands the post-length analyzer already knows are common; hashtag grid
    # 0..6 covers the realistic range; media is a binary toggle.
    grid_caption = [40, 80, 120, 180, 280, 400]
    grid_hashtags = [0, 2, 4, 6]
    grid_media = [0, 1]

    best = None
    for cl in grid_caption:
        for hc in grid_hashtags:
            for hm in grid_media:
                feat = np.array([[wd, hr, cl, hc, hm]], dtype=float)
                pred = float(np.expm1(model.predict(feat)[0]))
                if best is None or pred > best["pred"]:
                    best = {
                        "pred":          pred,
                        "weekday":       wd,
                        "hour":          hr,
                        "caption_len":   cl,
                        "hashtag_count": hc,
                        "has_media":     bool(hm),
                    }
    weekday_names_uz = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba",
                        "Juma", "Shanba", "Yakshanba"]
    return {
        "weekday":       weekday_names_uz[best["weekday"]],
        "weekday_idx":   best["weekday"],
        "hour":          best["hour"],
        "caption_len":   best["caption_len"],
        "hashtag_count": best["hashtag_count"],
        "has_media":     best["has_media"],
        "expected_likes": max(0, int(best["pred"])),
    }
