from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class UsStock(Base):
    __tablename__ = "us_stocks"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_us_stocks_symbol_exchange"),
        Index("idx_us_stocks_active_type", "is_active", "stock_type"),
        Index("idx_us_stocks_exchange", "exchange"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_ko: Mapped[str | None] = mapped_column(Text, nullable=True)
    exchange: Mapped[str] = mapped_column(Text, nullable=False)
    stock_type: Mapped[str] = mapped_column(Text, nullable=False, default="COMMON")
    naver_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_synced_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    historical_price_status: Mapped[str] = mapped_column(Text, nullable=False, default="NOT_COLLECTED")
    historical_price_completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class UsStockDailyPrice(Base):
    __tablename__ = "us_stock_daily_prices"
    __table_args__ = (
        UniqueConstraint("us_stock_id", "trade_date", name="uq_us_stock_daily_prices_stock_date"),
        Index("idx_us_stock_daily_prices_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    us_stock_id: Mapped[int] = mapped_column(ForeignKey("us_stocks.id", ondelete="CASCADE"), nullable=False)
    trade_date: Mapped[str] = mapped_column(Text, nullable=False)
    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    high_price: Mapped[float] = mapped_column(Float, nullable=False)
    low_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="KIWOOM")
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
