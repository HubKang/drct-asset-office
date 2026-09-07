from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.drct_insight_schema import DrctInsightTodayResponse
from backend.app.services.drct_insight_service import DrctInsightService


router = APIRouter()


@router.get("/api/drct-insight/today", response_model=DrctInsightTodayResponse)
def get_today_drct_insight(db: Session = Depends(get_db)) -> DrctInsightTodayResponse:
    return DrctInsightService(db).today()


@router.post("/api/drct-insight/today/evaluate", response_model=DrctInsightTodayResponse)
def capture_today_drct_insight_candidates(db: Session = Depends(get_db)) -> DrctInsightTodayResponse:
    return DrctInsightService(db).capture_today_candidates()
