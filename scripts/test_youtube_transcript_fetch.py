from __future__ import annotations

import argparse
from importlib.metadata import version


def clip(text: str, max_len: int = 200) -> str:
    return text[:max_len]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    args = parser.parse_args()
    video_id = args.video_id.strip()

    print(f"package_version={version('youtube-transcript-api')}")

    from youtube_transcript_api import YouTubeTranscriptApi

    fetch_success = False
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["ko", "en"])
        count = len(fetched)
        preview = fetched[0].text if count > 0 and hasattr(fetched[0], "text") else ""
        fetch_success = count > 0
        print(f"fetch_success={fetch_success}")
        print(f"fetch_item_count={count}")
        print(f"fetch_preview={clip(preview)}")
    except Exception as exc:
        print("fetch_success=False")
        print(f"fetch_error_type={exc.__class__.__name__}")
        print(f"fetch_error={clip(str(exc), 200)}")

    get_success = False
    try:
        legacy = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])  # type: ignore[attr-defined]
        count = len(legacy)
        preview = str(legacy[0].get("text") or "") if count > 0 and isinstance(legacy[0], dict) else ""
        get_success = count > 0
        print(f"get_transcript_success={get_success}")
        print(f"get_transcript_item_count={count}")
        print(f"get_transcript_preview={clip(preview)}")
    except Exception as exc:
        print("get_transcript_success=False")
        print(f"get_transcript_error_type={exc.__class__.__name__}")
        print(f"get_transcript_error={clip(str(exc), 200)}")

    try:
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            lst = YouTubeTranscriptApi.list_transcripts(video_id)  # type: ignore[attr-defined]
            _ = list(lst)
            print("list_success=True")
        elif hasattr(YouTubeTranscriptApi, "list"):
            lst = YouTubeTranscriptApi.list(video_id)  # type: ignore[attr-defined]
            _ = list(lst)
            print("list_success=True")
        else:
            print("list_success=False")
            print("list_error_type=NotSupported")
    except Exception as exc:
        print("list_success=False")
        print(f"list_error_type={exc.__class__.__name__}")
        print(f"list_error={clip(str(exc), 200)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
