"""Collecteur RSS/Atom via feedparser.

Porte depuis veille-ia.py avec adaptation a l'interface BaseCollector.

Usage:
    python3 collectors/rss.py '{"keywords":["LLM"],"time_range":"7d","max_results":5,"config":{"feeds":[{"url":"https://simonwillison.net/atom/entries/","name":"Simon Willison"}]}}'
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

import feedparser

from collectors.base import Article, BaseCollector


class RSSCollector(BaseCollector):
    SOURCE_ID = "rss"
    SOURCE_NAME = "RSS/Atom"

    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        config = kwargs.get("config", {})
        feeds: list[dict] = config.get("feeds", [])

        if not feeds:
            print("[rss] Aucun feed configure", flush=True)
            return []

        seconds = self.parse_time_range(time_range)
        cutoff = time.time() - seconds
        pattern = self._build_pattern(keywords)

        articles: list[Article] = []

        for feed_cfg in feeds:
            url = feed_cfg.get("url", "")
            feed_name = feed_cfg.get("name", "")
            if not url:
                continue

            entries = self._fetch_feed(url, feed_name)
            for entry in entries:
                published_ts = self._parse_date(entry)
                if published_ts and published_ts < cutoff:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")[:500]

                if pattern and not pattern.search(f"{title} {summary}"):
                    continue

                published_iso = ""
                if published_ts:
                    published_iso = datetime.fromtimestamp(
                        published_ts, tz=timezone.utc
                    ).isoformat()

                articles.append(
                    Article(
                        title=title,
                        url=entry.get("link", ""),
                        source_id=self.SOURCE_ID,
                        source_name=f"RSS: {feed_name}" if feed_name else self.SOURCE_NAME,
                        published=published_iso,
                        summary=self._clean_html(summary),
                        author=entry.get("author", ""),
                        score=0.0,
                        tags=[t.get("term", "") for t in entry.get("tags", [])],
                        metadata={"feed_url": url, "feed_name": feed_name},
                    )
                )

                if len(articles) >= max_results:
                    return articles

        return articles

    def _fetch_feed(self, url: str, name: str) -> list[dict]:
        """Telecharge et parse un feed RSS/Atom."""
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                print(f"[rss] Erreur {resp.status_code} sur {url}", flush=True)
                return []

            feed = feedparser.parse(resp.content)
            if not feed.entries:
                print(f"[rss] Aucune entree pour {name or url}", flush=True)
                return []

            return feed.entries
        except Exception as e:
            print(f"[rss] Erreur sur {url}: {e}", flush=True)
            return []

    @staticmethod
    def _parse_date(entry: dict) -> float | None:
        """Extrait le timestamp d'une entree RSS."""
        for field in ("published_parsed", "updated_parsed"):
            parsed = entry.get(field)
            if parsed:
                try:
                    return time.mktime(parsed)
                except (TypeError, ValueError, OverflowError):
                    continue
        return None

    @staticmethod
    def _build_pattern(keywords: list[str]) -> re.Pattern | None:
        """Construit une regex OR a partir des mots-cles."""
        if not keywords:
            return None
        escaped = [re.escape(kw) for kw in keywords]
        return re.compile("|".join(escaped), re.IGNORECASE)

    @staticmethod
    def _clean_html(text: str) -> str:
        """Retire les balises HTML basiques."""
        return re.sub(r"<[^>]+>", "", text).strip()


if __name__ == "__main__":
    RSSCollector.cli_main()
