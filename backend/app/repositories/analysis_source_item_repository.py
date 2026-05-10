from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from backend.app.entities.analysis_source_item import AnalysisSourceItem


class AnalysisSourceItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_many(self, items: list[AnalysisSourceItem]) -> None:
        if not items:
            return
        self.db.add_all(items)
        self.db.commit()

    def list_used_source_ids(self, stock_id: int, source_type: str) -> set[int]:
        stmt: Select[tuple[int]] = select(AnalysisSourceItem.source_id).where(
            AnalysisSourceItem.stock_id == stock_id,
            AnalysisSourceItem.source_type == source_type,
            AnalysisSourceItem.used_stage == "final_briefing",
        )
        return set(self.db.scalars(stmt).all())

    def exists_used(self, stock_id: int, source_type: str, source_id: int) -> bool:
        stmt = select(AnalysisSourceItem.id).where(
            AnalysisSourceItem.stock_id == stock_id,
            AnalysisSourceItem.source_type == source_type,
            AnalysisSourceItem.source_id == source_id,
            AnalysisSourceItem.used_stage == "final_briefing",
        )
        return self.db.scalar(stmt) is not None

    def list_by_report(self, report_id: int) -> list[AnalysisSourceItem]:
        stmt: Select[tuple[AnalysisSourceItem]] = (
            select(AnalysisSourceItem)
            .where(AnalysisSourceItem.report_id == report_id)
            .order_by(AnalysisSourceItem.id.asc())
        )
        return list(self.db.scalars(stmt).all())
