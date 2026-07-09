from __future__ import annotations

from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session


class StockFinancialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_snapshot(self, values: dict[str, Any]) -> None:
        self.db.execute(text("""
            INSERT INTO stock_financial_snapshots (
                stock_id, stock_code, snapshot_date, source_type, source_method,
                current_price, market_cap, listed_shares, per, pbr, eps, bps, roe,
                debt_ratio, reserve_ratio, created_at, updated_at
            ) VALUES (
                :stock_id, :stock_code, :snapshot_date, :source_type, :source_method,
                :current_price, :market_cap, :listed_shares, :per, :pbr, :eps, :bps, :roe,
                :debt_ratio, :reserve_ratio, :created_at, :updated_at
            ) ON CONFLICT(stock_id, snapshot_date, source_method) DO UPDATE SET
                current_price=excluded.current_price, market_cap=excluded.market_cap,
                listed_shares=excluded.listed_shares, per=excluded.per, pbr=excluded.pbr,
                eps=excluded.eps, bps=excluded.bps, roe=excluded.roe,
                debt_ratio=excluded.debt_ratio, reserve_ratio=excluded.reserve_ratio,
                updated_at=excluded.updated_at
        """), values)

    def upsert_statement(self, values: dict[str, Any]) -> None:
        self.db.execute(text("""
            INSERT INTO stock_financial_statements (
                stock_id, stock_code, statement_type, fiscal_year, fiscal_quarter,
                period_label, period_end_date, source_type, source_method,
                revenue, operating_profit, net_income, total_assets, total_liabilities,
                total_equity, operating_cash_flow, created_at, updated_at
            ) VALUES (
                :stock_id, :stock_code, :statement_type, :fiscal_year, :fiscal_quarter,
                :period_label, :period_end_date, :source_type, :source_method,
                :revenue, :operating_profit, :net_income, :total_assets, :total_liabilities,
                :total_equity, :operating_cash_flow, :created_at, :updated_at
            ) ON CONFLICT(stock_id, statement_type, fiscal_year, fiscal_quarter, source_method) DO UPDATE SET
                period_label=excluded.period_label, period_end_date=excluded.period_end_date,
                revenue=excluded.revenue, operating_profit=excluded.operating_profit,
                net_income=excluded.net_income, updated_at=excluded.updated_at
        """), values)

    def latest_snapshot(self, stock_id: int) -> dict[str, Any] | None:
        row=self.db.execute(text("SELECT * FROM stock_financial_snapshots WHERE stock_id=:stock_id ORDER BY snapshot_date DESC, id DESC LIMIT 1"), {"stock_id": stock_id}).mappings().first()
        return dict(row) if row else None

    def list_statements(self, stock_id: int, statement_type: str, limit: int) -> list[dict[str, Any]]:
        rows=self.db.execute(text("""SELECT period_label, period_end_date, revenue, operating_profit, net_income,
            total_assets, total_liabilities, total_equity, operating_cash_flow, source_method
            FROM stock_financial_statements WHERE stock_id=:stock_id AND statement_type=:statement_type
            ORDER BY fiscal_year DESC, fiscal_quarter DESC LIMIT :limit"""),
            {"stock_id": stock_id, "statement_type": statement_type, "limit": limit}).mappings().all()
        return list(reversed([dict(row) for row in rows]))

    def latest_foreign_holding(self, stock_id: int) -> dict[str, Any] | None:
        row=self.db.execute(text("""SELECT flow_date AS snapshot_date, foreign_holding_qty, foreign_holding_ratio
            FROM stock_investor_flows WHERE stock_id=:stock_id AND is_real_investor_flow=1
            AND foreign_holding_ratio IS NOT NULL ORDER BY flow_date DESC, id DESC LIMIT 1"""), {"stock_id": stock_id}).mappings().first()
        return dict(row) if row else None

    def commit(self) -> None:
        self.db.commit()
