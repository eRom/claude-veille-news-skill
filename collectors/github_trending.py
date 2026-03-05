"""Collecteur GitHub Trending via GitHub Search API.

Utilise l'API Search repos triee par etoiles pour approximer les trending repos.
Supporte l'auth via variable d'env GITHUB_TOKEN pour un meilleur rate limit.

Usage:
    python3 collectors/github_trending.py '{"keywords":["LLM","AI agent"],"time_range":"7d","max_results":10}'
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.base import Article, BaseCollector

GH_SEARCH_URL = "https://api.github.com/search/repositories"


class GitHubTrendingCollector(BaseCollector):
    SOURCE_ID = "github_trending"
    SOURCE_NAME = "GitHub Trending"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "WhatAbout-Collector/1.0",
            }
        )
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"token {token}"

    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        # Calcul de la date limite depuis time_range
        seconds = self.parse_time_range(time_range)
        since_date = (
            datetime.now(timezone.utc) - timedelta(seconds=seconds)
        ).strftime("%Y-%m-%d")

        # Langages depuis la config ou kwargs
        config = kwargs.get("config", {})
        languages = config.get("languages", ["python", "typescript", "rust"])

        # Delai entre requetes (ms -> s)
        rate_limit = kwargs.get("rate_limit", {})
        delay_s = rate_limit.get("delay_between_ms", 1000) / 1000.0

        # Construction de la base de la query avec keywords
        keyword_part = " OR ".join(keywords) if keywords else ""

        seen_urls: set[str] = set()
        articles: list[Article] = []

        for i, lang in enumerate(languages):
            if i > 0:
                time.sleep(delay_s)

            # Build query: "keyword1 OR keyword2 created:>YYYY-MM-DD language:python"
            q_parts = []
            if keyword_part:
                q_parts.append(keyword_part)
            q_parts.append(f"created:>{since_date}")
            q_parts.append(f"language:{lang}")
            query = " ".join(q_parts)

            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": min(max_results, 100),
            }

            try:
                resp = self.session.get(GH_SEARCH_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(
                    f"[github_trending] Erreur API (lang={lang}): {e}",
                    file=sys.stderr,
                    flush=True,
                )
                continue

            for repo in data.get("items", []):
                url = repo.get("html_url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Tags: language + topics (max 5)
                tags = []
                repo_lang = repo.get("language")
                if repo_lang:
                    tags.append(repo_lang)
                topics = repo.get("topics", []) or []
                for t in topics[:5]:
                    if t not in tags:
                        tags.append(t)

                # Summary tronque a 500 chars
                description = repo.get("description") or ""
                if len(description) > 500:
                    description = description[:497] + "..."

                articles.append(
                    Article(
                        title=repo.get("full_name", ""),
                        url=url,
                        source_id=self.SOURCE_ID,
                        source_name=self.SOURCE_NAME,
                        published=repo.get("created_at", ""),
                        summary=description,
                        author=repo.get("owner", {}).get("login", ""),
                        score=float(repo.get("stargazers_count", 0)),
                        tags=tags,
                        metadata={
                            "github_id": repo.get("id", 0),
                            "stars": repo.get("stargazers_count", 0),
                            "forks": repo.get("forks_count", 0),
                            "language": repo_lang or "",
                            "open_issues": repo.get("open_issues_count", 0),
                            "watchers": repo.get("watchers_count", 0),
                        },
                    )
                )

        # Trier par score (etoiles) decroissant et limiter
        articles.sort(key=lambda a: a.score, reverse=True)
        return articles[:max_results]


if __name__ == "__main__":
    GitHubTrendingCollector.cli_main()
