from __future__ import annotations

from sqlalchemy import Select, and_, func, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.stock import Stock
from backend.app.entities.stock_daily_price import StockDailyPrice
from backend.app.entities.watchlist import Watchlist


class StockPriceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_daily_rows(self, stock_id: int, source: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO stock_daily_prices (
                stock_id, trade_date,
                open_price, high_price, low_price, close_price,
                change_price, change_rate, volume, trading_value,
                source, created_at, updated_at
            ) VALUES (
                :stock_id, :trade_date,
                :open_price, :high_price, :low_price, :close_price,
                :change_price, :change_rate, :volume, :trading_value,
                :source, :created_at, :updated_at
            )
            ON CONFLICT(stock_id, trade_date) DO UPDATE SET
                open_price=excluded.open_price,
                high_price=excluded.high_price,
                low_price=excluded.low_price,
                close_price=excluded.close_price,
                change_price=excluded.change_price,
                change_rate=excluded.change_rate,
                volume=excluded.volume,
                trading_value=excluded.trading_value,
                source=excluded.source,
                updated_at=excluded.updated_at
            """
        )
        now = now_kst()
        params = []
        for row in rows:
            params.append(
                {
                    "stock_id": stock_id,
                    "trade_date": row["trade_date"],
                    "open_price": row.get("open_price"),
                    "high_price": row.get("high_price"),
                    "low_price": row.get("low_price"),
                    "close_price": row.get("close_price"),
                    "change_price": row.get("change_price"),
                    "change_rate": row.get("change_rate"),
                    "volume": row.get("volume"),
                    "trading_value": row.get("trading_value"),
                    "source": source,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        try:
            self.db.execute(sql, params)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(rows)

    def upsert_daily_prices(self, stock_id: int, source: str, rows: list[dict]) -> int:
        return self.upsert_daily_rows(stock_id=stock_id, source=source, rows=rows)

    def list_by_stock(
        self,
        stock_id: int,
        start_date: str | None,
        end_date: str | None,
        source: str | None,
        limit: int,
        offset: int,
    ) -> list[StockDailyPrice]:
        stmt: Select[tuple[StockDailyPrice]] = select(StockDailyPrice).where(StockDailyPrice.stock_id == stock_id)
        if start_date:
            stmt = stmt.where(StockDailyPrice.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(StockDailyPrice.trade_date <= end_date)
        if source:
            stmt = stmt.where(StockDailyPrice.source == source)
        stmt = stmt.order_by(StockDailyPrice.trade_date.desc(), StockDailyPrice.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def list_daily_prices(
        self,
        stock_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[StockDailyPrice]:
        return self.list_by_stock(stock_id=stock_id, start_date=start_date, end_date=end_date, source=source, limit=limit, offset=offset)

    def list_by_stock_with_technical_indicators(
        self,
        stock_id: int,
        start_date: str | None,
        end_date: str | None,
        source: str | None,
        limit: int,
        offset: int,
    ) -> list[dict]:
        where_clauses = ["p.stock_id = :stock_id"]
        params: dict[str, object] = {"stock_id": stock_id, "limit": limit, "offset": offset}
        if start_date:
            where_clauses.append("p.trade_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            where_clauses.append("p.trade_date <= :end_date")
            params["end_date"] = end_date
        if source:
            where_clauses.append("p.source = :source")
            params["source"] = source

        sql = text(
            f"""
            SELECT
                p.id, p.stock_id, p.trade_date,
                p.open_price, p.high_price, p.low_price, p.close_price,
                p.change_price, p.change_rate, p.volume, p.trading_value,
                p.ma5, p.ma10, p.ma20, p.ma60, p.ma120, p.ma240,
                p.source, p.created_at, p.updated_at,
                t.rsi14, t.macd, t.macd_signal, t.macd_histogram,
                t.bb_upper, t.bb_middle, t.bb_lower, t.bb_width, t.bb_close_position,
                t.atr14, t.atr14_ratio_to_close,
                t.ma20_gap_pct, t.volume_5_20_ratio,
                t.calculation_version AS technical_indicator_calculation_version
            FROM stock_daily_prices p
            LEFT JOIN stock_daily_technical_indicators t
              ON t.stock_id = p.stock_id
             AND t.trade_date = p.trade_date
            WHERE {" AND ".join(where_clauses)}
            ORDER BY p.trade_date DESC, p.id DESC
            LIMIT :limit OFFSET :offset
            """
        )
        rows = self.db.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def list_by_stock_asc(self, stock_id: int) -> list[StockDailyPrice]:
        stmt: Select[tuple[StockDailyPrice]] = (
            select(StockDailyPrice)
            .where(StockDailyPrice.stock_id == stock_id)
            .order_by(StockDailyPrice.trade_date.asc(), StockDailyPrice.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_prices_for_ma_calculation(self, stock_id: int) -> list[StockDailyPrice]:
        return self.list_by_stock_asc(stock_id=stock_id)

    def update_moving_averages(
        self,
        row_id: int,
        ma5: float | None,
        ma10: float | None,
        ma20: float | None,
        ma60: float | None,
        ma120: float | None,
        ma240: float | None,
    ) -> None:
        row = self.db.get(StockDailyPrice, row_id)
        if not row:
            return
        row.ma5 = ma5
        row.ma10 = ma10
        row.ma20 = ma20
        row.ma60 = ma60
        row.ma120 = ma120
        row.ma240 = ma240
        row.updated_at = now_kst()
        self.db.add(row)

    def commit(self) -> None:
        self.db.commit()

    def recalculate_change_rate_for_stock(self, stock_id: int, source: str, digits: int = 2) -> dict[str, int]:
        rows = (
            self.db.query(StockDailyPrice)
            .filter(StockDailyPrice.stock_id == stock_id, StockDailyPrice.source == source)
            .order_by(StockDailyPrice.trade_date.asc(), StockDailyPrice.id.asc())
            .all()
        )
        updated_count = 0
        null_count = 0
        prev_close: float | None = None
        for row in rows:
            close_price = None if row.close_price is None else float(row.close_price)
            next_rate: float | None
            if prev_close in (None, 0) or close_price is None:
                next_rate = None
            else:
                next_rate = round(((close_price - float(prev_close)) / float(prev_close)) * 100, digits)

            current_rate = None if row.change_rate is None else float(row.change_rate)
            changed = (current_rate is None and next_rate is not None) or (
                current_rate is not None and next_rate is None
            ) or (current_rate is not None and next_rate is not None and abs(current_rate - next_rate) >= 0.000001)

            if changed:
                row.change_rate = next_rate
                row.updated_at = now_kst()
                self.db.add(row)
                updated_count += 1
            if next_rate is None:
                null_count += 1
            prev_close = close_price

        self.db.commit()
        return {"row_count": len(rows), "updated_count": updated_count, "null_count": null_count}

    def list_distinct_stock_ids_by_source(self, source: str) -> list[int]:
        stmt = (
            select(StockDailyPrice.stock_id)
            .where(StockDailyPrice.source == source)
            .distinct()
            .order_by(StockDailyPrice.stock_id.asc())
        )
        return [int(x) for x in self.db.scalars(stmt).all()]

    def count_by_stock(self, stock_id: int) -> int:
        stmt = select(func.count(StockDailyPrice.id)).where(StockDailyPrice.stock_id == stock_id)
        return int(self.db.scalar(stmt) or 0)

    def count_prices_by_stock(self, stock_id: int, source: str | None = None) -> int:
        stmt = select(func.count(StockDailyPrice.id)).where(StockDailyPrice.stock_id == stock_id)
        if source:
            stmt = stmt.where(StockDailyPrice.source == source)
        return int(self.db.scalar(stmt) or 0)

    def get_latest_trade_date(self, stock_id: int, source: str | None = None) -> str | None:
        stmt = select(func.max(StockDailyPrice.trade_date)).where(StockDailyPrice.stock_id == stock_id)
        if source:
            stmt = stmt.where(StockDailyPrice.source == source)
        return self.db.scalar(stmt)

    def get_latest_trade_dates(self, stock_ids: list[int]) -> dict[int, str]:
        """Return each stock's latest stored date in one grouped query."""
        if not stock_ids:
            return {}
        stmt = (
            select(
                StockDailyPrice.stock_id,
                func.max(StockDailyPrice.trade_date).label("latest_trade_date"),
            )
            .where(StockDailyPrice.stock_id.in_(stock_ids))
            .group_by(StockDailyPrice.stock_id)
        )
        return {
            int(row.stock_id): str(row.latest_trade_date)
            for row in self.db.execute(stmt)
            if row.latest_trade_date
        }

    def get_trade_dates_in_window(self, stock_id: int, start_date: str, end_date: str) -> set[str]:
        stmt = select(StockDailyPrice.trade_date).where(
            StockDailyPrice.stock_id == stock_id,
            StockDailyPrice.trade_date >= start_date,
            StockDailyPrice.trade_date <= end_date,
        )
        return {str(value) for value in self.db.scalars(stmt).all()}

    def get_stock_summary_window(self, stock_id: int, source: str = "pykrx") -> dict | None:
        stmt = (
            select(
                func.count(StockDailyPrice.id).label("price_count"),
                func.min(StockDailyPrice.trade_date).label("min_trade_date"),
                func.max(StockDailyPrice.trade_date).label("max_trade_date"),
            )
            .where(StockDailyPrice.stock_id == stock_id, StockDailyPrice.source == source)
        )
        row = self.db.execute(stmt).mappings().one()
        if not row["price_count"]:
            return None
        return dict(row)

    def list_recent_rows(self, stock_id: int, source: str = "pykrx", limit: int = 252) -> list[StockDailyPrice]:
        return self.list_by_stock(
            stock_id=stock_id,
            start_date=None,
            end_date=None,
            source=source,
            limit=limit,
            offset=0,
        )

    def list_price_summary(
        self,
        keyword: str | None,
        market: str | None,
        source: str | None,
        scope: str | None,
        limit: int,
        offset: int,
    ) -> list[dict]:
        base_stmt = (
            select(
                StockDailyPrice.stock_id.label("stock_id"),
                func.count(StockDailyPrice.id).label("price_count"),
                func.min(StockDailyPrice.trade_date).label("min_trade_date"),
                func.max(StockDailyPrice.trade_date).label("max_trade_date"),
            )
            .group_by(StockDailyPrice.stock_id)
        )
        if source:
            base_stmt = base_stmt.where(StockDailyPrice.source == source)
        summary_subq = base_stmt.subquery()

        latest_subq = (
            select(
                StockDailyPrice.stock_id.label("stock_id"),
                StockDailyPrice.trade_date.label("trade_date"),
                StockDailyPrice.close_price.label("latest_close_price"),
                StockDailyPrice.volume.label("latest_volume"),
                StockDailyPrice.trading_value.label("latest_trading_value"),
                StockDailyPrice.ma5.label("latest_ma5"),
                StockDailyPrice.ma20.label("latest_ma20"),
                StockDailyPrice.ma60.label("latest_ma60"),
                StockDailyPrice.ma120.label("latest_ma120"),
                StockDailyPrice.ma240.label("latest_ma240"),
                StockDailyPrice.source.label("source"),
            )
            .join(
                summary_subq,
                and_(
                    StockDailyPrice.stock_id == summary_subq.c.stock_id,
                    StockDailyPrice.trade_date == summary_subq.c.max_trade_date,
                ),
            )
            .subquery()
        )

        stmt = (
            select(
                Stock.id.label("stock_id"),
                Stock.stock_code.label("stock_code"),
                Stock.stock_name.label("stock_name"),
                Stock.market.label("market"),
                Stock.security_type.label("security_type"),
                summary_subq.c.price_count,
                summary_subq.c.min_trade_date,
                summary_subq.c.max_trade_date,
                latest_subq.c.latest_close_price,
                latest_subq.c.latest_volume,
                latest_subq.c.latest_trading_value,
                latest_subq.c.latest_ma5,
                latest_subq.c.latest_ma20,
                latest_subq.c.latest_ma60,
                latest_subq.c.latest_ma120,
                latest_subq.c.latest_ma240,
                latest_subq.c.source,
            )
            .join(summary_subq, Stock.id == summary_subq.c.stock_id)
            .join(latest_subq, Stock.id == latest_subq.c.stock_id)
        )

        if (scope or "watchlist") == "watchlist":
            stmt = stmt.join(Watchlist, Watchlist.stock_id == Stock.id).where(Watchlist.is_active == 1)

        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where((Stock.stock_code.like(keyword_like)) | (Stock.stock_name.like(keyword_like)))
        if market:
            stmt = stmt.where(Stock.market == market)
        if source:
            stmt = stmt.where(latest_subq.c.source == source)

        stmt = stmt.order_by(summary_subq.c.max_trade_date.desc(), Stock.stock_name.asc()).limit(limit).offset(offset)
        rows = self.db.execute(stmt).mappings().all()
        return [dict(r) for r in rows]

    def get_unique_policy(self) -> dict:
        table_cols = self.db.execute(text("PRAGMA table_info(stock_daily_prices)")).mappings().all()
        index_rows = self.db.execute(text("PRAGMA index_list(stock_daily_prices)")).mappings().all()

        unique_indexes: list[dict] = []
        for idx in index_rows:
            if int(idx.get("unique") or 0) != 1:
                continue
            idx_name = str(idx.get("name") or "")
            cols = self.db.execute(text(f"PRAGMA index_info('{idx_name}')")).mappings().all()
            col_names = [str(c.get("name") or "") for c in cols]
            unique_indexes.append({"name": idx_name, "columns": col_names})

        has_stock_date_source = any(
            i["columns"] == ["stock_id", "trade_date", "source"] for i in unique_indexes
        )
        has_stock_date = any(i["columns"] == ["stock_id", "trade_date"] for i in unique_indexes)

        if has_stock_date_source:
            policy = "stock_id_trade_date_source"
        elif has_stock_date:
            policy = "stock_id_trade_date"
        else:
            policy = "unknown"

        return {
            "policy": policy,
            "columns": [str(c.get("name") or "") for c in table_cols],
            "unique_indexes": unique_indexes,
        }

    def list_source_summary_for_stock(self, stock_id: int) -> list[dict]:
        sql = text(
            """
            SELECT
                COALESCE(source, 'unknown') AS source,
                COUNT(*) AS cnt,
                MIN(trade_date) AS min_date,
                MAX(trade_date) AS max_date
            FROM stock_daily_prices
            WHERE stock_id = :stock_id
            GROUP BY COALESCE(source, 'unknown')
            ORDER BY source
            """
        )
        rows = self.db.execute(sql, {"stock_id": stock_id}).mappings().all()
        return [dict(r) for r in rows]

    def count_existing_rows_in_window_excluding_source(
        self,
        stock_id: int,
        start_date: str,
        end_date: str,
        source: str,
    ) -> int:
        sql = text(
            """
            SELECT COUNT(*) AS cnt
            FROM stock_daily_prices
            WHERE stock_id = :stock_id
              AND trade_date >= :start_date
              AND trade_date <= :end_date
              AND COALESCE(source, '') <> :source
            """
        )
        return int(
            self.db.execute(
                sql,
                {
                    "stock_id": stock_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "source": source,
                },
            ).scalar()
            or 0
        )
