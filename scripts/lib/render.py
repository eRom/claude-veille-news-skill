"""Rendu des resultats : compact, json, md."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any
from itertools import groupby

from scripts.lib.normalize import ScoredArticle


@dataclass
class CollectionReport:
    topic: str
    query_type: str
    domain_id: str | None
    time_range: str
    range_from: str
    range_to: str
    articles: list[ScoredArticle]
    stats: dict[str, Any]
    collected_at: str


def render(report: CollectionReport, mode: str = "compact") -> str:
    """Rend le rapport selon le mode choisi."""
    if mode == "json":
        return _render_json(report)
    elif mode == "md":
        return _render_md(report)
    else:
        return _render_compact(report)


def _render_compact(report: CollectionReport) -> str:
    """Mode compact : markdown concis optimise pour la synthese LLM."""
    lines = []

    lines.append(f"## Resultats : {report.topic}")
    lines.append(
        f"Periode : {report.range_from} -> {report.range_to} | "
        f"Sources : {report.stats.get('sources_count', 0)} | "
        f"Articles : {len(report.articles)}"
    )
    lines.append("")

    # Grouper par source
    articles_sorted = sorted(report.articles, key=lambda a: a.source_id)
    for source_id, group in groupby(articles_sorted, key=lambda a: a.source_id):
        items = list(group)
        source_name = items[0].source_name if items else source_id
        lines.append(f"### {source_name} ({len(items)} articles)")
        lines.append("")

        for idx, a in enumerate(items, 1):
            # Ligne principale
            eng_parts = []
            if a.engagement.points is not None:
                eng_parts.append(f"{a.engagement.points} pts")
            if a.engagement.num_comments is not None:
                eng_parts.append(f"{a.engagement.num_comments} comments")
            eng_str = ", ".join(eng_parts) if eng_parts else ""

            date_short = a.published[:10] if a.published else ""
            meta_parts = [p for p in [eng_str, date_short] if p]
            meta_str = f" | {' | '.join(meta_parts)}" if meta_parts else ""

            lines.append(f"{idx}. [{a.title}]({a.url}){meta_str}")

            # Resume
            if a.summary:
                summary = a.summary[:200].replace("\n", " ").strip()
                if len(a.summary) > 200:
                    summary += "..."
                lines.append(f"   {summary}")

            # Cross-refs
            if a.cross_refs:
                lines.append(f"   [aussi sur: {', '.join(a.cross_refs)}]")

            lines.append("")

    # Stats
    lines.append("---")
    source_stats = []
    for source_id, group in groupby(
        sorted(report.articles, key=lambda a: a.source_id), key=lambda a: a.source_id
    ):
        items = list(group)
        source_stats.append(f"{source_id}={len(items)}")

    cross_count = sum(1 for a in report.articles if a.cross_refs)
    max_score = max((a.score for a in report.articles), default=0)

    lines.append(f"Stats: {' '.join(source_stats)} | Cross-source={cross_count} | Score max={max_score}")

    return "\n".join(lines)


def _render_json(report: CollectionReport) -> str:
    """Mode JSON : dump structure complet."""
    data = {
        "topic": report.topic,
        "query_type": report.query_type,
        "domain_id": report.domain_id,
        "time_range": report.time_range,
        "range_from": report.range_from,
        "range_to": report.range_to,
        "collected_at": report.collected_at,
        "stats": report.stats,
        "articles": [a.to_dict() for a in report.articles],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _render_md(report: CollectionReport) -> str:
    """Mode markdown : rapport complet."""
    lines = []

    lines.append(f"# Rapport de veille : {report.topic}")
    lines.append("")
    lines.append(f"**Type** : {report.query_type}")
    if report.domain_id:
        lines.append(f"**Domaine** : {report.domain_id}")
    lines.append(f"**Periode** : {report.range_from} - {report.range_to}")
    lines.append(f"**Collecte** : {report.collected_at}")
    lines.append(f"**Articles** : {len(report.articles)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Articles groupes par source
    articles_sorted = sorted(report.articles, key=lambda a: a.source_id)
    for source_id, group in groupby(articles_sorted, key=lambda a: a.source_id):
        items = list(group)
        source_name = items[0].source_name if items else source_id
        lines.append(f"## {source_name}")
        lines.append("")

        for a in items:
            lines.append(f"### [{a.title}]({a.url})")
            lines.append("")
            if a.author:
                lines.append(f"**Auteur** : {a.author}")
            if a.published:
                lines.append(f"**Date** : {a.published[:10]}")

            eng_parts = []
            if a.engagement.points is not None:
                eng_parts.append(f"Points: {a.engagement.points}")
            if a.engagement.num_comments is not None:
                eng_parts.append(f"Commentaires: {a.engagement.num_comments}")
            if eng_parts:
                lines.append(f"**Engagement** : {', '.join(eng_parts)}")

            lines.append(f"**Score** : {a.score}/100")

            if a.cross_refs:
                lines.append(f"**Cross-source** : {', '.join(a.cross_refs)}")

            lines.append("")
            if a.summary:
                lines.append(a.summary)
                lines.append("")

            if a.tags:
                lines.append(f"Tags: {', '.join(a.tags)}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Statistiques
    lines.append("## Statistiques")
    lines.append("")
    for k, v in report.stats.items():
        lines.append(f"- **{k}** : {v}")
    lines.append("")

    return "\n".join(lines)
