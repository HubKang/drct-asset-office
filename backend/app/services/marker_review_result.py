from __future__ import annotations

from fastapi import HTTPException


MARKER_REVIEW_RESULTS = {"S", "F"}
LEGACY_MARKER_REVIEW_RESULTS = {"SUCCESS": "S", "FAILURE": "F"}


def normalize_marker_review_result(value: str | None) -> str | None:
    """Normalize persisted legacy marker review codes at the read boundary."""
    if value is None:
        return None
    normalized = str(value).strip().upper()
    normalized = LEGACY_MARKER_REVIEW_RESULTS.get(normalized, normalized)
    if normalized not in MARKER_REVIEW_RESULTS:
        raise HTTPException(500, f"지원하지 않는 차트마커 복기 코드입니다: {value}")
    return normalized


def legacy_training_label(value: str | None) -> str | None:
    """Keep the retired search-research response contract compatible."""
    normalized = normalize_marker_review_result(value)
    return {"S": "SUCCESS", "F": "FAILURE"}.get(normalized) if normalized else None

