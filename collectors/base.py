"""Base abstraite pour tous les collecteurs What About."""

from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests


@dataclass
class Article:
    """Un article collecté depuis une source."""

    title: str
    url: str
    source_id: str
    source_name: str
    published: str = ""
    summary: str = ""
    author: str = ""
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseCollector(ABC):
    """Interface commune pour tous les collecteurs."""

    SOURCE_ID: str = ""
    SOURCE_NAME: str = ""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )

    @abstractmethod
    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        """Collecte des articles selon les criteres donnes.

        Args:
            keywords: Mots-cles de recherche.
            time_range: Periode (ex: "24h", "7d", "30d").
            max_results: Nombre max d'articles a retourner.

        Returns:
            Liste d'Articles.
        """
        ...

    def to_json(self, articles: list[Article]) -> str:
        """Serialise une liste d'articles en JSON."""
        return json.dumps(
            {
                "source_id": self.SOURCE_ID,
                "source_name": self.SOURCE_NAME,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "count": len(articles),
                "articles": [a.to_dict() for a in articles],
            },
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def parse_time_range(time_range: str) -> int:
        """Convertit une duree texte en secondes."""
        unit = time_range[-1]
        value = int(time_range[:-1])
        multipliers = {"h": 3600, "d": 86400, "w": 604800}
        return value * multipliers.get(unit, 86400)

    @classmethod
    def cli_main(cls) -> None:
        """Point d'entree CLI standard : python3 collectors/xxx.py '<json_params>'"""
        if len(sys.argv) < 2:
            print(
                json.dumps({"error": "Usage: python3 collectors/xxx.py '<json_params>'"}),
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            params = json.loads(sys.argv[1])
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"JSON invalide: {e}"}), file=sys.stderr)
            sys.exit(1)

        collector = cls()
        articles = collector.collect(
            keywords=params.get("keywords", []),
            time_range=params.get("time_range", "7d"),
            max_results=params.get("max_results", 20),
            **{k: v for k, v in params.items() if k not in ("keywords", "time_range", "max_results")},
        )
        print(collector.to_json(articles))
