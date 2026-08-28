from __future__ import annotations

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.telegram_item import TelegramItem, TelegramMessageExclusion
from backend.app.entities.telegram_source import TelegramSource


class TelegramRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sources(self, include_deleted: bool = False) -> list[TelegramSource]:
        stmt: Select[tuple[TelegramSource]] = select(TelegramSource)
        if not include_deleted:
            stmt = stmt.where(TelegramSource.is_deleted == 0)
        return list(self.db.scalars(stmt.order_by(TelegramSource.is_default.desc(), TelegramSource.id)).all())

    def get_source(self, source_id: int) -> TelegramSource | None:
        return self.db.get(TelegramSource, source_id)

    def get_source_by_channel_username(self, channel_username: str) -> TelegramSource | None:
        return self.db.scalar(select(TelegramSource).where(TelegramSource.channel_username == channel_username))

    def get_active_sources(self) -> list[TelegramSource]:
        stmt = select(TelegramSource).where(
            TelegramSource.is_active == 1, TelegramSource.is_deleted == 0
        ).order_by(TelegramSource.id)
        return list(self.db.scalars(stmt).all())

    def create_source(self, source: TelegramSource) -> TelegramSource:
        self.db.add(source); self.db.commit(); self.db.refresh(source)
        return source

    def update_source(self, source: TelegramSource, updates: dict) -> TelegramSource:
        for key, value in updates.items():
            setattr(source, key, value)
        source.updated_at = now_kst()
        self.db.add(source); self.db.commit(); self.db.refresh(source)
        return source

    def delete_source_physical(self, source: TelegramSource) -> None:
        self.db.delete(source); self.db.commit()

    def get_item(self, item_id: int) -> TelegramItem | None:
        return self.db.get(TelegramItem, item_id)

    def get_items(self, item_ids: list[int]) -> list[TelegramItem]:
        if not item_ids:
            return []
        return list(self.db.scalars(select(TelegramItem).where(TelegramItem.id.in_(item_ids))).all())

    def update_summary(self, item: TelegramItem, summary: str) -> TelegramItem:
        item.summary = summary
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_item_by_fingerprint(self, collection_date: str, fingerprint: str) -> TelegramItem | None:
        return self.db.scalar(select(TelegramItem).where(
            TelegramItem.collection_date == collection_date,
            TelegramItem.message_fingerprint == fingerprint,
        ))

    def is_excluded(self, exclusion_date: str, fingerprint: str) -> bool:
        return self.db.get(TelegramMessageExclusion, (exclusion_date, fingerprint)) is not None

    def cleanup_exclusions(self, target_date: str) -> int:
        result = self.db.execute(delete(TelegramMessageExclusion).where(
            TelegramMessageExclusion.exclusion_date != target_date
        ))
        self.db.commit()
        return int(result.rowcount or 0)

    def create_item(self, payload: dict) -> TelegramItem:
        item = TelegramItem(**payload)
        self.db.add(item); self.db.commit(); self.db.refresh(item)
        return item

    def delete_items_with_exclusion(self, item_ids: list[int]) -> int:
        if not item_ids:
            return 0
        rows = list(self.db.scalars(select(TelegramItem).where(TelegramItem.id.in_(item_ids))).all())
        try:
            for row in rows:
                self.db.execute(sqlite_insert(TelegramMessageExclusion).values(
                    exclusion_date=row.collection_date, message_fingerprint=row.message_fingerprint,
                ).on_conflict_do_nothing(index_elements=["exclusion_date", "message_fingerprint"]))
                self.db.delete(row)
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return len(rows)

    def list_items(self, date_from: str | None = None, date_to: str | None = None,
                   keyword: str | None = None, limit: int = 20, offset: int = 0
                   ) -> tuple[list[TelegramItem], int, int, int]:
        stmt = select(TelegramItem)
        count_stmt = select(func.count()).select_from(TelegramItem)
        conditions = []
        if date_from:
            conditions.append(TelegramItem.collection_date >= date_from)
        if date_to:
            conditions.append(TelegramItem.collection_date <= date_to)
        if keyword:
            escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            value = f"%{escaped}%"
            conditions.append(or_(TelegramItem.title.like(value, escape="\\"),
                                  TelegramItem.summary.like(value, escape="\\"),
                                  TelegramItem.source_url.like(value, escape="\\")))
        for condition in conditions:
            stmt = stmt.where(condition); count_stmt = count_stmt.where(condition)
        total = int(self.db.scalar(count_stmt) or 0)
        with_summary = int(self.db.scalar(count_stmt.where(TelegramItem.summary.is_not(None))) or 0)
        items = list(self.db.scalars(stmt.order_by(
            TelegramItem.message_at.desc(), TelegramItem.id.desc()
        ).limit(limit).offset(offset)).all())
        return items, total, with_summary, total - with_summary
