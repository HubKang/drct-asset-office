from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.dashboard_activity_service import DashboardActivityService


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/recent-activities", response_model=dict)
def recent_dashboard_activities(
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict:
    return DashboardActivityService(db).recent(days=days, limit=limit)
