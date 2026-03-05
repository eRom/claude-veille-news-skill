"""Scoring unifie des articles."""

from __future__ import annotations

import math
import re
from typing import Any

from scripts.lib.dates import recency_score
from scripts.lib.normalize import ScoredArticle


def relevance_score(title: str, summary: str, keywords: dict[str, list[str]]) -> int:
    """Score de pertinence 0-100 base sur le match des keywords."""
    text = f"{title} {summary}".lower()
    primary = keywords.get("primary", [])
    secondary = keywords.get("secondary", [])
    exclude = keywords.get("exclude", [])

    for ex in exclude:
        if ex.lower() in text:
            return 0

    total = 0
    max_possible = 0

    for kw in primary:
        max_possible += 2
        if kw.lower() in text:
            total += 2

    for kw in secondary:
        max_possible += 1
        if kw.lower() in text:
            total += 1

    if max_possible == 0:
        return 50

    return int(100 * total / max_possible)


def compute_engagement_raw(article: ScoredArticle) -> float | None:
    """Score d'engagement brut : log1p(points) * 0.55 + log1p(comments) * 0.45."""
    pts = article.engagement.points
    cmt = article.engagement.num_comments

    if pts is None and cmt is None:
        return None

    p = math.log1p(pts or 0) * 0.55
    c = math.log1p(cmt or 0) * 0.45
    return p + c


def normalize_to_100(values: list[float | None]) -> list[int]:
    """Normalisation min-max vers 0-100. None -> 0."""
    valid = [v for v in values if v is not None]
    if not valid:
        return [0] * len(values)

    mn = min(valid)
    mx = max(valid)
    rng = mx - mn

    result = []
    for v in values:
        if v is None:
            result.append(0)
        elif rng == 0:
            result.append(50)
        else:
            result.append(int(100 * (v - mn) / rng))
    return result


def score_articles(
    articles: list[ScoredArticle],
    keywords: dict[str, list[str]],
    settings: dict[str, Any],
    time_range: str = "7d",
) -> list[ScoredArticle]:
    """Calcule et assigne les scores a chaque article."""
    weights = settings.get("scoring", {}).get("weights", {})
    w_rel = weights.get("relevance", 0.35)
    w_rec = weights.get("recency", 0.25)
    w_eng = weights.get("engagement", 0.25)
    w_aut = weights.get("authority", 0.15)

    # Calcul des sous-scores
    for a in articles:
        a.subs.relevance = relevance_score(a.title, a.summary, keywords)
        a.subs.recency = recency_score(a.published, time_range)

    # Engagement : calcul brut puis normalisation
    raw_eng = [compute_engagement_raw(a) for a in articles]
    norm_eng = normalize_to_100(raw_eng)
    for a, eng in zip(articles, norm_eng):
        a.subs.engagement = eng

    # Score final (authority = 50 par defaut, pas de data pour le moment)
    authority_default = 50
    for a in articles:
        a.score = int(
            a.subs.relevance * w_rel
            + a.subs.recency * w_rec
            + a.subs.engagement * w_eng
            + authority_default * w_aut
        )

    # Tri : score desc, date desc, source_id
    articles.sort(key=lambda a: (-a.score, a.published or "", a.source_id), reverse=False)

    return articles
