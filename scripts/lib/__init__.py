"""What About — Pipeline de traitement des articles."""

from scripts.lib.normalize import ScoredArticle, Engagement, SubScores, normalize_collector_output
from scripts.lib.score import score_articles
from scripts.lib.dedupe import dedupe_articles, cross_source_link
from scripts.lib.render import render, CollectionReport

__all__ = [
    "ScoredArticle",
    "Engagement",
    "SubScores",
    "normalize_collector_output",
    "score_articles",
    "dedupe_articles",
    "cross_source_link",
    "render",
    "CollectionReport",
]
