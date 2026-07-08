from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class StockInvestorFlowRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_flow(self, row: dict[str, Any]) -> None:
        payload = dict(row)
        payload.setdefault("data_source_type", "DERIVED_PRICE_FLOW" if payload.get("source") == "derived_price_flow" else "KIWOOM_REAL")
        payload.setdefault("source_method", payload.get("source") or "derived_price_flow")
        payload.setdefault("is_real_investor_flow", 1 if payload.get("data_source_type") == "KIWOOM_REAL" else 0)
        payload["is_real_investor_flow"] = 1 if payload.get("is_real_investor_flow") is True else int(payload.get("is_real_investor_flow") or 0)
        raw_json = payload.get("raw_json")
        payload["raw_json"] = json.dumps(raw_json, ensure_ascii=False) if raw_json else None
        self.db.execute(
            text(
                """
                INSERT INTO stock_investor_flows (
                    stock_id, stock_code, flow_date,
                    foreign_buy_qty, foreign_sell_qty, foreign_net_qty,
                    foreign_buy_amount, foreign_sell_amount, foreign_net_amount,
                    foreign_holding_qty, foreign_holding_ratio,
                    institution_buy_qty, institution_sell_qty, institution_net_qty,
                    institution_buy_amount, institution_sell_amount, institution_net_amount,
                    financial_investment_net_qty, insurance_net_qty, investment_trust_net_qty,
                    bank_net_qty, other_finance_net_qty, pension_fund_net_qty,
                    private_fund_net_qty, other_corporation_net_qty,
                    program_buy_qty, program_sell_qty, program_net_qty,
                    program_buy_amount, program_sell_amount, program_net_amount,
                    program_arbitrage_net_qty, program_non_arbitrage_net_qty,
                    source, data_source_type, source_method, is_real_investor_flow,
                    collection_status, raw_json, created_at, updated_at
                ) VALUES (
                    :stock_id, :stock_code, :flow_date,
                    :foreign_buy_qty, :foreign_sell_qty, :foreign_net_qty,
                    :foreign_buy_amount, :foreign_sell_amount, :foreign_net_amount,
                    :foreign_holding_qty, :foreign_holding_ratio,
                    :institution_buy_qty, :institution_sell_qty, :institution_net_qty,
                    :institution_buy_amount, :institution_sell_amount, :institution_net_amount,
                    :financial_investment_net_qty, :insurance_net_qty, :investment_trust_net_qty,
                    :bank_net_qty, :other_finance_net_qty, :pension_fund_net_qty,
                    :private_fund_net_qty, :other_corporation_net_qty,
                    :program_buy_qty, :program_sell_qty, :program_net_qty,
                    :program_buy_amount, :program_sell_amount, :program_net_amount,
                    :program_arbitrage_net_qty, :program_non_arbitrage_net_qty,
                    :source, :data_source_type, :source_method, :is_real_investor_flow,
                    :collection_status, :raw_json, :created_at, :updated_at
                )
                ON CONFLICT(stock_id, flow_date) DO UPDATE SET
                    stock_code=excluded.stock_code,
                    foreign_buy_qty=excluded.foreign_buy_qty,
                    foreign_sell_qty=excluded.foreign_sell_qty,
                    foreign_net_qty=excluded.foreign_net_qty,
                    foreign_buy_amount=excluded.foreign_buy_amount,
                    foreign_sell_amount=excluded.foreign_sell_amount,
                    foreign_net_amount=excluded.foreign_net_amount,
                    foreign_holding_qty=COALESCE(excluded.foreign_holding_qty, stock_investor_flows.foreign_holding_qty),
                    foreign_holding_ratio=COALESCE(excluded.foreign_holding_ratio, stock_investor_flows.foreign_holding_ratio),
                    institution_buy_qty=excluded.institution_buy_qty,
                    institution_sell_qty=excluded.institution_sell_qty,
                    institution_net_qty=excluded.institution_net_qty,
                    institution_buy_amount=excluded.institution_buy_amount,
                    institution_sell_amount=excluded.institution_sell_amount,
                    institution_net_amount=excluded.institution_net_amount,
                    financial_investment_net_qty=excluded.financial_investment_net_qty,
                    insurance_net_qty=excluded.insurance_net_qty,
                    investment_trust_net_qty=excluded.investment_trust_net_qty,
                    bank_net_qty=excluded.bank_net_qty,
                    other_finance_net_qty=excluded.other_finance_net_qty,
                    pension_fund_net_qty=excluded.pension_fund_net_qty,
                    private_fund_net_qty=excluded.private_fund_net_qty,
                    other_corporation_net_qty=excluded.other_corporation_net_qty,
                    program_buy_qty=excluded.program_buy_qty,
                    program_sell_qty=excluded.program_sell_qty,
                    program_net_qty=excluded.program_net_qty,
                    program_buy_amount=excluded.program_buy_amount,
                    program_sell_amount=excluded.program_sell_amount,
                    program_net_amount=excluded.program_net_amount,
                    program_arbitrage_net_qty=excluded.program_arbitrage_net_qty,
                    program_non_arbitrage_net_qty=excluded.program_non_arbitrage_net_qty,
                    source=excluded.source,
                    data_source_type=excluded.data_source_type,
                    source_method=excluded.source_method,
                    is_real_investor_flow=excluded.is_real_investor_flow,
                    collection_status=excluded.collection_status,
                    raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """
            ),
            payload,
        )

    def upsert_foreign_holding(self, row: dict[str, Any]) -> None:
        payload = dict(row)
        payload.setdefault("source", "kiwoom")
        payload.setdefault("data_source_type", "KIWOOM_REAL")
        payload.setdefault("source_method", "kiwoom_rest_ka10008")
        payload.setdefault("is_real_investor_flow", 1)
        payload.setdefault("collection_status", "PARTIAL")
        payload.setdefault("raw_json", None)
        self.db.execute(
            text(
                """
                INSERT INTO stock_investor_flows (
                    stock_id, stock_code, flow_date,
                    foreign_holding_qty, foreign_holding_ratio,
                    source, data_source_type, source_method, is_real_investor_flow,
                    collection_status, raw_json, created_at, updated_at
                ) VALUES (
                    :stock_id, :stock_code, :flow_date,
                    :foreign_holding_qty, :foreign_holding_ratio,
                    :source, :data_source_type, :source_method, :is_real_investor_flow,
                    :collection_status, :raw_json, :created_at, :updated_at
                )
                ON CONFLICT(stock_id, flow_date) DO UPDATE SET
                    stock_code=excluded.stock_code,
                    foreign_holding_qty=excluded.foreign_holding_qty,
                    foreign_holding_ratio=excluded.foreign_holding_ratio,
                    source=CASE
                        WHEN stock_investor_flows.source_method = 'kiwoom_rest_multi_investor_flow' THEN stock_investor_flows.source
                        ELSE excluded.source
                    END,
                    data_source_type=CASE
                        WHEN stock_investor_flows.source_method = 'kiwoom_rest_multi_investor_flow' THEN stock_investor_flows.data_source_type
                        ELSE excluded.data_source_type
                    END,
                    source_method=CASE
                        WHEN stock_investor_flows.source_method = 'kiwoom_rest_multi_investor_flow' THEN stock_investor_flows.source_method
                        ELSE excluded.source_method
                    END,
                    is_real_investor_flow=1,
                    collection_status=CASE
                        WHEN stock_investor_flows.source_method = 'kiwoom_rest_multi_investor_flow' THEN stock_investor_flows.collection_status
                        WHEN stock_investor_flows.collection_status = 'SUCCESS' THEN stock_investor_flows.collection_status
                        ELSE excluded.collection_status
                    END,
                    raw_json=NULL,
                    updated_at=excluded.updated_at
                """
            ),
            payload,
        )

    def list_by_stock(
        self,
        stock_id: int,
        *,
        limit: int = 90,
        start_date: str | None = None,
        end_date: str | None = None,
        data_source_type: str | None = None,
        real_only: bool = False,
        exclude_source_methods: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["stock_id = :stock_id"]
        params: dict[str, Any] = {"stock_id": stock_id, "limit": limit}
        if start_date:
            clauses.append("flow_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            clauses.append("flow_date <= :end_date")
            params["end_date"] = end_date
        if data_source_type:
            clauses.append("data_source_type = :data_source_type")
            params["data_source_type"] = data_source_type
        if real_only:
            clauses.append("is_real_investor_flow = 1")
        if exclude_source_methods:
            placeholders = []
            for index, method in enumerate(exclude_source_methods):
                key = f"exclude_source_method_{index}"
                placeholders.append(f":{key}")
                params[key] = method
            clauses.append(f"COALESCE(source_method, '') NOT IN ({', '.join(placeholders)})")
        where_sql = " AND ".join(clauses)
        rows = self.db.execute(
            text(
                f"""
                SELECT *
                FROM stock_investor_flows
                WHERE {where_sql}
                ORDER BY flow_date DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in reversed(rows)]

    def get_latest_date(self, stock_id: int, *, real_only: bool = False) -> str | None:
        where = "stock_id=:stock_id"
        if real_only:
            where += " AND is_real_investor_flow=1"
        return self.db.execute(
            text(f"SELECT MAX(flow_date) FROM stock_investor_flows WHERE {where}"),
            {"stock_id": stock_id},
        ).scalar_one_or_none()

    def commit(self) -> None:
        self.db.commit()
