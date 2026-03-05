"""What About — Collecteurs multi-sources pour veille technologique."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from collectors.base import Article, BaseCollector

__all__ = ["Article", "BaseCollector", "discover"]

COLLECTORS_DIR = Path(__file__).resolve().parent


def discover(sources_config: dict | None = None) -> list[tuple[str, type, dict]]:
    """Decouvre les collecteurs disponibles et leur config.

    Scanne les .py dans collectors/, importe dynamiquement,
    cherche les sous-classes de BaseCollector.
    Croise avec sources.json pour le statut enabled et la config.

    Args:
        sources_config: Contenu de sources.json. Si None, charge le fichier.

    Returns:
        Liste de (source_id, collector_class, source_config)
    """
    if sources_config is None:
        config_path = COLLECTORS_DIR.parent / "config" / "sources.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                sources_config = json.load(f)
        else:
            sources_config = {}

    # Index des sources par collector path
    source_by_id: dict[str, dict] = {}
    for src in sources_config.get("sources", []):
        source_by_id[src["id"]] = src

    result: list[tuple[str, type, dict]] = []

    for py_file in sorted(COLLECTORS_DIR.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "base.py":
            continue

        try:
            spec = importlib.util.spec_from_file_location(
                f"collectors.{py_file.stem}", str(py_file)
            )
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseCollector)
                    and attr is not BaseCollector
                ):
                    source_id = attr.SOURCE_ID
                    src_cfg = source_by_id.get(source_id, {})

                    if not src_cfg.get("enabled", False):
                        continue

                    result.append((source_id, attr, src_cfg))

        except Exception:
            continue

    return result
