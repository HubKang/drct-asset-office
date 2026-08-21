from __future__ import annotations

from sqlalchemy import Select, case, func, or_, select, text
from sqlalchemy.orm import Session

from backend.app.entities.us_stock import UsStock


class UsStockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, stock_id: int) -> UsStock | None:
        return self.db.get(UsStock, stock_id)

    def get_by_symbol_exchange(self, symbol: str, exchange: str) -> UsStock | None:
        return self.db.scalar(select(UsStock).where(UsStock.symbol == symbol, UsStock.exchange == exchange))

    def list(self, *, keyword: str | None, exchange: str | None, stock_type: str | None, is_active: int | None, price_status: str | None, limit: int, offset: int) -> tuple[list[UsStock], int]:
        filters = []
        if keyword:
            term = f"%{keyword.strip()}%"
            filters.append(or_(UsStock.symbol.like(term), UsStock.name.like(term), UsStock.name_ko.like(term)))
        if exchange:
            filters.append(UsStock.exchange == exchange)
        if stock_type:
            filters.append(UsStock.stock_type == stock_type)
        if is_active is not None:
            filters.append(UsStock.is_active == is_active)
        if price_status:
            filters.append(UsStock.historical_price_status == price_status)
        stmt: Select[tuple[UsStock]] = select(UsStock).where(*filters).order_by(UsStock.symbol.asc(), UsStock.id.asc())
        total = int(self.db.scalar(select(func.count()).select_from(UsStock).where(*filters)) or 0)
        return list(self.db.scalars(stmt.limit(limit).offset(offset)).all()), total

    def summary(self) -> dict[str, object]:
        total, active, common, etf = self.db.execute(
            select(
                func.count(UsStock.id),
                func.sum(case((UsStock.is_active == 1, 1), else_=0)),
                func.sum(case((UsStock.stock_type == "COMMON", 1), else_=0)),
                func.sum(case((UsStock.stock_type == "ETF", 1), else_=0)),
            )
        ).one()
        price_counts = self.db.execute(text("""
            SELECT
              SUM(CASE WHEN historical_price_status='COMPLETE' THEN 1 ELSE 0 END) complete,
              SUM(CASE WHEN historical_price_status='NOT_COLLECTED' THEN 1 ELSE 0 END) not_collected,
              SUM(CASE WHEN historical_price_status='PARTIAL' THEN 1 ELSE 0 END) partial,
              SUM(CASE WHEN historical_price_status='ERROR' THEN 1 ELSE 0 END) error
            FROM us_stocks WHERE is_active=1
        """)).mappings().one()
        latest_date = self.db.scalar(text("SELECT MAX(trade_date) FROM us_stock_daily_prices"))
        return {"total": int(total or 0), "active": int(active or 0), "common": int(common or 0), "etf": int(etf or 0), "price_complete": int(price_counts["complete"] or 0), "price_not_collected": int(price_counts["not_collected"] or 0), "price_partial": int(price_counts["partial"] or 0), "price_error": int(price_counts["error"] or 0), "latest_price_date": str(latest_date) if latest_date else None}

    def latest_prices(self, stock_ids: list[int]) -> dict[int, dict[str, object]]:
        if not stock_ids:
            return {}
        placeholders = ",".join(f":stock_{index}" for index, _ in enumerate(stock_ids))
        params = {f"stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        rows = self.db.execute(text(f"""
            SELECT p.us_stock_id,p.trade_date,p.close_price,
                   (SELECT COUNT(*) FROM us_stock_daily_prices pc WHERE pc.us_stock_id=p.us_stock_id) row_count,
                   (SELECT p2.close_price FROM us_stock_daily_prices p2
                    WHERE p2.us_stock_id=p.us_stock_id AND p2.trade_date<p.trade_date
                    ORDER BY p2.trade_date DESC LIMIT 1) previous_close
            FROM us_stock_daily_prices p
            WHERE p.us_stock_id IN ({placeholders})
              AND p.trade_date=(SELECT MAX(p3.trade_date) FROM us_stock_daily_prices p3 WHERE p3.us_stock_id=p.us_stock_id)
        """), params).mappings().all()
        return {int(row["us_stock_id"]): dict(row) for row in rows}

    def create(self, stock: UsStock) -> UsStock:
        self.db.add(stock)
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def create_many(self, stocks: list[UsStock]) -> list[UsStock]:
        self.db.add_all(stocks)
        self.db.commit()
        for stock in stocks:
            self.db.refresh(stock)
        return stocks

    def update(self, stock: UsStock) -> UsStock:
        self.db.commit()
        self.db.refresh(stock)
        return stock
