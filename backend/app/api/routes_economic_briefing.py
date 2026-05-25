from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.economic_briefing_schema import (
    BriefingSourceCreate,
    BriefingSourceRefreshRequest,
    BriefingSourceListResponse,
    BriefingSourceMutationResponse,
    BriefingSourceUpdate,
    BriefingSummaryDetailResponse,
    BriefingVideoSummarizeResponse,
    BriefingTranscriptCheckResponse,
    BriefingVideoListResponse,
    BriefingVideoManualCreate,
    BriefingVideoMutationResponse,
    BriefingVideoStatusUpdate,
)
from backend.app.services.economic_briefing_service import EconomicBriefingService

router = APIRouter(prefix="/economic-briefing")


@router.get("/sources", response_model=BriefingSourceListResponse)
def get_briefing_sources(
    status: str = Query(default="all"),
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> BriefingSourceListResponse:
    return EconomicBriefingService(db).list_sources(status_filter=status, include_deleted=include_deleted)


@router.post("/sources", response_model=BriefingSourceMutationResponse)
def create_briefing_source(payload: BriefingSourceCreate, db: Session = Depends(get_db)) -> BriefingSourceMutationResponse:
    return EconomicBriefingService(db).create_source(payload)


@router.patch("/sources/{source_id}", response_model=BriefingSourceMutationResponse)
def update_briefing_source(source_id: int, payload: BriefingSourceUpdate, db: Session = Depends(get_db)) -> BriefingSourceMutationResponse:
    return EconomicBriefingService(db).update_source(source_id, payload)


@router.delete("/sources/{source_id}", response_model=BriefingSourceMutationResponse)
def delete_briefing_source(source_id: int, db: Session = Depends(get_db)) -> BriefingSourceMutationResponse:
    return EconomicBriefingService(db).soft_delete_source(source_id)


@router.patch("/sources/{source_id}/activate", response_model=BriefingSourceMutationResponse)
def activate_briefing_source(source_id: int, db: Session = Depends(get_db)) -> BriefingSourceMutationResponse:
    return EconomicBriefingService(db).activate_source(source_id)


@router.patch("/sources/{source_id}/deactivate", response_model=BriefingSourceMutationResponse)
def deactivate_briefing_source(source_id: int, db: Session = Depends(get_db)) -> BriefingSourceMutationResponse:
    return EconomicBriefingService(db).deactivate_source(source_id)


@router.post("/sources/{source_id}/refresh-videos", response_model=BriefingSourceMutationResponse)
def refresh_briefing_source_videos(
    source_id: int,
    payload: BriefingSourceRefreshRequest,
    db: Session = Depends(get_db),
) -> BriefingSourceMutationResponse:
    return EconomicBriefingService(db).refresh_source_videos(source_id, max_results=payload.max_results)


@router.get("/videos", response_model=BriefingVideoListResponse)
def get_briefing_videos(
    source_id: int | None = Query(default=None),
    manual_only: bool = Query(default=False),
    analysis_status: str | None = Query(default=None),
    transcript_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> BriefingVideoListResponse:
    return EconomicBriefingService(db).list_videos(
        source_id=source_id,
        manual_only=manual_only,
        analysis_status=analysis_status,
        transcript_status=transcript_status,
        limit=limit,
    )


@router.post("/videos/manual", response_model=BriefingVideoMutationResponse)
def create_manual_briefing_video(payload: BriefingVideoManualCreate, db: Session = Depends(get_db)) -> BriefingVideoMutationResponse:
    return EconomicBriefingService(db).create_manual_video(payload)


@router.post("/videos/{video_id}/mark-status", response_model=BriefingVideoMutationResponse)
def mark_briefing_video_status(video_id: int, payload: BriefingVideoStatusUpdate, db: Session = Depends(get_db)) -> BriefingVideoMutationResponse:
    return EconomicBriefingService(db).mark_video_status(briefing_video_id=video_id, payload=payload)


@router.post("/videos/{video_id}/refresh-metadata", response_model=BriefingVideoMutationResponse)
def refresh_briefing_video_metadata(video_id: str, db: Session = Depends(get_db)) -> BriefingVideoMutationResponse:
    return EconomicBriefingService(db).refresh_video_metadata(video_id=video_id)


@router.get("/videos/{video_id}/summaries", response_model=BriefingSummaryDetailResponse)
def get_briefing_video_summaries(video_id: str, db: Session = Depends(get_db)) -> BriefingSummaryDetailResponse:
    return EconomicBriefingService(db).get_summary_detail(video_id=video_id)


@router.post("/videos/{video_id}/transcript-check", response_model=BriefingTranscriptCheckResponse)
def check_briefing_video_transcript(video_id: str, db: Session = Depends(get_db)) -> BriefingTranscriptCheckResponse:
    return EconomicBriefingService(db).check_video_transcript(video_id=video_id)


@router.post("/videos/{video_id}/summarize", response_model=BriefingVideoSummarizeResponse)
def summarize_briefing_video(
    video_id: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> BriefingVideoSummarizeResponse:
    return EconomicBriefingService(db).summarize_video(video_id=video_id, force=force)
