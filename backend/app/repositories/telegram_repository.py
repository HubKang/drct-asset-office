from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.telegram_daily_summary import TelegramDailySummary
from backend.app.entities.telegram_item import TelegramItem
from backend.app.entities.telegram_source import TelegramSource


class TelegramRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sources(self, include_deleted: bool = False) -> list[TelegramSource]:
        stmt: Select[tuple[TelegramSource]] = select(TelegramSource)
        if not include_deleted:
            stmt = stmt.where(TelegramSource.is_deleted == 0)
        stmt = stmt.order_by(TelegramSource.is_default.desc(), TelegramSource.id.asc())
        return list(self.db.scalars(stmt).all())

    def get_source(self, source_id: int) -> TelegramSource | None:
        return self.db.get(TelegramSource, source_id)

    def get_source_by_channel_username(self, channel_username: str) -> TelegramSource | None:
        stmt = select(TelegramSource).where(TelegramSource.channel_username == channel_username)
        return self.db.scalar(stmt)

    def get_active_sources(self) -> list[TelegramSource]:
        stmt: Select[tuple[TelegramSource]] = (
            select(TelegramSource)
            .where(TelegramSource.is_active == 1, TelegramSource.is_deleted == 0)
            .order_by(TelegramSource.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def create_source(self, source: TelegramSource) -> TelegramSource:
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def update_source(self, source: TelegramSource, updates: dict) -> TelegramSource:
        for key, value in updates.items():
            setattr(source, key, value)
        source.updated_at = now_kst()
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def count_items_by_source(self, source_id: int) -> int:
        stmt = select(func.count()).select_from(TelegramItem).where(TelegramItem.source_id == source_id)
        return int(self.db.scalar(stmt) or 0)

    def delete_source_physical(self, source: TelegramSource) -> None:
        self.db.delete(source)
        self.db.commit()

    def get_item_by_source_message_id(self, source_id: int, telegram_message_id: int) -> TelegramItem | None:
        stmt = select(TelegramItem).where(
            TelegramItem.source_id == source_id,
            TelegramItem.telegram_message_id == telegram_message_id,
        )
        return self.db.scalar(stmt)

    def get_item_by_source_normalized_url(self, source_id: int, normalized_url: str) -> TelegramItem | None:
        if not normalized_url.strip():
            return None
        stmt = select(TelegramItem).where(
            TelegramItem.source_id == source_id,
            TelegramItem.normalized_url == normalized_url.strip(),
        )
        return self.db.scalar(stmt)

    def create_item(self, payload: dict) -> TelegramItem:
        item = TelegramItem(**payload)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(self, item: TelegramItem, payload: dict) -> TelegramItem:
        for key, value in payload.items():
            setattr(item, key, value)
        item.updated_at = now_kst()
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_item(self, item_id: int) -> TelegramItem | None:
        return self.db.get(TelegramItem, item_id)

    def delete_item(self, item: TelegramItem) -> None:
        self.db.delete(item)
        self.db.commit()

    def delete_items_by_ids(self, item_ids: list[int]) -> int:
        if not item_ids:
            return 0
        stmt = select(TelegramItem).where(TelegramItem.id.in_(item_ids))
        rows = list(self.db.scalars(stmt).all())
        for row in rows:
            self.db.delete(row)
        self.db.commit()
        return len(rows)

    def list_items(
        self,
        source_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        keyword: str | None = None,
        message_type: str | None = None,
        tag: str | None = None,
        sentiment: str | None = None,
        risk_level: str | None = None,
        event_type: str | None = None,
        related_stock_name: str | None = None,
        related_theme: str | None = None,
        summary_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TelegramItem], int]:
        stmt: Select[tuple[TelegramItem]] = select(TelegramItem)
        count_stmt = select(func.count()).select_from(TelegramItem)

        conditions = []
        if source_id is not None:
            conditions.append(TelegramItem.source_id == source_id)
        if date_from:
            conditions.append(TelegramItem.message_date >= f"{date_from} 00:00:00")
        if date_to:
            conditions.append(TelegramItem.message_date <= f"{date_to} 23:59:59")
        if keyword:
            like_value = f"%{keyword}%"
            conditions.append(or_(TelegramItem.message_text.like(like_value), TelegramItem.summary_text.like(like_value)))
        if message_type:
            conditions.append(TelegramItem.message_type == message_type)
        if tag:
            conditions.append(TelegramItem.tag == tag)
        if sentiment:
            conditions.append(TelegramItem.sentiment == sentiment)
        if risk_level:
            conditions.append(TelegramItem.risk_level == risk_level)
        if event_type:
            conditions.append(TelegramItem.event_type == event_type)
        if related_stock_name:
            conditions.append(TelegramItem.related_stock_name.like(f"%{related_stock_name}%"))
        if related_theme:
            conditions.append(TelegramItem.related_theme.like(f"%{related_theme}%"))
        if summary_status:
            conditions.append(TelegramItem.summary_status == summary_status)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        stmt = stmt.order_by(TelegramItem.id.desc()).limit(limit).offset(offset)
        items = list(self.db.scalars(stmt).all())
        total_count = int(self.db.scalar(count_stmt) or 0)
        return items, total_count

    def get_source_name_map(self, source_ids: Iterable[int]) -> dict[int, str]:
        target_ids = list(set(source_ids))
        if not target_ids:
            return {}
        rows = self.db.execute(
            select(TelegramSource.id, TelegramSource.source_name).where(TelegramSource.id.in_(target_ids))
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}

    def upsert_daily_summary(self, payload: dict) -> TelegramDailySummary:
        source_id = payload["source_id"]
        summary_date = payload["summary_date"]
        stmt = select(TelegramDailySummary).where(
            TelegramDailySummary.summary_date == summary_date,
            TelegramDailySummary.source_id == source_id,
        )
        existing = self.db.scalar(stmt)
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            existing.updated_at = now_kst()
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        record = TelegramDailySummary(**payload)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    @staticmethod
    def parse_json_array(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if str(v).strip()]
        except Exception:
            return []
        return []
