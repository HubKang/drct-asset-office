from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.youtube_transcript_service import (  # noqa: E402
    TranscriptFetchError,
    TranscriptProviderFailure,
    TranscriptUnavailableError,
    YouTubeTranscriptService,
)


def run(video_id: str) -> int:
    service = YouTubeTranscriptService()
    result: dict[str, object] = {"video_id": video_id}
    try:
        text, language, provider = service.fetch_transcript_text(video_id, caller="diagnostic_script")
        runtime = getattr(service, "_resolve_js_runtimes", lambda: "")()
        result.update(
            {
                "success": True,
                "provider": provider,
                "language": language,
                "yt_dlp_js_runtime": runtime or None,
                "transcript_length": len(text),
                "attempts": service.last_attempts,
            }
        )
    except TranscriptProviderFailure as exc:
        runtime = getattr(service, "_resolve_js_runtimes", lambda: "")()
        result.update(
            {
                "success": False,
                "error_type": "TranscriptProviderFailure",
                "error_message": str(exc)[:500],
                "provider": exc.selected_provider,
                "selected_provider": exc.selected_provider,
                "provider_results": exc.provider_results,
                "normalized_error_type": exc.normalized_error_type,
                "is_retryable": exc.is_retryable,
                "retry_after_minutes": exc.retry_after_minutes,
                "yt_dlp_js_runtime": runtime or None,
                "attempts": service.last_attempts,
            }
        )
    except TranscriptUnavailableError as exc:
        result.update(
            {
                "success": False,
                "error_type": "TranscriptUnavailableError",
                "error_message": str(exc)[:300],
                "provider": "all_failed",
                "attempts": service.last_attempts,
            }
        )
    except TranscriptFetchError as exc:
        result.update(
            {
                "success": False,
                "error_type": "TranscriptFetchError",
                "error_message": str(exc)[:300],
                "provider": "all_failed",
                "selected_provider": "all_failed",
                "provider_results": {},
                "normalized_error_type": "unknown",
                "is_retryable": True,
                "retry_after_minutes": 60,
                "attempts": service.last_attempts,
            }
        )
    except Exception as exc:  # pragma: no cover
        result.update(
            {
                "success": False,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc)[:300],
                "provider": "all_failed",
                "attempts": service.last_attempts,
            }
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test transcript providers for one YouTube video_id")
    parser.add_argument("video_id", help="YouTube video_id")
    args = parser.parse_args()
    raise SystemExit(run(args.video_id))
