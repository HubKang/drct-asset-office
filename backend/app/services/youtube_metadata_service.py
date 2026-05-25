from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import requests

from backend.app.core.config import (
    YOUTUBE_API_ENABLED,
    YOUTUBE_API_KEY,
    YOUTUBE_API_TIMEOUT_SECONDS,
)


class YouTubeMetadataError(RuntimeError):
    pass


@dataclass
class YouTubeVideoMetadata:
    video_id: str
    title: str
    channel_name: str | None
    published_at: str | None
    duration_seconds: int | None
    thumbnail_url: str | None
    description_summary: str | None


class YouTubeMetadataService:
    PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
    VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, timeout_seconds: int | None = None) -> None:
        self.timeout_seconds = timeout_seconds or YOUTUBE_API_TIMEOUT_SECONDS

    @staticmethod
    def ensure_youtube_enabled() -> None:
        if not YOUTUBE_API_ENABLED:
            raise YouTubeMetadataError("YOUTUBE_API_ENABLED=false 상태입니다.")
        if not YOUTUBE_API_KEY:
            raise YouTubeMetadataError("YOUTUBE_API_KEY 설정이 필요합니다.")

    def fetch_playlist_video_ids(self, playlist_id: str, max_results: int = 20) -> list[str]:
        self.ensure_youtube_enabled()
        if max_results <= 0:
            return []
        collected: list[str] = []
        page_token: str | None = None
        while len(collected) < max_results:
            batch_size = min(50, max_results - len(collected))
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": batch_size,
                "key": YOUTUBE_API_KEY,
            }
            if page_token:
                params["pageToken"] = page_token
            try:
                resp = requests.get(self.PLAYLIST_ITEMS_URL, params=params, timeout=self.timeout_seconds)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                raise YouTubeMetadataError("YouTube playlist 조회에 실패했습니다.") from exc
            items = data.get("items", []) if isinstance(data, dict) else []
            if not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                content = item.get("contentDetails", {})
                snippet = item.get("snippet", {})
                video_id = None
                if isinstance(content, dict):
                    video_id = content.get("videoId")
                if not video_id and isinstance(snippet, dict):
                    resource = snippet.get("resourceId", {})
                    if isinstance(resource, dict):
                        video_id = resource.get("videoId")
                if isinstance(video_id, str) and video_id.strip():
                    collected.append(video_id.strip())
                if len(collected) >= max_results:
                    break
            page_token = data.get("nextPageToken") if isinstance(data, dict) else None
            if not page_token:
                break
        return collected

    def fetch_video_metadata(self, video_ids: list[str]) -> list[YouTubeVideoMetadata]:
        self.ensure_youtube_enabled()
        cleaned = [x.strip() for x in video_ids if isinstance(x, str) and x.strip()]
        if not cleaned:
            return []
        out: list[YouTubeVideoMetadata] = []
        for i in range(0, len(cleaned), 50):
            batch = cleaned[i : i + 50]
            params = {
                "part": "snippet,contentDetails,status",
                "id": ",".join(batch),
                "key": YOUTUBE_API_KEY,
            }
            try:
                resp = requests.get(self.VIDEOS_URL, params=params, timeout=self.timeout_seconds)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                raise YouTubeMetadataError("YouTube video 메타데이터 조회에 실패했습니다.") from exc
            items = data.get("items", []) if isinstance(data, dict) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                vid = str(item.get("id") or "").strip()
                if not vid:
                    continue
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                title = "미조회 영상"
                channel_name = None
                published_at = None
                description_summary = None
                thumbnail_url = None
                duration_seconds = None
                if isinstance(snippet, dict):
                    title = str(snippet.get("title") or "미조회 영상").strip() or "미조회 영상"
                    channel_name = str(snippet.get("channelTitle") or "").strip() or None
                    published_at = str(snippet.get("publishedAt") or "").strip() or None
                    description_summary = self.make_description_summary(str(snippet.get("description") or ""))
                    thumbnail_url = self.select_thumbnail(snippet)
                if isinstance(content_details, dict):
                    duration_seconds = self.parse_youtube_duration_to_seconds(str(content_details.get("duration") or ""))
                out.append(
                    YouTubeVideoMetadata(
                        video_id=vid,
                        title=title[:300],
                        channel_name=channel_name,
                        published_at=published_at,
                        duration_seconds=duration_seconds,
                        thumbnail_url=thumbnail_url,
                        description_summary=description_summary,
                    )
                )
        return out

    @staticmethod
    def parse_youtube_duration_to_seconds(duration: str) -> int | None:
        if not duration:
            return None
        match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration.strip())
        if not match:
            return None
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def make_description_summary(description: str, max_length: int = 300) -> str | None:
        if not description:
            return None
        compact = re.sub(r"\s+", " ", description).strip()
        if not compact:
            return None
        return compact[:max_length]

    @staticmethod
    def select_thumbnail(snippet: dict[str, Any]) -> str | None:
        thumbs = snippet.get("thumbnails", {})
        if not isinstance(thumbs, dict):
            return None
        for key in ["high", "medium", "default"]:
            item = thumbs.get(key, {})
            if isinstance(item, dict):
                url = str(item.get("url") or "").strip()
                if url:
                    return url
        return None
