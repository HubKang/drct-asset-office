from __future__ import annotations

from sqlalchemy import Select, case, delete, func, not_, or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.app.entities.disclosure import Disclosure, DisclosureItemExclusion, StockDisclosureCollectionState
from backend.app.entities.stock import Stock
from backend.app.entities.watchlist import Watchlist


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

    def update_summary_text(self, disclosure_id: int, summary: str | None) -> None:
        item = self.get_by_id(disclosure_id)
        if not item:
            return
        item.summary = summary
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

    def delete_by_ids(self, disclosure_ids: list[int]) -> int:
        if not disclosure_ids:
            return 0
        stmt: Select[tuple[Disclosure]] = select(Disclosure).where(Disclosure.id.in_(disclosure_ids))
        rows = list(self.db.scalars(stmt).all())
        for item in rows:
            self.db.delete(item)
        self.db.commit()
        return len(rows)

    def delete_by_ids_with_exclusion(self, disclosure_ids: list[int], exclusion_date: str) -> int:
        if not disclosure_ids:
            return 0
        rows = list(self.db.scalars(select(Disclosure).where(Disclosure.id.in_(disclosure_ids))).all())
        exclusions = [
            {"exclusion_date": exclusion_date, "stock_id": row.stock_id, "rcept_no": row.dart_receipt_no.strip()}
            for row in rows
            if row.dart_receipt_no and row.dart_receipt_no.strip()
        ]
        try:
            if exclusions:
                self.db.execute(
                    sqlite_insert(DisclosureItemExclusion)
                    .values(exclusions)
                    .on_conflict_do_nothing(index_elements=["exclusion_date", "stock_id", "rcept_no"])
                )
            if rows:
                self.db.execute(delete(Disclosure).where(Disclosure.id.in_([row.id for row in rows])))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(rows)

    def bulk_create_skip_duplicates(self, items: list[Disclosure]) -> tuple[int, int]:
        receipts = {(item.dart_receipt_no or "").strip() for item in items if (item.dart_receipt_no or "").strip()}
        existing = self.list_existing_receipts(receipts)
        saved = 0
        skipped = 0
        seen_receipts: set[str] = set()
        for item in items:
            receipt_no = (item.dart_receipt_no or "").strip()
            if receipt_no and (receipt_no in seen_receipts or receipt_no in existing):
                skipped += 1
                continue
            if receipt_no:
                seen_receipts.add(receipt_no)
            self.db.add(item)
            saved += 1
        self.db.commit()
        return saved, skipped

    def list_existing_receipts(self, receipt_nos: set[str]) -> set[str]:
        if not receipt_nos:
            return set()
        return set(self.db.scalars(select(Disclosure.dart_receipt_no).where(Disclosure.dart_receipt_no.in_(receipt_nos))).all())

    def get_collection_states(self, stock_ids: list[int]) -> dict[int, StockDisclosureCollectionState]:
        if not stock_ids:
            return {}
        rows = self.db.scalars(select(StockDisclosureCollectionState).where(StockDisclosureCollectionState.stock_id.in_(stock_ids))).all()
        return {row.stock_id: row for row in rows}

    def list_today_exclusions(self, exclusion_date: str, stock_ids: list[int]) -> set[tuple[int, str]]:
        if not stock_ids:
            return set()
        rows = self.db.execute(
            select(DisclosureItemExclusion.stock_id, DisclosureItemExclusion.rcept_no).where(
                DisclosureItemExclusion.exclusion_date == exclusion_date,
                DisclosureItemExclusion.stock_id.in_(stock_ids),
            )
        ).all()
        return {(stock_id, rcept_no) for stock_id, rcept_no in rows}

    def cleanup_expired_exclusions(self, exclusion_date: str) -> int:
        result = self.db.execute(delete(DisclosureItemExclusion).where(DisclosureItemExclusion.exclusion_date != exclusion_date))
        self.db.commit()
        return int(result.rowcount or 0)

    def save_collection_result(
        self,
        items: list[Disclosure],
        stock_id: int,
        completed_date: str,
        completed_at: str,
        excluded_receipts: set[str],
    ) -> tuple[int, int, int]:
        receipts = {(item.dart_receipt_no or "").strip() for item in items if (item.dart_receipt_no or "").strip()}
        existing = self.list_existing_receipts(receipts)
        seen: set[str] = set()
        saved = duplicate_skipped = excluded_skipped = 0
        try:
            for item in items:
                receipt_no = (item.dart_receipt_no or "").strip()
                if receipt_no in excluded_receipts:
                    excluded_skipped += 1
                    continue
                if receipt_no in existing or receipt_no in seen:
                    duplicate_skipped += 1
                    continue
                seen.add(receipt_no)
                self.db.add(item)
                saved += 1
            self.db.execute(
                sqlite_insert(StockDisclosureCollectionState)
                .values(
                    stock_id=stock_id,
                    last_successful_collection_date=completed_date,
                    last_successful_at=completed_at,
                )
                .on_conflict_do_update(
                    index_elements=["stock_id"],
                    set_={
                        "last_successful_collection_date": completed_date,
                        "last_successful_at": completed_at,
                    },
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return saved, duplicate_skipped, excluded_skipped

    def list_collection_targets(self) -> list[dict]:
        summarized = case((or_(Disclosure.ai_summary.is_not(None), Disclosure.summary.is_not(None)), 1), else_=0)
        rows = self.db.execute(
            select(
                Stock.id,
                Stock.stock_code,
                Stock.stock_name,
                func.count(Disclosure.id),
                func.coalesce(func.sum(summarized), 0),
                StockDisclosureCollectionState.last_successful_collection_date,
                StockDisclosureCollectionState.last_successful_at,
            )
            .join(Watchlist, Watchlist.stock_id == Stock.id)
            .outerjoin(Disclosure, Disclosure.stock_id == Stock.id)
            .outerjoin(StockDisclosureCollectionState, StockDisclosureCollectionState.stock_id == Stock.id)
            .where(Watchlist.is_active == 1)
            .group_by(Stock.id, Stock.stock_code, Stock.stock_name, StockDisclosureCollectionState.last_successful_collection_date, StockDisclosureCollectionState.last_successful_at)
            .order_by(Stock.stock_name.asc())
        ).all()
        return [
            {
                "stock_id": row[0], "stock_code": row[1], "stock_name": row[2],
                "disclosure_count": int(row[3] or 0), "summarized_count": int(row[4] or 0),
                "last_successful_collection_date": row[5], "last_successful_at": row[6],
            }
            for row in rows
        ]
