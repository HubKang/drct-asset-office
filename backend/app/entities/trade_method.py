from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class TradeMethod(Base):
    __tablename__ = "trade_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    method_name: Mapped[str] = mapped_column(Text, nullable=False)
    core_concept: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    buy_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    sell_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    position_sizing_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    stop_loss_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    take_profit_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklist: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
