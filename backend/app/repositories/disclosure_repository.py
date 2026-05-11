from __future__ import annotations

from sqlalchemy import Select, not_, select
from sqlalchemy.orm import Session

from backend.app.entities.disclosure import Disclosure
from backend.app.entities.stock import Stock


class DisclosureRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, item: Disclosure) -> Disclosure:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_id(self, disclosure_id: int) -> Disclosure | None:
        return self.db.get(Disclosure, disclosure_id)

    def get_by_receipt_no(self, receipt_no: str) -> Disclosure | None:
        return self.db.scalar(select(Disclosure).where(Disclosure.dart_receipt_no == receipt_no))

    def list(
        self,
        stock_id: int | None,
        keyword: str | None,
        disclosure_type: str | None,
        limit: int,
        offset: int,
    ) -> list[Disclosure]:
        stmt: Select[tuple[Disclosure]] = select(Disclosure)
        if stock_id is not None:
            stmt = stmt.where(Disclosure.stock_id == stock_id)
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where(Disclosure.disclosure_title.like(keyword_like))
        if disclosure_type:
            stmt = stmt.where(Disclosure.disclosure_type == disclosure_type)
        stmt = stmt.order_by(Disclosure.created_at.desc(), Disclosure.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def list_with_stock(
        self,
        stock_id: int | None,
        keyword: str | None,
        disclosure_type: str | None,
        limit: int,
        offset: int,
    ) -> list[tuple[Disclosure, Stock | None]]:
        stmt: Select[tuple[Disclosure, Stock | None]] = select(Disclosure, Stock).join(Stock, Disclosure.stock_id == Stock.id, isouter=True)
        if stock_id is not None:
            stmt = stmt.where(Disclosure.stock_id == stock_id)
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where(Disclosure.disclosure_title.like(keyword_like))
        if disclosure_type:
            stmt = stmt.where(Disclosure.disclosure_type == disclosure_type)
        stmt = stmt.order_by(Disclosure.created_at.desc(), Disclosure.id.desc()).limit(limit).offset(offset)
        return list(self.db.execute(stmt).all())

    def list_recent_by_stock(self, stock_id: int, limit: int) -> list[Disclosure]:
        stmt: Select[tuple[Disclosure]] = (
            select(Disclosure)
            .where(Disclosure.stock_id == stock_id)
            .order_by(Disclosure.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_by_ids(self, stock_id: int, ids: list[int]) -> list[Disclosure]:
        if not ids:
            return []
        stmt: Select[tuple[Disclosure]] = (
            select(Disclosure)
            .where(Disclosure.stock_id == stock_id, Disclosure.id.in_(ids))
            .order_by(Disclosure.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_ids_any(self, ids: list[int]) -> list[Disclosure]:
        if not ids:
            return []
        stmt: Select[tuple[Disclosure]] = select(Disclosure).where(Disclosure.id.in_(ids)).order_by(Disclosure.id.desc())
        return list(self.db.scalars(stmt).all())

    def list_recent_unused_by_stock(self, stock_id: int, exclude_ids: set[int], limit: int) -> list[Disclosure]:
        stmt: Select[tuple[Disclosure]] = select(Disclosure).where(Disclosure.stock_id == stock_id)
        if exclude_ids:
            stmt = stmt.where(not_(Disclosure.id.in_(exclude_ids)))
        stmt = stmt.order_by(Disclosure.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def list_for_ai_summary(
        self,
        stock_id: int | None = None,
        limit: int = 10,
        only_unprocessed: bool = True,
        overwrite: bool = False,
    ) -> list[Disclosure]:
        stmt: Select[tuple[Disclosure]] = select(Disclosure)
        if stock_id is not None:
            stmt = stmt.where(Disclosure.stock_id == stock_id)
        if only_unprocessed and not overwrite:
            stmt = stmt.where(Disclosure.ai_summary.is_(None))
        stmt = stmt.order_by(Disclosure.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def list_for_classification(self, stock_id: int | None = None, limit: int = 100) -> list[Disclosure]:
        stmt: Select[tuple[Disclosure]] = select(Disclosure).where(Disclosure.ai_summary.is_not(None))
        if stock_id is not None:
            stmt = stmt.where(Disclosure.stock_id == stock_id)
        stmt = stmt.order_by(Disclosure.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def update_ai_summary(
        self,
        disclosure_id: int,
        ai_summary: str,
        ai_importance_score: int,
        ai_tags: str | None,
        ai_risk_level: str | None,
        ai_event_type: str | None,
        ai_processed_at: str,
        ai_summary_error: str | None = None,
    ) -> None:
        item = self.get_by_id(disclosure_id)
        if not item:
            return
        item.ai_summary = ai_summary
        item.ai_importance_score = ai_importance_score
        item.ai_tags = ai_tags
        item.ai_risk_level = ai_risk_level
        item.ai_event_type = ai_event_type
        item.ai_processed_at = ai_processed_at
        item.ai_summary_error = ai_summary_error
        self.db.add(item)
        self.db.commit()

    def mark_ai_summary_failed(self, disclosure_id: int, error_message: str, ai_processed_at: str) -> None:
        item = self.get_by_id(disclosure_id)
        if not item:
            return
        item.ai_summary_error = error_message
        item.ai_processed_at = ai_processed_at
        self.db.add(item)
        self.db.commit()

    def bulk_create_skip_duplicates(self, items: list[Disclosure]) -> tuple[int, int]:
        saved = 0
        skipped = 0
        seen_receipts: set[str] = set()

        for item in items:
            receipt_no = (item.dart_receipt_no or "").strip()
            if receipt_no:
                if receipt_no in seen_receipts or self.get_by_receipt_no(receipt_no):
                    skipped += 1
                    continue
                seen_receipts.add(receipt_no)
            self.db.add(item)
            saved += 1

        self.db.commit()
        return saved, skipped
