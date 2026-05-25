from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class StockDailyMarketMetric(Base):
    __tablename__ = "stock_daily_market_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    trade_date: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listed_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trading_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trading_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_cap_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trading_value_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_trading_value_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trading_value_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_trading_value_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    foreign_ownership_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
