from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from backend.app.entities.research_report import ResearchReport


class ResearchReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, report: ResearchReport) -> ResearchReport:
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_by_id(self, report_id: int) -> ResearchReport | None:
        return self.db.get(ResearchReport, report_id)

    def list(
        self,
        stock_id: int | None,
        report_type: str | None,
        limit: int,
        offset: int,
    ) -> list[ResearchReport]:
        stmt: Select[tuple[ResearchReport]] = select(ResearchReport)
        if stock_id is not None:
            stmt = stmt.where(ResearchReport.stock_id == stock_id)
        if report_type:
            stmt = stmt.where(ResearchReport.report_type == report_type)
        stmt = stmt.order_by(ResearchReport.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())
