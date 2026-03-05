"""Normalisation des sorties collecteurs en ScoredArticle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Engagement:
    points: int | None = None
    num_comments: int | None = None


@dataclass
class SubScores:
    relevance: int = 0
    recency: int = 0
    engagement: int = 0


@dataclass
class ScoredArticle:
    title: str
    url: str
    source_id: str
    source_name: str
    published: str
    summary: str
    author: str
    tags: list[str]
    metadata: dict[str, Any]
    engagement: Engagement
    subs: SubScores
    score: int = 0
    cross_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "published": self.published,
            "summary": self.summary,
            "author": self.author,
            "tags": self.tags,
            "metadata": self.metadata,
            "engagement": {"points": self.engagement.points, "num_comments": self.engagement.num_comments},
            "subs": {"relevance": self.subs.relevance, "recency": self.subs.recency, "engagement": self.subs.engagement},
            "score": self.score,
            "cross_refs": self.cross_refs,
        }


def normalize_collector_output(raw_json: dict[str, Any]) -> list[ScoredArticle]:
    """Convertit la sortie JSON brute d'un collecteur en liste de ScoredArticle."""
    articles = []
    source_id = raw_json.get("source_id", "unknown")
    source_name = raw_json.get("source_name", "Unknown")

    for item in raw_json.get("articles", []):
        points = None
        raw_score = item.get("score")
        if raw_score and float(raw_score) > 0:
            points = int(float(raw_score))

        meta = item.get("metadata", {})
        if points is None and "points" in meta:
            points = int(meta["points"])

        num_comments = None
        if "num_comments" in meta:
            num_comments = int(meta["num_comments"])

        articles.append(
            ScoredArticle(
                title=item.get("title", ""),
                url=item.get("url", ""),
                source_id=item.get("source_id", source_id),
                source_name=item.get("source_name", source_name),
                published=item.get("published", ""),
                summary=item.get("summary", ""),
                author=item.get("author", ""),
                tags=item.get("tags", []),
                metadata=meta,
                engagement=Engagement(points=points, num_comments=num_comments),
                subs=SubScores(),
            )
        )

    return articles
