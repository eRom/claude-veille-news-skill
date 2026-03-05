"""Deduplication et cross-source linking des articles."""

from __future__ import annotations

import re
from scripts.lib.normalize import ScoredArticle


def normalize_text(text: str) -> str:
    """Normalise un texte pour la comparaison."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _trigrams(text: str) -> set[str]:
    """Genere les trigrams d'un texte."""
    t = normalize_text(text)
    if len(t) < 3:
        return {t}
    return {t[i : i + 3] for i in range(len(t) - 2)}


def _tokens(text: str) -> set[str]:
    """Genere les tokens (mots) d'un texte."""
    return set(normalize_text(text).split())


def jaccard_similarity(set1: set, set2: set) -> float:
    """Similarite Jaccard entre deux ensembles."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def _token_jaccard(text_a: str, text_b: str) -> float:
    """Similarite Jaccard basee sur les mots."""
    return jaccard_similarity(_tokens(text_a), _tokens(text_b))


def _trigram_jaccard(text_a: str, text_b: str) -> float:
    """Similarite Jaccard basee sur les trigrams."""
    return jaccard_similarity(_trigrams(text_a), _trigrams(text_b))


def _hybrid_similarity(a: str, b: str) -> float:
    """Similarite hybride : max(trigram, token)."""
    return max(_trigram_jaccard(a, b), _token_jaccard(a, b))


def _url_match(url_a: str, url_b: str) -> bool:
    """Verifie si deux URLs pointent vers le meme contenu (ignore query params)."""
    def clean(u: str) -> str:
        u = u.split("?")[0].split("#")[0].rstrip("/")
        u = re.sub(r"^https?://(?:www\.)?", "", u)
        return u.lower()

    a, b = clean(url_a), clean(url_b)
    return a == b and a != ""


def dedupe_articles(articles: list[ScoredArticle], threshold: float = 0.7) -> list[ScoredArticle]:
    """Supprime les doublons, garde l'article avec le meilleur score."""
    if not articles:
        return []

    keep: list[ScoredArticle] = []

    for article in articles:
        is_dup = False
        for kept in keep:
            if _url_match(article.url, kept.url):
                is_dup = True
                break
            sim = _hybrid_similarity(article.title, kept.title)
            if sim >= threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(article)

    return keep


def cross_source_link(articles: list[ScoredArticle], threshold: float = 0.4) -> None:
    """Annote les articles mentionnes sur 2+ sources (in-place)."""
    n = len(articles)
    for i in range(n):
        for j in range(i + 1, n):
            if articles[i].source_id == articles[j].source_id:
                continue

            sim = _hybrid_similarity(articles[i].title, articles[j].title)
            if sim >= threshold or _url_match(articles[i].url, articles[j].url):
                a_name = articles[i].source_name
                b_name = articles[j].source_name

                if b_name not in articles[i].cross_refs:
                    articles[i].cross_refs.append(b_name)
                if a_name not in articles[j].cross_refs:
                    articles[j].cross_refs.append(a_name)
