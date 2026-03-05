"""Collecteur arXiv via l'API Atom publique.

Usage:
    python3 collectors/arxiv.py '{"keywords":["LLM","transformer"],"time_range":"7d","max_results":10}'
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.base import Article, BaseCollector

ARXIV_API_URL = "http://export.arxiv.org/api/query"

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivCollector(BaseCollector):
    SOURCE_ID = "arxiv"
    SOURCE_NAME = "arXiv"

    def _build_query(self, keywords: list[str], categories: list[str]) -> str:
        """Construit la query arXiv a partir des keywords et categories."""
        parts: list[str] = []

        if keywords:
            kw_query = " OR ".join(f"all:{kw}" for kw in keywords)
            parts.append(f"({kw_query})")

        if categories:
            cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
            parts.append(f"({cat_query})")

        return " AND ".join(parts) if parts else "all:*"

    def _clean_text(self, text: str | None) -> str:
        """Nettoie un texte XML (supprime newlines superflues, strip)."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def _extract_arxiv_id(self, entry_id: str) -> str:
        """Extrait l'ID arXiv depuis l'URL id (ex: http://arxiv.org/abs/2401.12345v1)."""
        match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?$", entry_id)
        return match.group(1) if match else entry_id.split("/")[-1]

    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        categories = kwargs.get("categories", ["cs.AI", "cs.CL", "cs.LG"])
        sort_by = kwargs.get("sort_by", "submittedDate")
        sort_order = kwargs.get("sort_order", "descending")

        query = self._build_query(keywords, categories)
        seconds = self.parse_time_range(time_range)
        cutoff = datetime.now(timezone.utc).timestamp() - seconds

        params = {
            "search_query": query,
            "start": 0,
            "max_results": min(max_results, 100),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        try:
            resp = self.session.get(ARXIV_API_URL, params=params, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"[arxiv] Erreur API: {e}", file=sys.stderr, flush=True)
            return []

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            print(f"[arxiv] Erreur parsing XML: {e}", file=sys.stderr, flush=True)
            return []

        articles: list[Article] = []

        for entry in root.findall(f"{ATOM_NS}entry"):
            # Published date
            published_el = entry.find(f"{ATOM_NS}published")
            published_str = published_el.text.strip() if published_el is not None and published_el.text else ""

            # Filtrer par time_range
            if published_str:
                try:
                    pub_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    if pub_dt.timestamp() < cutoff:
                        continue
                except ValueError:
                    pass

            # Title
            title_el = entry.find(f"{ATOM_NS}title")
            title = self._clean_text(title_el.text if title_el is not None else "")

            # URL : lien alternate ou id
            url = ""
            for link in entry.findall(f"{ATOM_NS}link"):
                if link.get("rel") == "alternate":
                    url = link.get("href", "")
                    break
            if not url:
                id_el = entry.find(f"{ATOM_NS}id")
                url = id_el.text.strip() if id_el is not None and id_el.text else ""

            # Summary
            summary_el = entry.find(f"{ATOM_NS}summary")
            summary = self._clean_text(summary_el.text if summary_el is not None else "")
            if len(summary) > 500:
                summary = summary[:497] + "..."

            # Authors
            authors = []
            for author_el in entry.findall(f"{ATOM_NS}author"):
                name_el = author_el.find(f"{ATOM_NS}name")
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())
            if len(authors) >= 4:
                author = authors[0]
            else:
                author = ", ".join(authors)

            # Categories / tags
            tags = []
            for cat_el in entry.findall(f"{ATOM_NS}category"):
                term = cat_el.get("term", "")
                if term:
                    tags.append(term)

            # arXiv ID et PDF URL
            entry_id_el = entry.find(f"{ATOM_NS}id")
            entry_id = entry_id_el.text.strip() if entry_id_el is not None and entry_id_el.text else ""
            arxiv_id = self._extract_arxiv_id(entry_id)

            pdf_url = ""
            for link in entry.findall(f"{ATOM_NS}link"):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break
            if not pdf_url and arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

            articles.append(
                Article(
                    title=title,
                    url=url,
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    published=published_str,
                    summary=summary,
                    author=author,
                    score=0.0,
                    tags=tags,
                    metadata={
                        "arxiv_id": arxiv_id,
                        "categories": tags[:],
                        "pdf_url": pdf_url,
                    },
                )
            )

        return articles[:max_results]


if __name__ == "__main__":
    ArxivCollector.cli_main()
