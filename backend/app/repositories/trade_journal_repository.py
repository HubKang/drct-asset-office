from __future__ import annotations

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.trade_journal import TradeJournal
from backend.app.entities.trade_journal_image import TradeJournalImage
from backend.app.entities.trade_method import TradeMethod


class TradeJournalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_trade_methods(self, is_active: int | None, keyword: str | None) -> list[TradeMethod]:
        stmt: Select[tuple[TradeMethod]] = select(TradeMethod)
        if is_active is not None:
            stmt = stmt.where(TradeMethod.is_active == is_active)
        if keyword:
            stmt = stmt.where(TradeMethod.method_name.like(f"%{keyword.strip()}%"))
        stmt = stmt.order_by(TradeMethod.sort_order.asc(), TradeMethod.id.asc())
        return list(self.db.scalars(stmt).all())

    def get_trade_method(self, method_id: int) -> TradeMethod | None:
        return self.db.get(TradeMethod, method_id)

    def create_trade_method(self, payload: dict) -> TradeMethod:
        item = TradeMethod(**payload)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_trade_method(self, item: TradeMethod, payload: dict) -> TradeMethod:
        for key, value in payload.items():
            setattr(item, key, value)
        item.updated_at = now_kst()
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def create_trade_journal(self, payload: dict) -> TradeJournal:
        item = TradeJournal(**payload)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_trade_journal(self, journal_id: int) -> TradeJournal | None:
        return self.db.get(TradeJournal, journal_id)

    def update_trade_journal(self, item: TradeJournal, payload: dict) -> TradeJournal:
        for key, value in payload.items():
            setattr(item, key, value)
        item.updated_at = now_kst()
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_trade_journal(self, item: TradeJournal) -> None:
        self.db.delete(item)
        self.db.commit()

    def list_trade_journals(
        self,
        start_date: str,
        end_date: str,
        stock_name: str | None,
        stock_theme: str | None,
        trade_method_id: int | None,
        result_type: str | None,
    ) -> tuple[list[tuple[TradeJournal, int]], int]:
        image_count_subq = (
            select(
                TradeJournalImage.trade_journal_id.label("trade_journal_id"),
                func.count(TradeJournalImage.id).label("image_count"),
            )
            .group_by(TradeJournalImage.trade_journal_id)
            .subquery()
        )
        stmt = (
            select(
                TradeJournal,
                func.coalesce(image_count_subq.c.image_count, 0),
            )
            .outerjoin(image_count_subq, image_count_subq.c.trade_journal_id == TradeJournal.id)
        )
        count_stmt = select(func.count()).select_from(TradeJournal)
        conditions = [
            TradeJournal.buy_date >= start_date,
            TradeJournal.buy_date <= end_date,
        ]
        if stock_name:
            conditions.append(TradeJournal.stock_name.like(f"%{stock_name.strip()}%"))
        if stock_theme:
            conditions.append(TradeJournal.stock_theme.like(f"%{stock_theme.strip()}%"))
        if trade_method_id is not None:
            conditions.append(TradeJournal.trade_method_id == trade_method_id)
        if result_type:
            conditions.append(TradeJournal.result_type == result_type.strip())

        stmt = stmt.where(and_(*conditions)).order_by(TradeJournal.buy_date.desc(), TradeJournal.id.desc())
        count_stmt = count_stmt.where(and_(*conditions))
        items = list(self.db.execute(stmt).all())
        total_count = int(self.db.scalar(count_stmt) or 0)
        return items, total_count

    def list_trade_journal_images(self, journal_id: int) -> list[TradeJournalImage]:
        stmt = (
            select(TradeJournalImage)
            .where(TradeJournalImage.trade_journal_id == journal_id)
            .order_by(TradeJournalImage.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def create_trade_journal_image(self, payload: dict) -> TradeJournalImage:
        item = TradeJournalImage(**payload)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_trade_journal_image(self, image_id: int) -> TradeJournalImage | None:
        return self.db.get(TradeJournalImage, image_id)

    def delete_trade_journal_image(self, image: TradeJournalImage) -> None:
        self.db.delete(image)
        self.db.commit()

    def list_calendar_monthly(self, month: str) -> list[tuple[str, int, int]]:
        stmt = (
            select(
                TradeJournal.buy_date.label("trade_date"),
                func.count(TradeJournal.id).label("trade_count"),
                func.coalesce(func.sum(TradeJournal.realized_profit), 0).label("realized_profit_sum"),
            )
            .where(TradeJournal.buy_date.like(f"{month}%"))
            .group_by(TradeJournal.buy_date)
            .order_by(TradeJournal.buy_date.asc())
        )
        return [(str(r[0]), int(r[1] or 0), int(r[2] or 0)) for r in self.db.execute(stmt).all()]

    def list_statistics_monthly(self, page: int, page_size: int) -> tuple[list[tuple], int]:
        month_col = func.substr(TradeJournal.buy_date, 1, 7)
        grouped = (
            select(
                month_col.label("trade_month"),
                func.count(TradeJournal.id).label("trade_count"),
                func.sum(case((TradeJournal.result_type == "profit", 1), else_=0)).label("profit_count"),
                func.sum(case((TradeJournal.result_type == "loss", 1), else_=0)).label("loss_count"),
                func.coalesce(func.sum(TradeJournal.realized_profit), 0).label("realized_profit_sum"),
                func.coalesce(func.avg(TradeJournal.profit_rate), 0.0).label("avg_profit_rate"),
            )
            .group_by(month_col)
            .order_by(month_col.desc())
        ).subquery()
        total = int(self.db.scalar(select(func.count()).select_from(grouped)) or 0)
        offset = max(0, (page - 1) * page_size)
        stmt = select(grouped).order_by(grouped.c.trade_month.desc()).offset(offset).limit(page_size)
        rows = self.db.execute(stmt).all()
        return rows, total
