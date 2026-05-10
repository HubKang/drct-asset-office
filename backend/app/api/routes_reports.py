from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.report_schema import ResearchReportResponse
from backend.app.services.report_service import ReportService

router = APIRouter()


@router.get("/reports", response_model=list[ResearchReportResponse])
def list_reports(
    stock_id: int | None = None,
    report_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ResearchReportResponse]:
    return ReportService(db).list_reports(stock_id=stock_id, report_type=report_type, limit=limit, offset=offset)


@router.get("/reports/{report_id}", response_model=ResearchReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)) -> ResearchReportResponse:
    return ReportService(db).get_report(report_id)
