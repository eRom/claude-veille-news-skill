"""Collecteur Hacker News via Algolia API.

Usage:
    python3 collectors/hackernews.py '{"keywords":["LLM","AI agent"],"time_range":"7d","max_results":5}'
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from collectors.base import Article, BaseCollector

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsCollector(BaseCollector):
    SOURCE_ID = "hackernews"
    SOURCE_NAME = "Hacker News"

    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        query = " OR ".join(keywords) if keywords else ""
        seconds = self.parse_time_range(time_range)
        created_after = int(time.time()) - seconds

        params = {
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>{created_after}",
            "hitsPerPage": min(max_results, 50),
        }

        try:
            resp = self.session.get(HN_SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[hackernews] Erreur API: {e}", flush=True)
            return []

        articles: list[Article] = []
        for hit in data.get("hits", [])[:max_results]:
            created_at = hit.get("created_at", "")
            if not created_at and hit.get("created_at_i"):
                created_at = datetime.fromtimestamp(
                    hit["created_at_i"], tz=timezone.utc
                ).isoformat()

            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"

            articles.append(
                Article(
                    title=hit.get("title", ""),
                    url=url,
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    published=created_at,
                    summary=hit.get("story_text", "") or "",
                    author=hit.get("author", ""),
                    score=float(hit.get("points", 0)),
                    tags=[t for t in hit.get("_tags", []) if t != "story"],
                    metadata={
                        "hn_id": hit.get("objectID", ""),
                        "num_comments": hit.get("num_comments", 0),
                    },
                )
            )

        return articles


if __name__ == "__main__":
    HackerNewsCollector.cli_main()
