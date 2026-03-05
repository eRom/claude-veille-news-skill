"""Collecteur Perplexity Sonar Pro — recherche web augmentee.

Usage:
    python3 collectors/perplexity.py '{"keywords":["LLM","AI agent"],"time_range":"7d","max_results":10}'

Necessite la variable d'environnement PERPLEXITY_API_KEY.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.base import Article, BaseCollector

SONAR_API_URL = "https://api.perplexity.ai/chat/completions"

TIME_RANGE_LABELS = {
    "24h": "last 24 hours",
    "1d": "last 24 hours",
    "3d": "last 3 days",
    "7d": "last week",
    "14d": "last 2 weeks",
    "30d": "last month",
}


class PerplexityCollector(BaseCollector):
    SOURCE_ID = "perplexity"
    SOURCE_NAME = "Perplexity Sonar Pro"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = os.environ.get("PERPLEXITY_API_KEY", "")

    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        if not self.api_key:
            print("[perplexity] PERPLEXITY_API_KEY non definie, skip", flush=True)
            return []

        query = self._build_query(keywords, time_range)
        recency = self._map_recency(time_range)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a tech news research assistant. "
                        "Return relevant recent articles with their URLs. "
                        "Focus on quality sources: official blogs, research papers, "
                        "reputable tech publications. Be concise."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "max_tokens": 4096,
            "return_citations": True,
            "return_related_questions": False,
        }

        if recency:
            payload["search_recency_filter"] = recency

        try:
            resp = self.session.post(
                SONAR_API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[perplexity] Erreur API: {e}", flush=True)
            return []

        return self._parse_response(data, max_results)

    def _build_query(self, keywords: list[str], time_range: str) -> str:
        kw_str = ", ".join(keywords) if keywords else "technology"
        period = TIME_RANGE_LABELS.get(time_range, f"last {time_range}")
        return (
            f"Find the most important and recent articles, blog posts, and papers "
            f"about {kw_str} published in the {period}. "
            f"For each result, provide: title, URL, author if known, "
            f"and a one-sentence summary."
        )

    @staticmethod
    def _map_recency(time_range: str) -> str | None:
        """Mappe time_range vers le filtre recency Perplexity."""
        seconds = BaseCollector.parse_time_range(time_range)
        if seconds <= 86400:
            return "day"
        if seconds <= 7 * 86400:
            return "week"
        return "month"

    def _parse_response(self, data: dict, max_results: int) -> list[Article]:
        """Extrait les articles depuis la reponse Sonar Pro."""
        articles: list[Article] = []
        citations = data.get("citations", [])
        content = ""

        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        now_iso = datetime.now(timezone.utc).isoformat()

        # Chaque citation = 1 article
        for i, url in enumerate(citations[:max_results]):
            title = self._extract_title_for_citation(content, url, i)

            articles.append(
                Article(
                    title=title,
                    url=url,
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    published=now_iso,
                    summary=self._extract_snippet_for_citation(content, url, i),
                    author="",
                    score=0.0,
                    tags=[],
                    metadata={
                        "citation_index": i + 1,
                        "perplexity_model": "sonar-pro",
                    },
                )
            )

        return articles

    @staticmethod
    def _extract_title_for_citation(content: str, url: str, index: int) -> str:
        """Tente d'extraire le titre associe a une citation dans le contenu."""
        # Cherche un pattern markdown [titre](url) ou [titre][ref]
        # Sinon utilise le domaine comme fallback
        import re

        # Pattern: [Title](url)
        pattern = re.escape(url)
        match = re.search(rf"\[([^\]]+)\]\({pattern}\)", content)
        if match:
            return match.group(1).strip()

        # Pattern: reference numerotee [n] pres d'un titre
        ref_marker = f"[{index + 1}]"
        if ref_marker in content:
            pos = content.index(ref_marker)
            # Regarde le contexte autour de la reference
            start = max(0, pos - 200)
            context = content[start:pos]
            # Cherche la derniere ligne non vide avant la ref
            lines = [l.strip() for l in context.split("\n") if l.strip()]
            if lines:
                title_candidate = lines[-1]
                # Nettoie les marqueurs markdown
                title_candidate = re.sub(r"^[#*\-\d.]+\s*", "", title_candidate)
                title_candidate = re.sub(r"\[?\d+\]?\s*$", "", title_candidate)
                if len(title_candidate) > 10:
                    return title_candidate[:200]

        # Fallback: domaine
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "")
        return f"Article from {domain}"

    @staticmethod
    def _extract_snippet_for_citation(content: str, url: str, index: int) -> str:
        """Extrait un snippet contextuel pour la citation."""
        import re

        ref_marker = f"[{index + 1}]"
        if ref_marker not in content:
            return ""

        # Trouve toutes les occurrences de la reference
        positions = [m.start() for m in re.finditer(re.escape(ref_marker), content)]
        if not positions:
            return ""

        # Prend le contexte autour de la premiere occurrence
        pos = positions[0]
        # Cherche la phrase contenant la reference
        start = max(0, content.rfind(".", 0, pos) + 1)
        end = content.find(".", pos)
        if end == -1:
            end = min(len(content), pos + 200)
        else:
            end += 1

        snippet = content[start:end].strip()
        # Nettoie les marqueurs
        snippet = re.sub(r"\[\d+\]", "", snippet).strip()
        return snippet[:300] if snippet else ""


if __name__ == "__main__":
    PerplexityCollector.cli_main()
