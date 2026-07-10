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
                total_equity, operating_cash_flow, value_type, calculation_method,
                source_report_code, source_period_label, report_code, created_at, updated_at
            ) VALUES (
                :stock_id, :stock_code, :statement_type, :fiscal_year, :fiscal_quarter,
                :period_label, :period_end_date, :source_type, :source_method,
                :revenue, :operating_profit, :net_income, :total_assets, :total_liabilities,
                :total_equity, :operating_cash_flow, :value_type, :calculation_method,
                :source_report_code, :source_period_label, :report_code, :created_at, :updated_at
            ) ON CONFLICT(stock_id, statement_type, fiscal_year, fiscal_quarter, source_method) DO UPDATE SET
                period_label=excluded.period_label, period_end_date=excluded.period_end_date,
                revenue=excluded.revenue, operating_profit=excluded.operating_profit,
                net_income=excluded.net_income, total_assets=excluded.total_assets,
                total_liabilities=excluded.total_liabilities, total_equity=excluded.total_equity,
                operating_cash_flow=excluded.operating_cash_flow, value_type=excluded.value_type,
                calculation_method=excluded.calculation_method, source_report_code=excluded.source_report_code,
                source_period_label=excluded.source_period_label, report_code=excluded.report_code,
                updated_at=excluded.updated_at
        """), values)


    def upsert_external_identifier(self, values: dict[str, Any]) -> None:
        self.db.execute(text("""
            INSERT INTO stock_external_identifiers (
                stock_id, stock_code, corp_code, corp_name, source_type, source_method,
                mapped_at, created_at, updated_at
            ) VALUES (
                :stock_id, :stock_code, :corp_code, :corp_name, :source_type, :source_method,
                :mapped_at, :created_at, :updated_at
            ) ON CONFLICT(stock_code, source_type) DO UPDATE SET
                stock_id=excluded.stock_id, corp_code=excluded.corp_code, corp_name=excluded.corp_name,
                source_method=excluded.source_method, mapped_at=excluded.mapped_at, updated_at=excluded.updated_at
        """), values)

    def get_external_identifier(self, stock_code: str, source_type: str = "OPENDART") -> dict[str, Any] | None:
        row = self.db.execute(text("""
            SELECT * FROM stock_external_identifiers
            WHERE stock_code=:stock_code AND source_type=:source_type
            ORDER BY id DESC LIMIT 1
        """), {"stock_code": stock_code, "source_type": source_type}).mappings().first()
        return dict(row) if row else None

    def upsert_shareholder_snapshot(self, values: dict[str, Any]) -> None:
        self.db.execute(text("""
            INSERT INTO stock_shareholder_snapshots (
                stock_id, stock_code, snapshot_date, source_type, source_method, report_code, receipt_no,
                largest_shareholder_name, largest_shareholder_shares, largest_shareholder_ratio,
                major_shareholder_name, major_shareholder_shares, major_shareholder_ratio,
                ownership_change_flag, notes, created_at, updated_at
            ) VALUES (
                :stock_id, :stock_code, :snapshot_date, :source_type, :source_method, :report_code, :receipt_no,
                :largest_shareholder_name, :largest_shareholder_shares, :largest_shareholder_ratio,
                :major_shareholder_name, :major_shareholder_shares, :major_shareholder_ratio,
                :ownership_change_flag, :notes, :created_at, :updated_at
            ) ON CONFLICT(stock_id, snapshot_date, source_method) DO UPDATE SET
                report_code=excluded.report_code, receipt_no=excluded.receipt_no,
                largest_shareholder_name=excluded.largest_shareholder_name,
                largest_shareholder_shares=excluded.largest_shareholder_shares,
                largest_shareholder_ratio=excluded.largest_shareholder_ratio,
                major_shareholder_name=excluded.major_shareholder_name,
                major_shareholder_shares=excluded.major_shareholder_shares,
                major_shareholder_ratio=excluded.major_shareholder_ratio,
                ownership_change_flag=excluded.ownership_change_flag, notes=excluded.notes,
                updated_at=excluded.updated_at
        """), values)

    def upsert_shareholder_change(self, values: dict[str, Any]) -> None:
        self.db.execute(text("""
            INSERT INTO stock_shareholder_changes (
                stock_id, stock_code, report_date, source_type, source_method, report_type, receipt_no,
                reporter_name, shares, ratio, previous_ratio, change_flag, reason, created_at, updated_at
            ) VALUES (
                :stock_id, :stock_code, :report_date, :source_type, :source_method, :report_type, :receipt_no,
                :reporter_name, :shares, :ratio, :previous_ratio, :change_flag, :reason, :created_at, :updated_at
            ) ON CONFLICT(stock_id, report_date, source_method, receipt_no) DO UPDATE SET
                report_type=excluded.report_type, reporter_name=excluded.reporter_name, shares=excluded.shares,
                ratio=excluded.ratio, previous_ratio=excluded.previous_ratio, change_flag=excluded.change_flag,
                reason=excluded.reason, updated_at=excluded.updated_at
        """), values)

    def latest_shareholder_snapshot(self, stock_id: int) -> dict[str, Any] | None:
        row = self.db.execute(text("""
            SELECT * FROM stock_shareholder_snapshots
            WHERE stock_id=:stock_id ORDER BY snapshot_date DESC, id DESC LIMIT 1
        """), {"stock_id": stock_id}).mappings().first()
        return dict(row) if row else None

    def latest_snapshot(self, stock_id: int) -> dict[str, Any] | None:
        row=self.db.execute(text("SELECT * FROM stock_financial_snapshots WHERE stock_id=:stock_id ORDER BY snapshot_date DESC, id DESC LIMIT 1"), {"stock_id": stock_id}).mappings().first()
        return dict(row) if row else None

    def list_statements(self, stock_id: int, statement_type: str, limit: int) -> list[dict[str, Any]]:
        rows=self.db.execute(text("""SELECT period_label, period_end_date, revenue, operating_profit, net_income,
            total_assets, total_liabilities, total_equity, operating_cash_flow, source_method,
            value_type, calculation_method, source_report_code, source_period_label, report_code
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
