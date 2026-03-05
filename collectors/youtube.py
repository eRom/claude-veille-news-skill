"""Collecteur YouTube via Data API v3 ou RSS fallback.

Mode API (si YOUTUBE_API_KEY est definie) :
    Utilise l'endpoint search + videos pour recuperer les stats.

Mode RSS fallback (sinon) :
    Utilise les flux RSS par channel. Necessite des channels configures
    dans sources.json avec leur channel_id (pas un handle @).
    Les channel_id se trouvent via : https://www.youtube.com/channel/CHANNEL_ID
    ou via l'API YouTube / outils tiers.

Usage:
    python3 collectors/youtube.py '{"keywords":["LLM","AI agent"],"time_range":"7d","max_results":5}'
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

YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YT_RSS_URL = "https://www.youtube.com/feeds/videos.xml"

NS_ATOM = "{http://www.w3.org/2005/Atom}"
NS_MEDIA = "{http://search.yahoo.com/mrss/}"
NS_YT = "{http://www.youtube.com/xml/schemas/2015}"


class YouTubeCollector(BaseCollector):
    SOURCE_ID = "youtube"
    SOURCE_NAME = "YouTube"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = os.environ.get("YOUTUBE_API_KEY", "")

    def collect(
        self,
        keywords: list[str],
        time_range: str = "7d",
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[Article]:
        config = kwargs.get("config", {})

        if self.api_key:
            print("[youtube] Mode API (YOUTUBE_API_KEY detectee)", file=sys.stderr, flush=True)
            return self._collect_api(keywords, time_range, max_results)
        else:
            print("[youtube] Mode RSS fallback (pas de YOUTUBE_API_KEY)", file=sys.stderr, flush=True)
            return self._collect_rss(keywords, time_range, max_results, config)

    # ------------------------------------------------------------------
    # Mode API
    # ------------------------------------------------------------------

    def _collect_api(
        self,
        keywords: list[str],
        time_range: str,
        max_results: int,
    ) -> list[Article]:
        seconds = self.parse_time_range(time_range)
        published_after = datetime.fromtimestamp(
            time.time() - seconds, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        query = " ".join(keywords)
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "relevance",
            "maxResults": min(max_results, 50),
            "publishedAfter": published_after,
            "key": self.api_key,
        }

        try:
            resp = self.session.get(YT_SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[youtube] Erreur API search: {e}", file=sys.stderr, flush=True)
            return []

        items = data.get("items", [])
        if not items:
            return []

        # Extraire les video IDs pour le batch stats
        video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
        stats_map = self._fetch_video_stats(video_ids)

        articles: list[Article] = []
        seen_ids: set[str] = set()

        for item in items:
            video_id = item.get("id", {}).get("videoId", "")
            if not video_id or video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            snippet = item.get("snippet", {})
            stats = stats_map.get(video_id, {})

            view_count = int(stats.get("statistics", {}).get("viewCount", 0))
            like_count = int(stats.get("statistics", {}).get("likeCount", 0))
            comment_count = int(stats.get("statistics", {}).get("commentCount", 0))
            duration = stats.get("contentDetails", {}).get("duration", "")

            description = snippet.get("description", "")

            articles.append(
                Article(
                    title=snippet.get("title", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    published=snippet.get("publishedAt", ""),
                    summary=description[:500] if description else "",
                    author=snippet.get("channelTitle", ""),
                    score=float(view_count),
                    tags=[],
                    metadata={
                        "youtube_id": video_id,
                        "channel_id": snippet.get("channelId", ""),
                        "channel_name": snippet.get("channelTitle", ""),
                        "view_count": view_count,
                        "like_count": like_count,
                        "comment_count": comment_count,
                        "duration": duration,
                    },
                )
            )

        return articles[:max_results]

    def _fetch_video_stats(self, video_ids: list[str]) -> dict[str, Any]:
        """Recupere stats et contentDetails pour une liste de video IDs (batch max 50)."""
        if not video_ids:
            return {}

        stats_map: dict[str, Any] = {}

        # Traiter par batch de 50
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            params = {
                "part": "statistics,contentDetails",
                "id": ",".join(batch),
                "key": self.api_key,
            }

            try:
                time.sleep(0.2)  # Rate limit
                resp = self.session.get(YT_VIDEOS_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[youtube] Erreur API videos stats: {e}", file=sys.stderr, flush=True)
                continue

            for item in data.get("items", []):
                vid = item.get("id", "")
                stats_map[vid] = {
                    "statistics": item.get("statistics", {}),
                    "contentDetails": item.get("contentDetails", {}),
                }

        return stats_map

    # ------------------------------------------------------------------
    # Mode RSS fallback
    # ------------------------------------------------------------------

    def _collect_rss(
        self,
        keywords: list[str],
        time_range: str,
        max_results: int,
        config: dict[str, Any],
    ) -> list[Article]:
        channels = config.get("channels", [])
        if not channels:
            print(
                "[youtube] Aucun channel configure dans sources.json. "
                "Ajoute des channels avec leur channel_id pour utiliser le mode RSS.",
                file=sys.stderr,
                flush=True,
            )
            return []

        seconds = self.parse_time_range(time_range)
        cutoff = datetime.fromtimestamp(time.time() - seconds, tz=timezone.utc)
        keywords_lower = [kw.lower() for kw in keywords]

        articles: list[Article] = []
        seen_ids: set[str] = set()

        for channel in channels:
            channel_id = channel.get("channel_id", "")
            channel_name = channel.get("name", channel_id)

            if not channel_id:
                continue

            feed_url = f"{YT_RSS_URL}?channel_id={channel_id}"

            try:
                time.sleep(0.5)  # Rate limit
                resp = self.session.get(feed_url, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                print(f"[youtube] Erreur RSS {channel_name}: {e}", file=sys.stderr, flush=True)
                continue

            try:
                root = ET.fromstring(resp.text)
            except ET.ParseError as e:
                print(f"[youtube] Erreur parsing XML {channel_name}: {e}", file=sys.stderr, flush=True)
                continue

            for entry in root.findall(f"{NS_ATOM}entry"):
                video_id_el = entry.find(f"{NS_YT}videoId")
                video_id = video_id_el.text if video_id_el is not None else ""

                if not video_id or video_id in seen_ids:
                    continue

                # Parse date
                published_el = entry.find(f"{NS_ATOM}published")
                published_str = published_el.text if published_el is not None else ""
                if published_str:
                    try:
                        pub_date = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                        if pub_date < cutoff:
                            continue
                    except ValueError:
                        pass

                # Titre et description
                title_el = entry.find(f"{NS_ATOM}title")
                title = title_el.text if title_el is not None else ""

                media_group = entry.find(f"{NS_MEDIA}group")
                description = ""
                if media_group is not None:
                    desc_el = media_group.find(f"{NS_MEDIA}description")
                    description = desc_el.text if desc_el is not None else ""

                # Filtre par keywords
                if keywords_lower:
                    text_to_search = f"{title} {description}".lower()
                    if not any(kw in text_to_search for kw in keywords_lower):
                        continue

                seen_ids.add(video_id)

                articles.append(
                    Article(
                        title=title,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        source_id=self.SOURCE_ID,
                        source_name=self.SOURCE_NAME,
                        published=published_str,
                        summary=description[:500] if description else "",
                        author=channel_name,
                        score=0.0,
                        tags=[],
                        metadata={
                            "youtube_id": video_id,
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "view_count": None,
                            "like_count": None,
                            "comment_count": None,
                            "duration": None,
                        },
                    )
                )

                if len(articles) >= max_results:
                    return articles

        return articles[:max_results]


if __name__ == "__main__":
    YouTubeCollector.cli_main()
