"""Helpers dates et recency scoring."""

from __future__ import annotations

from datetime import datetime, timezone


def time_range_to_seconds(range_str: str) -> int:
    """Convertit une duree texte en secondes (ex: '7d' -> 604800)."""
    unit = range_str[-1]
    value = int(range_str[:-1])
    multipliers = {"h": 3600, "d": 86400, "w": 604800}
    return value * multipliers.get(unit, 86400)


def parse_iso(date_str: str) -> datetime | None:
    """Parse une date ISO 8601 en datetime UTC."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def recency_score(iso_date: str, time_range: str) -> int:
    """Score de recence 0-100. Plus l'article est recent dans la fenetre, plus le score est eleve."""
    dt = parse_iso(iso_date)
    if dt is None:
        return 0

    now = datetime.now(timezone.utc)
    age_seconds = (now - dt).total_seconds()
    window_seconds = time_range_to_seconds(time_range)

    if age_seconds <= 0:
        return 100
    if age_seconds >= window_seconds:
        return 0

    return int(100 * (1 - age_seconds / window_seconds))
