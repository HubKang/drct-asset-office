from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class StockDailyTechnicalIndicator(Base):
    __tablename__ = "stock_daily_technical_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    trade_date: Mapped[str] = mapped_column(Text, nullable=False)

    rsi14: Mapped[float | None] = mapped_column(Float, nullable=True)

    macd: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_histogram: Mapped[float | None] = mapped_column(Float, nullable=True)

    bb_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_middle: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_close_position: Mapped[str | None] = mapped_column(Text, nullable=True)

    atr14: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr14_ratio_to_close: Mapped[float | None] = mapped_column(Float, nullable=True)

    ma5_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma10_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma20_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma60_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma120_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma240_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    volume_ma5: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ma20: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_5_20_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    calculation_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
