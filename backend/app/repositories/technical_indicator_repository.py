from __future__ import annotations

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.stock_daily_technical_indicator import StockDailyTechnicalIndicator


class TechnicalIndicatorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_daily_rows(self, stock_id: int, rows: list[dict]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO stock_daily_technical_indicators (
                stock_id, trade_date,
                rsi14, macd, macd_signal, macd_histogram,
                bb_upper, bb_middle, bb_lower, bb_width, bb_close_position,
                atr14, atr14_ratio_to_close,
                ma5_gap_pct, ma10_gap_pct, ma20_gap_pct, ma60_gap_pct, ma120_gap_pct, ma240_gap_pct,
                volume_ma5, volume_ma20, volume_5_20_ratio,
                calculation_version, created_at, updated_at
            ) VALUES (
                :stock_id, :trade_date,
                :rsi14, :macd, :macd_signal, :macd_histogram,
                :bb_upper, :bb_middle, :bb_lower, :bb_width, :bb_close_position,
                :atr14, :atr14_ratio_to_close,
                :ma5_gap_pct, :ma10_gap_pct, :ma20_gap_pct, :ma60_gap_pct, :ma120_gap_pct, :ma240_gap_pct,
                :volume_ma5, :volume_ma20, :volume_5_20_ratio,
                :calculation_version, :created_at, :updated_at
            )
            ON CONFLICT(stock_id, trade_date) DO UPDATE SET
                rsi14=excluded.rsi14,
                macd=excluded.macd,
                macd_signal=excluded.macd_signal,
                macd_histogram=excluded.macd_histogram,
                bb_upper=excluded.bb_upper,
                bb_middle=excluded.bb_middle,
                bb_lower=excluded.bb_lower,
                bb_width=excluded.bb_width,
                bb_close_position=excluded.bb_close_position,
                atr14=excluded.atr14,
                atr14_ratio_to_close=excluded.atr14_ratio_to_close,
                ma5_gap_pct=excluded.ma5_gap_pct,
                ma10_gap_pct=excluded.ma10_gap_pct,
                ma20_gap_pct=excluded.ma20_gap_pct,
                ma60_gap_pct=excluded.ma60_gap_pct,
                ma120_gap_pct=excluded.ma120_gap_pct,
                ma240_gap_pct=excluded.ma240_gap_pct,
                volume_ma5=excluded.volume_ma5,
                volume_ma20=excluded.volume_ma20,
                volume_5_20_ratio=excluded.volume_5_20_ratio,
                calculation_version=excluded.calculation_version,
                updated_at=excluded.updated_at
            """
        )
        now = now_kst()
        payload = []
        for row in rows:
            payload.append(
                {
                    "stock_id": stock_id,
                    "trade_date": row["trade_date"],
                    "rsi14": row.get("rsi14"),
                    "macd": row.get("macd"),
                    "macd_signal": row.get("macd_signal"),
                    "macd_histogram": row.get("macd_histogram"),
                    "bb_upper": row.get("bb_upper"),
                    "bb_middle": row.get("bb_middle"),
                    "bb_lower": row.get("bb_lower"),
                    "bb_width": row.get("bb_width"),
                    "bb_close_position": row.get("bb_close_position"),
                    "atr14": row.get("atr14"),
                    "atr14_ratio_to_close": row.get("atr14_ratio_to_close"),
                    "ma5_gap_pct": row.get("ma5_gap_pct"),
                    "ma10_gap_pct": row.get("ma10_gap_pct"),
                    "ma20_gap_pct": row.get("ma20_gap_pct"),
                    "ma60_gap_pct": row.get("ma60_gap_pct"),
                    "ma120_gap_pct": row.get("ma120_gap_pct"),
                    "ma240_gap_pct": row.get("ma240_gap_pct"),
                    "volume_ma5": row.get("volume_ma5"),
                    "volume_ma20": row.get("volume_ma20"),
                    "volume_5_20_ratio": row.get("volume_5_20_ratio"),
                    "calculation_version": row.get("calculation_version", "v1"),
                    "created_at": now,
                    "updated_at": now,
                }
            )
        try:
            self.db.execute(sql, payload)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(payload)

    def get_latest(self, stock_id: int) -> StockDailyTechnicalIndicator | None:
        stmt: Select[tuple[StockDailyTechnicalIndicator]] = (
            select(StockDailyTechnicalIndicator)
            .where(StockDailyTechnicalIndicator.stock_id == stock_id)
            .order_by(StockDailyTechnicalIndicator.trade_date.desc(), StockDailyTechnicalIndicator.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def count_by_stock(self, stock_id: int) -> int:
        stmt = select(func.count(StockDailyTechnicalIndicator.id)).where(
            StockDailyTechnicalIndicator.stock_id == stock_id
        )
        return int(self.db.scalar(stmt) or 0)

