from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.research_report_repository import ResearchReportRepository


class ReportService:
    def __init__(self, db: Session) -> None:
        self.repo = ResearchReportRepository(db)

    def list_reports(self, stock_id: int | None, report_type: str | None, limit: int, offset: int):
        return self.repo.list(stock_id=stock_id, report_type=report_type, limit=limit, offset=offset)

    def get_report(self, report_id: int):
        report = self.repo.get_by_id(report_id)
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
        return report
