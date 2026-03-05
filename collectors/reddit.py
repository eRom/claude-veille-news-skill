"""Collecteur Reddit via API JSON publique (sans OAuth).

Usage:
    python3 collectors/reddit.py '{"keywords":["LLM","AI agent"],"time_range":"7d","max_results":10}'
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from typing import Any

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.base import Article, BaseCollector

REDDIT_SEARCH_URL = "https://www.reddit.com/r/{subreddit}/search.json"
REDDIT_USER_AGENT = "WhatAbout/1.0 (tech news aggregator)"

# Mapping time_range -> Reddit "t" param
TIME_RANGE_MAP = {
    "1h": "day",
    "6h": "day",
    "12h": "day",
    "24h": "day",
    "1d": "day",
    "3d": "week",
    "7d": "week",
    "14d": "month",
    "30d": "month",
}

DEFAULT_SUBREDDITS = ["MachineLearning", "LocalLLaMA", "artificial", "ClaudeAI"]


class RedditCollector(BaseCollector):
    SOURCE_ID = "reddit"
    SOURCE_NAME = "Reddit"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({"User-Agent": REDDIT_USER_AGENT})

    def _map_time_range(self, time_range: str) -> str:
        """Convertit le time_range du projet vers le param 't' de Reddit."""
        return TIME_RANGE_MAP.get(time_range, "week")

    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        query = " OR ".join(keywords) if keywords else ""
        reddit_time = self._map_time_range(time_range)

        # Config depuis kwargs (injecte par l'orchestrateur) ou valeurs par defaut
        config = kwargs.get("config", {})
        subreddits = config.get("subreddits", DEFAULT_SUBREDDITS)
        sort = config.get("sort", "relevance")

        # Rate limit delay
        rate_limit = kwargs.get("rate_limit", {})
        delay_ms = rate_limit.get("delay_between_ms", 1000)
        delay_s = delay_ms / 1000.0

        seen_urls: set[str] = set()
        articles: list[Article] = []

        for i, subreddit in enumerate(subreddits):
            if i > 0:
                time.sleep(delay_s)

            url = REDDIT_SEARCH_URL.format(subreddit=subreddit)
            params = {
                "q": query,
                "sort": sort,
                "t": reddit_time,
                "limit": min(max_results, 100),
                "restrict_sr": 1,
                "raw_json": 1,
            }

            try:
                resp = self.session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(
                    f"[reddit] Erreur API r/{subreddit}: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                continue

            children = data.get("data", {}).get("children", [])

            for child in children:
                post = child.get("data", {})
                if not post:
                    continue

                # URL : lien externe si dispo, sinon permalink Reddit
                post_url = post.get("url", "")
                if not post_url or post_url.startswith("/r/") or "reddit.com" in post_url:
                    permalink = post.get("permalink", "")
                    post_url = f"https://www.reddit.com{permalink}" if permalink else ""

                if not post_url or post_url in seen_urls:
                    continue
                seen_urls.add(post_url)

                # Timestamp -> ISO
                created_utc = post.get("created_utc", 0)
                published = ""
                if created_utc:
                    published = datetime.fromtimestamp(
                        created_utc, tz=timezone.utc
                    ).isoformat()

                # Selftext tronque a 500 chars
                selftext = (post.get("selftext") or "")[:500]

                # Tags : subreddit + flair
                tags = [subreddit]
                flair = post.get("link_flair_text")
                if flair:
                    tags.append(flair)

                articles.append(
                    Article(
                        title=post.get("title", ""),
                        url=post_url,
                        source_id=self.SOURCE_ID,
                        source_name=self.SOURCE_NAME,
                        published=published,
                        summary=selftext,
                        author=post.get("author", ""),
                        score=float(post.get("ups", 0)),
                        tags=tags,
                        metadata={
                            "reddit_id": post.get("id", ""),
                            "num_comments": post.get("num_comments", 0),
                            "subreddit": subreddit,
                            "upvote_ratio": post.get("upvote_ratio", 0.0),
                        },
                    )
                )

        return articles[:max_results]


if __name__ == "__main__":
    RedditCollector.cli_main()
