from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass
class TranscriptChunk:
    index: int
    text: str


class TranscriptUnavailableError(Exception):
    pass


class TranscriptFetchError(Exception):
    pass


class YouTubeTranscriptService:
    def __init__(self) -> None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        except Exception as exc:
            raise TranscriptFetchError("youtube-transcript-api가 설치되지 않았습니다.") from exc
        self._api_cls = YouTubeTranscriptApi
        self.last_attempts: list[dict[str, Any]] = []

    def fetch_transcript_text(self, video_id: str) -> tuple[str, str, str]:
        self.last_attempts = []

        # 1) v1.1.1 우선 경로: instance fetch
        try:
            api = self._api_cls()
            raw = api.fetch(video_id, languages=["ko", "en"])
            texts = self._normalize_transcript_items(raw)
            if texts:
                language = self._guess_language(raw) or "ko"
                self.last_attempts.append({"method": "fetch", "success": True})
                return " ".join(texts), language, "transcript_api"
            self.last_attempts.append({"method": "fetch", "success": False, "error_type": "EmptyTranscript"})
        except Exception as exc:
            self.last_attempts.append({"method": "fetch", "success": False, "error_type": exc.__class__.__name__})

        # 2) fallback: legacy static get_transcript
        try:
            raw_legacy = self._api_cls.get_transcript(video_id, languages=["ko", "en"])  # type: ignore[attr-defined]
            texts = self._normalize_transcript_items(raw_legacy)
            if texts:
                self.last_attempts.append({"method": "get_transcript", "success": True})
                return " ".join(texts), "ko", "transcript_api"
            self.last_attempts.append({"method": "get_transcript", "success": False, "error_type": "EmptyTranscript"})
        except Exception as exc:
            self.last_attempts.append({"method": "get_transcript", "success": False, "error_type": exc.__class__.__name__})

        # 3) 진단 fallback: list/list_transcripts (성공 여부 확인용)
        try:
            if hasattr(self._api_cls, "list_transcripts"):
                self._api_cls.list_transcripts(video_id)  # type: ignore[attr-defined]
            elif hasattr(self._api_cls, "list"):
                self._api_cls.list(video_id)  # type: ignore[attr-defined]
            self.last_attempts.append({"method": "list_fallback", "success": False, "error_type": "TranscriptNotResolved"})
            raise TranscriptFetchError("fetch/get_transcript 경로에서 자막 본문을 가져오지 못했습니다.")
        except Exception as exc:
            self.last_attempts.append({"method": "list_fallback", "success": False, "error_type": exc.__class__.__name__})
            msg = str(exc).lower()
            if "no transcripts" in msg or ("transcript" in msg and "not available" in msg):
                raise TranscriptUnavailableError("자막을 찾을 수 없습니다.") from exc
            raise TranscriptFetchError("자막 조회에 실패했습니다.") from exc

    @staticmethod
    def _normalize_transcript_items(raw_transcript: Any) -> list[str]:
        texts: list[str] = []
        try:
            iterator = iter(raw_transcript)
        except Exception:
            return texts
        for item in iterator:
            text_value = None
            if hasattr(item, "text"):
                text_value = getattr(item, "text", None)
            elif isinstance(item, dict):
                text_value = item.get("text")
            if text_value is None:
                continue
            normalized = re.sub(r"\s+", " ", str(text_value)).strip()
            if normalized:
                texts.append(normalized)
        return texts

    @staticmethod
    def _guess_language(raw_transcript: Any) -> str | None:
        try:
            first = next(iter(raw_transcript))
        except Exception:
            return None
        for key in ("language_code", "language"):
            if hasattr(first, key):
                value = getattr(first, key, None)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def split_text_into_chunks(text: str, max_chars: int = 4000, overlap_chars: int = 300) -> list[TranscriptChunk]:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return []
        if len(normalized) <= max_chars:
            return [TranscriptChunk(index=1, text=normalized)]

        chunks: list[TranscriptChunk] = []
        start = 0
        idx = 1
        while start < len(normalized):
            end = min(len(normalized), start + max_chars)
            split = normalized.rfind(". ", start, end)
            if split <= start + max_chars // 2:
                split = normalized.rfind(" ", start, end)
            if split <= start:
                split = end
            else:
                split += 1
            piece = normalized[start:split].strip()
            if piece:
                chunks.append(TranscriptChunk(index=idx, text=piece))
                idx += 1
            if split >= len(normalized):
                break
            next_start = max(0, split - overlap_chars)
            # overlap 때문에 포인터가 뒤로 밀리면 무한 루프가 생길 수 있어 강제로 전진시킨다.
            if next_start <= start:
                next_start = split
            if next_start <= start:
                next_start = min(len(normalized), start + max(1, max_chars - overlap_chars))
            start = next_start
        return chunks

    @staticmethod
    def split_text_into_chunks_for_llm(text: str, max_chars: int = 2500, overlap_chars: int = 150) -> list[TranscriptChunk]:
        return YouTubeTranscriptService.split_text_into_chunks(
            text=text,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )
