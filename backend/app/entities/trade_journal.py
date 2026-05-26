from __future__ import annotations

from sqlalchemy import Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class TradeJournal(Base):
    __tablename__ = "trade_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buy_date: Mapped[str] = mapped_column(Text, nullable=False)
    sell_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock_name: Mapped[str] = mapped_column(Text, nullable=False)
    stock_theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    trade_method_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trade_method_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    profit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_profit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buy_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buy_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sell_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sell_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trade_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
