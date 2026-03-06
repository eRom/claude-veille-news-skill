#!/usr/bin/env python3
"""What About — Orchestrateur principal de veille technologique.

Usage:
    python3 scripts/whatabout.py "topic ou domaine" [options]

Options:
    --domain=ID               ID domaine depuis domains.json
    --time=24h|7d|30d         Default: 7d
    --sources=hn,rss          Filtre sources (default: toutes actives)
    --depth=quick|standard|deep  Default: deep
    --max=N                   Max articles total
    --agent                   Mode agent (pas d'output interactif)
    --debug                   Logs verbose sur stderr
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Ajouter le repertoire racine au path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Charger .env si present
_env_file = ROOT_DIR / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key, _val = _key.strip(), _val.strip()
                if _key and _val:
                    os.environ.setdefault(_key, _val)

from scripts.lib.normalize import normalize_collector_output, ScoredArticle
from scripts.lib.score import score_articles
from scripts.lib.dedupe import dedupe_articles, cross_source_link
from scripts.lib.render import render, CollectionReport


def debug_log(msg: str, is_debug: bool) -> None:
    if is_debug:
        print(f"[debug] {msg}", file=sys.stderr, flush=True)


def load_all_config(root: Path) -> dict:
    """Charge tous les fichiers de configuration."""
    config_dir = root / "config"
    result = {}
    for name in ("sources", "domains", "settings"):
        path = config_dir / f"{name}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                result[name] = json.load(f)
        else:
            result[name] = {}
    return result


def find_domain(topic: str, domains_config: dict) -> dict | None:
    """Cherche un domaine par ID ou nom (fuzzy match)."""
    domains = domains_config.get("domains", [])
    topic_lower = topic.lower().strip()

    # Match exact par ID
    for d in domains:
        if d["id"] == topic_lower:
            return d

    # Match par nom (case-insensitive)
    for d in domains:
        if d["name"].lower() == topic_lower:
            return d

    # Match partiel
    for d in domains:
        if topic_lower in d["id"] or topic_lower in d["name"].lower():
            return d

    return None


def extract_keywords(topic: str) -> dict:
    """Extrait des keywords depuis un sujet libre (mode research)."""
    words = topic.split()
    return {
        "primary": words,
        "secondary": [],
        "exclude": [],
    }


def discover_collectors(source_filter: list[str] | None, sources_config: dict, root: Path) -> list[dict]:
    """Decouvre les collecteurs disponibles et actifs."""
    available = []
    for src in sources_config.get("sources", []):
        if not src.get("enabled", False):
            continue

        if source_filter and src["id"] not in source_filter:
            continue

        collector_path = root / src["collector"]
        if not collector_path.exists():
            continue

        available.append(src)

    return available


def collect_one(source: dict, keywords: list[str], time_range: str, max_results: int, root: Path, is_debug: bool) -> dict | None:
    """Execute un collecteur et retourne sa sortie JSON."""
    collector_path = root / source["collector"]

    try:
        # Import dynamique du module collecteur
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"collector_{source['id']}", str(collector_path))
        if spec is None or spec.loader is None:
            debug_log(f"[{source['id']}] Impossible de charger {collector_path}", is_debug)
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Trouver la sous-classe de BaseCollector
        from collectors.base import BaseCollector
        collector_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseCollector) and attr is not BaseCollector:
                collector_class = attr
                break

        if collector_class is None:
            debug_log(f"[{source['id']}] Aucun collecteur trouve dans {collector_path}", is_debug)
            return None

        # Instancier et collecter
        collector = collector_class()
        config = source.get("config", {})
        articles = collector.collect(
            keywords=keywords,
            time_range=time_range,
            max_results=max_results,
            config=config,
        )

        # Serialiser comme le fait to_json()
        result = {
            "source_id": collector.SOURCE_ID,
            "source_name": collector.SOURCE_NAME,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "count": len(articles),
            "articles": [a.to_dict() for a in articles],
        }

        debug_log(f"[{source['id']}] {len(articles)} articles collectes", is_debug)
        return result

    except Exception as e:
        debug_log(f"[{source['id']}] Erreur: {e}", is_debug)
        return None


def collect_parallel(
    sources: list[dict],
    keywords: list[str],
    time_range: str,
    max_per_source: int,
    depth: str,
    root: Path,
    is_debug: bool,
) -> list[dict]:
    """Collecte en parallele depuis toutes les sources."""
    timeouts = {"quick": 20, "standard": 45, "deep": 60}
    timeout = timeouts.get(depth, 45)

    results = []
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {
            executor.submit(collect_one, src, keywords, time_range, max_per_source, root, is_debug): src
            for src in sources
        }

        for future in as_completed(futures, timeout=timeout):
            src = futures[future]
            try:
                result = future.result(timeout=5)
                if result:
                    results.append(result)
            except Exception as e:
                debug_log(f"[{src['id']}] Timeout ou erreur: {e}", is_debug)

    return results


def build_report(
    topic: str,
    query_type: str,
    domain_id: str | None,
    time_range: str,
    articles: list[ScoredArticle],
    collected_at: str,
) -> CollectionReport:
    """Construit le rapport final."""
    from scripts.lib.dates import time_range_to_seconds

    now = datetime.now(timezone.utc)
    seconds = time_range_to_seconds(time_range)
    range_from = datetime.fromtimestamp(now.timestamp() - seconds, tz=timezone.utc).strftime("%Y-%m-%d")
    range_to = now.strftime("%Y-%m-%d")

    # Calculer les stats
    source_counts: dict[str, int] = {}
    for a in articles:
        source_counts[a.source_id] = source_counts.get(a.source_id, 0) + 1

    cross_count = sum(1 for a in articles if a.cross_refs)
    max_score = max((a.score for a in articles), default=0)

    stats = {
        "sources_count": len(source_counts),
        "total_articles": len(articles),
        "cross_source": cross_count,
        "max_score": max_score,
        **{f"source_{k}": v for k, v in source_counts.items()},
    }

    return CollectionReport(
        topic=topic,
        query_type=query_type,
        domain_id=domain_id,
        time_range=time_range,
        range_from=range_from,
        range_to=range_to,
        articles=articles,
        stats=stats,
        collected_at=collected_at,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="What About — Orchestrateur de veille")
    parser.add_argument("topic", help="Sujet ou domaine de recherche")
    parser.add_argument("--domain", default=None, help="ID domaine depuis domains.json")
    parser.add_argument("--time", default=None, help="Periode (24h, 7d, 30d)")
    parser.add_argument("--sources", default=None, help="Sources filtrees (ex: hn,rss)")
    parser.add_argument("--depth", choices=["quick", "standard", "deep"], default="deep")
    parser.add_argument("--emit", choices=["compact", "json", "md"], default="compact")
    parser.add_argument("--max", type=int, default=None, help="Max articles total")
    parser.add_argument("--agent", action="store_true", help="Mode agent")
    parser.add_argument("--debug", action="store_true", help="Logs verbose sur stderr")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_all_config(ROOT_DIR)

    settings = config.get("settings", {})
    collection_settings = settings.get("collection", {})

    # Resoudre domaine ou keywords
    domain = None
    if args.domain:
        domain = find_domain(args.domain, config["domains"])
    else:
        domain = find_domain(args.topic, config["domains"])

    # Keywords
    if domain:
        keywords = domain["keywords"]
        keyword_list = keywords.get("primary", []) + keywords.get("secondary", [])
    else:
        keywords = extract_keywords(args.topic)
        keyword_list = keywords.get("primary", [])

    # Time range
    time_range = args.time or collection_settings.get("default_time_range", "7d")

    # Max articles par source
    max_per_source = args.max or collection_settings.get("max_articles_per_source", 20)

    # Filtrer sources
    source_filter = None
    if args.sources:
        source_filter = [s.strip() for s in args.sources.split(",")]

    debug_log(f"Topic: {args.topic} | Time: {time_range} | Keywords: {keyword_list}", args.debug)

    # Decouvrir collecteurs
    available = discover_collectors(source_filter, config["sources"], ROOT_DIR)
    if not available:
        print(json.dumps({"error": "Aucun collecteur disponible"}), file=sys.stderr)
        sys.exit(1)

    debug_log(f"Collecteurs: {[s['id'] for s in available]}", args.debug)

    # Collecter en parallele
    raw_results = collect_parallel(available, keyword_list, time_range, max_per_source, args.depth, ROOT_DIR, args.debug)

    if not raw_results:
        print(json.dumps({"error": "Aucun resultat collecte"}), file=sys.stderr)
        sys.exit(1)

    # Pipeline
    all_articles: list[ScoredArticle] = []
    for raw in raw_results:
        all_articles.extend(normalize_collector_output(raw))

    debug_log(f"Articles normalises: {len(all_articles)}", args.debug)

    # Score
    all_articles = score_articles(all_articles, keywords, settings, time_range)

    # Dedup
    threshold = collection_settings.get("dedup_similarity_threshold", 0.85)
    all_articles = dedupe_articles(all_articles, threshold=threshold)

    debug_log(f"Articles apres dedup: {len(all_articles)}", args.debug)

    # Cross-source link
    cross_source_link(all_articles, threshold=0.4)

    # Tri final par score desc
    all_articles.sort(key=lambda a: -a.score)

    # Limiter au max total
    max_total = args.max or collection_settings.get("max_articles_total", 100)
    all_articles = all_articles[:max_total]

    # Construire et rendre le rapport
    collected_at = datetime.now(timezone.utc).isoformat()
    topic_display = domain["name"] if domain else args.topic
    domain_id = domain["id"] if domain else None
    query_type = "domain" if domain else "topic"

    report = build_report(topic_display, query_type, domain_id, time_range, all_articles, collected_at)
    output = render(report, args.emit)

    print(output)


if __name__ == "__main__":
    main()
