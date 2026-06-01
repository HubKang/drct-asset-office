from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import importlib.util
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any

from backend.app.core.config import (
    ECONOMIC_BRIEFING_TRANSCRIPT_RETRY_COOLDOWN_MINUTES,
    YOUTUBE_TRANSCRIPT_BYPASS_PROXY,
    YOUTUBE_TRANSCRIPT_ENABLE_YTDLP,
    YOUTUBE_TRANSCRIPT_LANGS,
    YOUTUBE_TRANSCRIPT_MAX_CHARS,
    YOUTUBE_TRANSCRIPT_PROVIDER,
    YOUTUBE_TRANSCRIPT_RATE_LIMIT_COOLDOWN_MINUTES,
    YOUTUBE_TRANSCRIPT_YTDLP_JS_RUNTIMES,
    YOUTUBE_TRANSCRIPT_YTDLP_TIMEOUT_SECONDS,
)


@dataclass
class TranscriptChunk:
    index: int
    text: str


class TranscriptUnavailableError(Exception):
    pass


class TranscriptFetchError(Exception):
    pass


class TranscriptProviderFailure(TranscriptFetchError):
    def __init__(
        self,
        message: str,
        *,
        selected_provider: str,
        provider_results: dict[str, dict[str, object]],
        normalized_error_type: str,
        is_retryable: bool,
        retry_after_minutes: int | None,
    ) -> None:
        super().__init__(message)
        self.selected_provider = selected_provider
        self.provider_results = provider_results
        self.normalized_error_type = normalized_error_type
        self.is_retryable = is_retryable
        self.retry_after_minutes = retry_after_minutes


logger = logging.getLogger(__name__)


class YouTubeTranscriptService:
    _proxy_bypass_lock = threading.RLock()
    _proxy_env_keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    )

    def __init__(self) -> None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        except Exception as exc:
            raise TranscriptFetchError("youtube-transcript-api가 설치되지 않았습니다.") from exc
        self._api_cls = YouTubeTranscriptApi
        self.last_attempts: list[dict[str, Any]] = []

    @contextmanager
    def _without_proxy_env(self):
        if not YOUTUBE_TRANSCRIPT_BYPASS_PROXY:
            with nullcontext():
                yield
            return

        with self._proxy_bypass_lock:
            previous_values = {key: os.environ.get(key) for key in self._proxy_env_keys}
            try:
                for key in self._proxy_env_keys:
                    os.environ.pop(key, None)
                yield
            finally:
                for key, value in previous_values.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def fetch_transcript_text(self, video_id: str, caller: str = "unknown") -> tuple[str, str, str]:
        self.last_attempts = []
        logger.info("[EconomicBriefing] transcript_fetch_start video_id=%s caller=%s bypass_proxy=%s", video_id, caller, YOUTUBE_TRANSCRIPT_BYPASS_PROXY)
        with self._without_proxy_env():
            try:
                text_all, language, source = self._fetch_transcript_text_with_fallback(video_id)
                logger.info(
                    "[EconomicBriefing] transcript_fetch_success video_id=%s caller=%s language=%s source=%s text_length=%s",
                    video_id,
                    caller,
                    language,
                    source,
                    len(text_all),
                )
                return text_all, language, source
            except Exception as exc:
                logger.warning(
                    "[EconomicBriefing] transcript_fetch_failed video_id=%s caller=%s error_type=%s attempts=%s",
                    video_id,
                    caller,
                    exc.__class__.__name__,
                    self.last_attempts,
                )
                raise

    def _fetch_transcript_text_with_fallback(self, video_id: str) -> tuple[str, str, str]:
        provider_mode = (YOUTUBE_TRANSCRIPT_PROVIDER or "auto").lower()
        api_error: Exception | None = None
        provider_results: dict[str, dict[str, object]] = {}

        should_try_api = provider_mode in {"auto", "transcript_api", "youtube_transcript_api"}
        should_try_ytdlp = YOUTUBE_TRANSCRIPT_ENABLE_YTDLP and provider_mode in {"auto", "yt_dlp", "ytdlp"}

        if should_try_api:
            try:
                return self._fetch_transcript_text_core(video_id)
            except Exception as exc:
                api_error = exc
                provider_results["youtube_transcript_api"] = {
                    "success": False,
                    "error_type": self._normalize_provider_error(exc, "youtube_transcript_api"),
                }
                self.last_attempts.append(
                    {
                        "method": "provider_transcript_api",
                        "success": False,
                        "error_type": exc.__class__.__name__,
                    }
                )
                if not should_try_ytdlp:
                    raise

        if should_try_ytdlp:
            try:
                text_all, language = self._fetch_with_ytdlp(video_id)
                provider_results["yt_dlp"] = {"success": True, "error_type": None}
                self.last_attempts.append({"method": "provider_yt_dlp", "success": True})
                return text_all, language, "yt_dlp"
            except TranscriptUnavailableError:
                provider_results["yt_dlp"] = {"success": False, "error_type": "transcript_unavailable"}
                raise
            except Exception as exc:
                provider_results["yt_dlp"] = {
                    "success": False,
                    "error_type": self._normalize_provider_error(exc, "yt_dlp"),
                }
                self.last_attempts.append(
                    {
                        "method": "provider_yt_dlp",
                        "success": False,
                        "error_type": exc.__class__.__name__,
                    }
                )
                api_reason = api_error.__class__.__name__ if api_error else "not_attempted"
                api_detail = str(api_error).strip().replace("\n", " ")[:120] if api_error else ""
                ytdlp_reason = exc.__class__.__name__
                ytdlp_detail = str(exc).strip().replace("\n", " ")[:120]
                api_part = f"{api_reason}:{api_detail}" if api_detail else api_reason
                ytdlp_part = f"{ytdlp_reason}:{ytdlp_detail}" if ytdlp_detail else ytdlp_reason
                normalized = self._normalize_aggregated_error(provider_results)
                retryable = normalized in {
                    "youtube_transcript_api_ip_blocked",
                    "rate_limited",
                    "yt_dlp_rate_limited",
                    "all_providers_rate_limited",
                    "access_limited",
                    "network_error",
                    "unknown",
                }
                retry_after = (
                    YOUTUBE_TRANSCRIPT_RATE_LIMIT_COOLDOWN_MINUTES
                    if normalized in {"rate_limited", "yt_dlp_rate_limited", "all_providers_rate_limited"}
                    else ECONOMIC_BRIEFING_TRANSCRIPT_RETRY_COOLDOWN_MINUTES
                )
                raise TranscriptProviderFailure(
                    f"transcript_source_failed:{normalized}; youtube_transcript_api={api_part}; yt_dlp={ytdlp_part}"[:500],
                    selected_provider="all_failed",
                    provider_results=provider_results,
                    normalized_error_type=normalized,
                    is_retryable=retryable,
                    retry_after_minutes=retry_after if retryable else None,
                ) from exc

        if api_error:
            raise api_error
        raise TranscriptFetchError("transcript provider is disabled")

    def _fetch_transcript_text_core(self, video_id: str) -> tuple[str, str, str]:
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
            if any(str(a.get("error_type", "")).lower() == "ipblocked" for a in self.last_attempts):
                raise TranscriptFetchError("IpBlocked") from exc
            raise TranscriptFetchError("자막 조회에 실패했습니다.") from exc

    def _fetch_with_ytdlp(self, video_id: str) -> tuple[str, str]:
        if importlib.util.find_spec("yt_dlp") is None:
            raise TranscriptFetchError("yt_dlp_not_installed")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        langs = YOUTUBE_TRANSCRIPT_LANGS or ["ko", "ko-KR", "en", "en-US"]
        js_runtimes = self._resolve_js_runtimes()
        base_tmp = Path.cwd() / "tmp" / "yt_dlp_subs"
        base_tmp.mkdir(parents=True, exist_ok=True)
        try:
            tmpdir = tempfile.mkdtemp(prefix="yt_sub_", dir=str(base_tmp))
            try:
                outtmpl = str(Path(tmpdir) / f"{video_id}.%(ext)s")
                cmd = [
                    sys.executable,
                    "-m",
                    "yt_dlp",
                    "--skip-download",
                    "--write-subs",
                    "--write-auto-subs",
                    "--sub-langs",
                    ",".join(langs),
                    "--sub-format",
                    "vtt/srt/best",
                    "-o",
                    outtmpl,
                ]
                if js_runtimes:
                    cmd.extend(["--js-runtimes", js_runtimes])
                cmd.append(video_url)
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=YOUTUBE_TRANSCRIPT_YTDLP_TIMEOUT_SECONDS,
                    check=False,
                    env=self._build_proxy_free_env(),
                )
                if proc.returncode != 0:
                    stderr = (proc.stderr or "").strip().replace("\n", " ")
                    summary = stderr[:220] if stderr else "yt-dlp command failed"
                    raise TranscriptFetchError(f"yt_dlp_failed:{summary}")

                subtitle_files = self._find_subtitle_files(tmpdir, video_id)
                if not subtitle_files:
                    raise TranscriptUnavailableError("yt-dlp 자막 파일을 찾을 수 없습니다.")

                for subtitle_file in subtitle_files:
                    text_all = self._extract_text_from_subtitle_file(subtitle_file)
                    if text_all:
                        language = self._guess_language_from_path(subtitle_file)
                        return text_all[:YOUTUBE_TRANSCRIPT_MAX_CHARS], language
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        except PermissionError as exc:
            detail = str(exc).strip().replace("\n", " ")[:180]
            raise TranscriptFetchError(f"yt_dlp_permission_error:{detail or exc.__class__.__name__}") from exc
        raise TranscriptUnavailableError("yt-dlp 자막 본문이 비어 있습니다.")

    @staticmethod
    def _find_subtitle_files(tmpdir: str, video_id: str) -> list[Path]:
        root = Path(tmpdir)
        candidates = sorted(root.glob(f"{video_id}*.vtt")) + sorted(root.glob(f"{video_id}*.srt"))
        preferred: list[Path] = []
        fallback: list[Path] = []
        for path in candidates:
            name = path.name.lower()
            if ".ko" in name:
                preferred.append(path)
            else:
                fallback.append(path)
        return preferred + fallback

    @staticmethod
    def _extract_text_from_subtitle_file(path: Path) -> str:
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
        lines: list[str] = []
        seen: set[str] = set()
        for line in raw.splitlines():
            s = line.strip()
            if not s:
                continue
            upper = s.upper()
            if upper == "WEBVTT":
                continue
            if s.isdigit():
                continue
            if "-->" in s:
                continue
            s = re.sub(r"<[^>]+>", " ", s)
            s = re.sub(r"&[a-zA-Z]+;", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            lines.append(s)
        return " ".join(lines)

    @staticmethod
    def _guess_language_from_path(path: Path) -> str:
        name = path.name.lower()
        if ".ko" in name:
            return "ko"
        if ".en" in name:
            return "en"
        return "unknown"

    @staticmethod
    def _normalize_provider_error(exc: Exception, provider: str) -> str:
        msg = str(exc).lower()
        name = exc.__class__.__name__.lower()
        if "ipblocked" in msg:
            return "youtube_transcript_api_ip_blocked"
        if "sign in to confirm you're not a bot" in msg or "cookies" in msg:
            return "yt_dlp_cookies_required"
        if "access denied" in msg or "forbidden" in msg or "blocked" in msg:
            return "yt_dlp_blocked"
        if "429" in msg or "too many requests" in msg or "rate limit" in msg:
            return "yt_dlp_rate_limited" if provider == "yt_dlp" else "rate_limited"
        if "yt_dlp_not_installed" in msg:
            return "yt_dlp_not_installed"
        if "javascript runtime" in msg or "only deno is enabled" in msg:
            return "yt_dlp_runtime_missing"
        if "timed out" in msg or "timeout" in msg:
            return "yt_dlp_failed"
        if "no subtitles" in msg or "transcript unavailable" in msg:
            return "transcript_unavailable"
        if "connection" in msg or "network" in msg or "proxy" in msg:
            return "network_error"
        if "unavailable" in msg and provider == "youtube_transcript_api":
            return "transcript_unavailable"
        if name == "transcriptunavailableerror":
            return "transcript_unavailable"
        if provider == "yt_dlp":
            return "yt_dlp_failed"
        return "unknown"

    @staticmethod
    def _normalize_aggregated_error(provider_results: dict[str, dict[str, object]]) -> str:
        yt_api_err = str((provider_results.get("youtube_transcript_api") or {}).get("error_type") or "")
        yt_dlp_err = str((provider_results.get("yt_dlp") or {}).get("error_type") or "")
        if yt_api_err == "youtube_transcript_api_ip_blocked" and yt_dlp_err == "yt_dlp_not_installed":
            return "all_providers_failed"
        if yt_api_err in {"youtube_transcript_api_ip_blocked", "rate_limited"} and yt_dlp_err == "yt_dlp_rate_limited":
            return "all_providers_rate_limited"
        if yt_dlp_err == "yt_dlp_not_installed":
            return "yt_dlp_not_installed"
        if "transcript_unavailable" in {yt_api_err, yt_dlp_err}:
            return "transcript_unavailable"
        if "rate_limited" in {yt_api_err, yt_dlp_err}:
            return "rate_limited"
        if yt_dlp_err == "yt_dlp_rate_limited":
            return "yt_dlp_rate_limited"
        if "network_error" in {yt_api_err, yt_dlp_err}:
            return "network_error"
        if yt_dlp_err == "yt_dlp_failed":
            return "yt_dlp_failed"
        if yt_dlp_err == "yt_dlp_runtime_missing":
            return "yt_dlp_runtime_missing"
        if yt_dlp_err == "yt_dlp_cookies_required":
            return "yt_dlp_cookies_required"
        if yt_dlp_err == "yt_dlp_blocked":
            return "yt_dlp_blocked"
        if yt_api_err == "youtube_transcript_api_ip_blocked":
            return "access_limited"
        return "unknown"

    @classmethod
    def _build_proxy_free_env(cls) -> dict[str, str]:
        env = dict(os.environ)
        for key in cls._proxy_env_keys:
            env.pop(key, None)
        return env

    @staticmethod
    def _resolve_js_runtimes() -> str:
        if YOUTUBE_TRANSCRIPT_YTDLP_JS_RUNTIMES:
            return YOUTUBE_TRANSCRIPT_YTDLP_JS_RUNTIMES
        candidates = ["node", "deno", "bun", "qjs", "quickjs"]
        for name in candidates:
            runtime_path = shutil.which(name)
            if runtime_path:
                return f"{name}:{runtime_path}"
        return ""

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
            # overlap 구문에서 start가 뒤로 밀리면 무한 루프가 생길 수 있어 강제로 전진시킨다.
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
