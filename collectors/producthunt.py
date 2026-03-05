"""Collecteur Product Hunt via API GraphQL ou RSS fallback.

Usage:
    python3 collectors/producthunt.py '{"keywords":["AI","developer tools"],"time_range":"7d","max_results":10}'

Auth:
    Export PRODUCTHUNT_TOKEN (Developer Token depuis producthunt.com/v2/oauth/applications)
    Sans token, le collecteur utilise le flux RSS public en fallback.
"""

from __future__ import annotations

import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.base import Article, BaseCollector

PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"
PH_RSS_URL = "https://www.producthunt.com/feed"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

POSTS_QUERY = """
query($postedAfter: DateTime!, $first: Int!) {
  posts(order: VOTES, postedAfter: $postedAfter, first: $first) {
    edges {
      node {
        id
        name
        tagline
        description
        url
        votesCount
        commentsCount
        createdAt
        topics { edges { node { name } } }
        makers { name }
        website
      }
    }
  }
}
"""


class ProductHuntCollector(BaseCollector):
    SOURCE_ID = "producthunt"
    SOURCE_NAME = "Product Hunt"

    def __init__(self) -> None:
        super().__init__()
        self.token = os.environ.get("PRODUCTHUNT_TOKEN", "")

    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        if self.token:
            print("[producthunt] Mode API GraphQL (token detecte)", file=sys.stderr, flush=True)
            return self._collect_api(keywords, time_range, max_results)
        else:
            print("[producthunt] Mode RSS fallback (pas de token)", file=sys.stderr, flush=True)
            return self._collect_rss(keywords, time_range, max_results)

    # ------------------------------------------------------------------
    # Mode API GraphQL
    # ------------------------------------------------------------------

    def _collect_api(
        self,
        keywords: list[str],
        time_range: str,
        max_results: int,
    ) -> list[Article]:
        seconds = self.parse_time_range(time_range)
        posted_after = datetime.fromtimestamp(
            time.time() - seconds, tz=timezone.utc
        ).isoformat()

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        payload = {
            "query": POSTS_QUERY,
            "variables": {
                "postedAfter": posted_after,
                "first": min(max_results * 3, 50),  # fetch more to allow filtering
            },
        }

        try:
            resp = self.session.post(
                PH_GRAPHQL_URL, json=payload, headers=headers, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[producthunt] Erreur API GraphQL: {e}", file=sys.stderr, flush=True)
            return []

        edges = (
            data.get("data", {}).get("posts", {}).get("edges", [])
        )

        articles: list[Article] = []
        seen_urls: set[str] = set()
        kw_lower = [k.lower() for k in keywords] if keywords else []

        for edge in edges:
            node = edge.get("node", {})
            name = node.get("name", "")
            tagline = node.get("tagline", "")
            description = node.get("description", "") or ""

            # Filtrage par keywords cote client
            if kw_lower:
                haystack = f"{name} {tagline} {description}".lower()
                if not any(kw in haystack for kw in kw_lower):
                    continue

            website = node.get("website", "") or ""
            ph_url = node.get("url", "") or ""
            url = website if website else ph_url
            if not url:
                continue

            # Dedup par URL
            if url in seen_urls:
                continue
            seen_urls.add(url)

            topics = [
                t["node"]["name"]
                for t in node.get("topics", {}).get("edges", [])
                if t.get("node", {}).get("name")
            ]
            makers = node.get("makers", []) or []
            author = makers[0].get("name", "") if makers else ""

            articles.append(
                Article(
                    title=f"{name} — {tagline}" if tagline else name,
                    url=url,
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    published=node.get("createdAt", ""),
                    summary=description[:500],
                    author=author,
                    score=float(node.get("votesCount", 0)),
                    tags=topics,
                    metadata={
                        "ph_id": node.get("id", ""),
                        "votes": node.get("votesCount", 0),
                        "comments": node.get("commentsCount", 0),
                        "ph_url": ph_url,
                        "tagline": tagline,
                    },
                )
            )

            if len(articles) >= max_results:
                break

        return articles

    # ------------------------------------------------------------------
    # Mode RSS fallback
    # ------------------------------------------------------------------

    def _collect_rss(
        self,
        keywords: list[str],
        time_range: str,
        max_results: int,
    ) -> list[Article]:
        try:
            resp = self.session.get(PH_RSS_URL, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[producthunt] Erreur RSS: {e}", file=sys.stderr, flush=True)
            return []

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            print(f"[producthunt] Erreur parsing RSS: {e}", file=sys.stderr, flush=True)
            return []

        seconds = self.parse_time_range(time_range)
        cutoff = time.time() - seconds
        kw_lower = [k.lower() for k in keywords] if keywords else []

        articles: list[Article] = []
        seen_urls: set[str] = set()

        for entry in root.findall(f"{ATOM_NS}entry"):
            title_el = entry.find(f"{ATOM_NS}title")
            title = title_el.text.strip() if title_el is not None and title_el.text else ""

            link_el = entry.find(f"{ATOM_NS}link")
            url = link_el.get("href", "") if link_el is not None else ""
            if not url:
                continue

            summary_el = entry.find(f"{ATOM_NS}summary") or entry.find(f"{ATOM_NS}content")
            summary = ""
            if summary_el is not None and summary_el.text:
                summary = summary_el.text.strip()[:500]

            # Filtrage par keywords
            if kw_lower:
                haystack = f"{title} {summary}".lower()
                if not any(kw in haystack for kw in kw_lower):
                    continue

            # Filtrage par date
            published_el = entry.find(f"{ATOM_NS}published") or entry.find(f"{ATOM_NS}updated")
            published = ""
            if published_el is not None and published_el.text:
                published = published_el.text.strip()
                try:
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if pub_dt.timestamp() < cutoff:
                        continue
                except (ValueError, OSError):
                    pass

            # Dedup par URL
            if url in seen_urls:
                continue
            seen_urls.add(url)

            articles.append(
                Article(
                    title=title,
                    url=url,
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    published=published,
                    summary=summary,
                    author="",
                    score=0.0,
                    tags=[],
                    metadata={"ph_url": url},
                )
            )

            if len(articles) >= max_results:
                break

        return articles


if __name__ == "__main__":
    ProductHuntCollector.cli_main()
