from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.drct_insight_schema import DrctInsightPerformanceRefreshResponse, DrctInsightPerformanceResponse, DrctInsightTodayResponse
from backend.app.services.drct_insight_performance_service import DrctInsightPerformanceService
from backend.app.services.drct_insight_service import DrctInsightService


router = APIRouter()


@router.get("/api/drct-insight/today", response_model=DrctInsightTodayResponse)
def get_today_drct_insight(
    force: bool = False,
    db: Session = Depends(get_db),
) -> DrctInsightTodayResponse:
    return DrctInsightService(db).today(force_refresh=force)


@router.post("/api/drct-insight/today/evaluate", response_model=DrctInsightTodayResponse)
def capture_today_drct_insight_candidates(db: Session = Depends(get_db)) -> DrctInsightTodayResponse:
    return DrctInsightService(db).capture_today_candidates()


@router.get("/api/drct-insight/evaluations", response_model=DrctInsightPerformanceResponse)
def get_drct_insight_evaluations(
    period: str = Query("60", pattern="^(20|60|120|ALL)$"),
    candidate_level: str | None = Query(None, pattern="^(FOCUS|FINAL)$"),
    theme_id: int | None = None,
    pattern_status: str | None = None,
    outcome_status: str | None = Query(None, pattern="^(PENDING|PARTIAL|COMPLETE)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=20, le=100),
    db: Session = Depends(get_db),
) -> DrctInsightPerformanceResponse:
    return DrctInsightPerformanceService(db).evaluations(
        period, candidate_level, theme_id, pattern_status, outcome_status, page, page_size
    )


@router.post("/api/drct-insight/evaluations/refresh", response_model=DrctInsightPerformanceRefreshResponse)
def refresh_drct_insight_evaluations(
    force: bool = False,
    db: Session = Depends(get_db),
) -> DrctInsightPerformanceRefreshResponse:
    return DrctInsightPerformanceService(db).refresh(force)
