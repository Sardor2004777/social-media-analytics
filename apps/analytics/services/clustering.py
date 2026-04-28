"""TF-IDF + KMeans clustering for the user's post captions.

Groups posts into 4-7 topic clusters based on their captions and reports
each cluster's average engagement, so the user can see "this group of
posts about X gets 4x engagement vs that group about Y".

Pure server-side scikit-learn. Caches per-request.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from apps.analytics.services.wordcloud import STOPWORDS
from apps.social.models import Post

MIN_POSTS_FOR_CLUSTERING = 12
MAX_CLUSTERS = 5
HASHTAG_RE = re.compile(r"#\w{2,30}", flags=re.UNICODE)
URL_RE = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class TopicCluster:
    cluster_id: int
    label: str               # 3-4 top tokens joined by " · "
    size: int                # number of posts in this cluster
    avg_engagement_pct: float
    avg_likes: int
    sample_caption: str      # representative post snippet


class NotEnoughPosts(RuntimeError):
    pass


def _clean(text: str) -> str:
    text = URL_RE.sub("", text)
    text = HASHTAG_RE.sub("", text)
    return text.strip().lower()


def cluster_posts(user, n_clusters: int | None = None) -> list[TopicCluster]:
    """Run TF-IDF on the user's post captions, fit KMeans, return clusters
    sorted by avg engagement (best first).

    ``n_clusters`` defaults to ``min(MAX_CLUSTERS, max(2, n_posts // 8))`` so
    a user with 30 posts gets 3 clusters, 50 posts gets 5, etc.
    """
    posts = list(
        Post.objects.filter(account__user=user)
        .exclude(caption="")
        .only("caption", "likes", "engagement_rate")
    )
    if len(posts) < MIN_POSTS_FOR_CLUSTERING:
        raise NotEnoughPosts(
            f"Klasterizatsiya uchun kamida {MIN_POSTS_FOR_CLUSTERING} ta caption "
            f"li post kerak — hozir {len(posts)} ta."
        )

    captions = [_clean(p.caption) for p in posts]

    if n_clusters is None:
        n_clusters = min(MAX_CLUSTERS, max(2, len(posts) // 8))

    # min_df=2 drops singleton tokens (less noise); max_df=0.85 drops
    # ubiquitous tokens; STOPWORDS list shared with the wordcloud module.
    vectoriser = TfidfVectorizer(
        max_features=300,
        min_df=2,
        max_df=0.85,
        stop_words=list(STOPWORDS),
        token_pattern=r"(?u)\b\w{3,}\b",
    )
    try:
        X = vectoriser.fit_transform(captions)
    except ValueError:
        # All tokens stop-word-eaten — fall back to a single bucket.
        return _fallback_single_cluster(posts)

    if X.shape[1] == 0:
        return _fallback_single_cluster(posts)

    n_clusters = min(n_clusters, X.shape[0])
    if n_clusters < 2:
        return _fallback_single_cluster(posts)

    km = KMeans(n_clusters=n_clusters, n_init="auto", random_state=42)
    labels = km.fit_predict(X)

    feature_names = vectoriser.get_feature_names_out()
    centroids = km.cluster_centers_

    out: list[TopicCluster] = []
    for cid in range(n_clusters):
        idxs = np.where(labels == cid)[0]
        if len(idxs) == 0:
            continue
        # Top 3 tokens by centroid weight = a readable cluster label.
        top_token_idx = np.argsort(centroids[cid])[::-1][:4]
        top_tokens = [feature_names[i] for i in top_token_idx if centroids[cid][i] > 0][:3]
        label = " · ".join(top_tokens) if top_tokens else f"Klaster {cid + 1}"

        cluster_posts = [posts[i] for i in idxs]
        eng_avg = sum(p.engagement_rate or 0 for p in cluster_posts) / len(cluster_posts)
        likes_avg = sum(p.likes or 0 for p in cluster_posts) / len(cluster_posts)
        # Pick the highest-engagement post as the cluster's "sample".
        sample = max(cluster_posts, key=lambda p: p.engagement_rate or 0)
        sample_text = (sample.caption or "")[:120].strip().replace("\n", " ")

        out.append(TopicCluster(
            cluster_id=cid,
            label=label,
            size=len(idxs),
            avg_engagement_pct=round(eng_avg * 100, 2),
            avg_likes=int(likes_avg),
            sample_caption=sample_text,
        ))

    out.sort(key=lambda c: c.avg_engagement_pct, reverse=True)
    return out


def _fallback_single_cluster(posts) -> list[TopicCluster]:
    eng = sum(p.engagement_rate or 0 for p in posts) / max(len(posts), 1)
    likes = sum(p.likes or 0 for p in posts) / max(len(posts), 1)
    sample = max(posts, key=lambda p: p.engagement_rate or 0)
    return [TopicCluster(
        cluster_id=0,
        label="Barcha postlar",
        size=len(posts),
        avg_engagement_pct=round(eng * 100, 2),
        avg_likes=int(likes),
        sample_caption=(sample.caption or "")[:120].strip().replace("\n", " "),
    )]
