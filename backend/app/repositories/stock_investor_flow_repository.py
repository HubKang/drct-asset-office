from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class StockInvestorFlowRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_flow(self, row: dict[str, Any]) -> None:
        payload = dict(row)
        for column_name in (
            "individual_buy_qty", "individual_sell_qty", "individual_net_qty",
            "individual_buy_amount", "individual_sell_amount", "individual_net_amount",
        ):
            payload.setdefault(column_name, None)
        payload.setdefault("data_source_type", "DERIVED_PRICE_FLOW" if payload.get("source") == "derived_price_flow" else "KIWOOM_REAL")
        payload.setdefault("source_method", payload.get("source") or "derived_price_flow")
        payload.setdefault("is_real_investor_flow", 1 if payload.get("data_source_type") == "KIWOOM_REAL" else 0)
        payload["is_real_investor_flow"] = 1 if payload.get("is_real_investor_flow") is True else int(payload.get("is_real_investor_flow") or 0)
        # Durable storage is an explicit column allow-list; raw provider payloads stay transient.
        payload["raw_json"] = None
        self.db.execute(
            text(
                """
                INSERT INTO stock_investor_flows (
                    stock_id, stock_code, flow_date,
                    individual_buy_qty, individual_sell_qty, individual_net_qty,
                    individual_buy_amount, individual_sell_amount, individual_net_amount,
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
                    :individual_buy_qty, :individual_sell_qty, :individual_net_qty,
                    :individual_buy_amount, :individual_sell_amount, :individual_net_amount,
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
                    individual_buy_qty=COALESCE(excluded.individual_buy_qty, stock_investor_flows.individual_buy_qty),
                    individual_sell_qty=COALESCE(excluded.individual_sell_qty, stock_investor_flows.individual_sell_qty),
                    individual_net_qty=COALESCE(excluded.individual_net_qty, stock_investor_flows.individual_net_qty),
                    individual_buy_amount=COALESCE(excluded.individual_buy_amount, stock_investor_flows.individual_buy_amount),
                    individual_sell_amount=COALESCE(excluded.individual_sell_amount, stock_investor_flows.individual_sell_amount),
                    individual_net_amount=COALESCE(excluded.individual_net_amount, stock_investor_flows.individual_net_amount),
                    foreign_buy_qty=COALESCE(excluded.foreign_buy_qty, stock_investor_flows.foreign_buy_qty),
                    foreign_sell_qty=COALESCE(excluded.foreign_sell_qty, stock_investor_flows.foreign_sell_qty),
                    foreign_net_qty=COALESCE(excluded.foreign_net_qty, stock_investor_flows.foreign_net_qty),
                    foreign_buy_amount=COALESCE(excluded.foreign_buy_amount, stock_investor_flows.foreign_buy_amount),
                    foreign_sell_amount=COALESCE(excluded.foreign_sell_amount, stock_investor_flows.foreign_sell_amount),
                    foreign_net_amount=COALESCE(excluded.foreign_net_amount, stock_investor_flows.foreign_net_amount),
                    foreign_holding_qty=COALESCE(excluded.foreign_holding_qty, stock_investor_flows.foreign_holding_qty),
                    foreign_holding_ratio=COALESCE(excluded.foreign_holding_ratio, stock_investor_flows.foreign_holding_ratio),
                    institution_buy_qty=COALESCE(excluded.institution_buy_qty, stock_investor_flows.institution_buy_qty),
                    institution_sell_qty=COALESCE(excluded.institution_sell_qty, stock_investor_flows.institution_sell_qty),
                    institution_net_qty=COALESCE(excluded.institution_net_qty, stock_investor_flows.institution_net_qty),
                    institution_buy_amount=COALESCE(excluded.institution_buy_amount, stock_investor_flows.institution_buy_amount),
                    institution_sell_amount=COALESCE(excluded.institution_sell_amount, stock_investor_flows.institution_sell_amount),
                    institution_net_amount=COALESCE(excluded.institution_net_amount, stock_investor_flows.institution_net_amount),
                    financial_investment_net_qty=COALESCE(excluded.financial_investment_net_qty, stock_investor_flows.financial_investment_net_qty),
                    insurance_net_qty=COALESCE(excluded.insurance_net_qty, stock_investor_flows.insurance_net_qty),
                    investment_trust_net_qty=COALESCE(excluded.investment_trust_net_qty, stock_investor_flows.investment_trust_net_qty),
                    bank_net_qty=COALESCE(excluded.bank_net_qty, stock_investor_flows.bank_net_qty),
                    other_finance_net_qty=COALESCE(excluded.other_finance_net_qty, stock_investor_flows.other_finance_net_qty),
                    pension_fund_net_qty=COALESCE(excluded.pension_fund_net_qty, stock_investor_flows.pension_fund_net_qty),
                    private_fund_net_qty=COALESCE(excluded.private_fund_net_qty, stock_investor_flows.private_fund_net_qty),
                    other_corporation_net_qty=COALESCE(excluded.other_corporation_net_qty, stock_investor_flows.other_corporation_net_qty),
                    program_buy_qty=COALESCE(excluded.program_buy_qty, stock_investor_flows.program_buy_qty),
                    program_sell_qty=COALESCE(excluded.program_sell_qty, stock_investor_flows.program_sell_qty),
                    program_net_qty=COALESCE(excluded.program_net_qty, stock_investor_flows.program_net_qty),
                    program_buy_amount=COALESCE(excluded.program_buy_amount, stock_investor_flows.program_buy_amount),
                    program_sell_amount=COALESCE(excluded.program_sell_amount, stock_investor_flows.program_sell_amount),
                    program_net_amount=COALESCE(excluded.program_net_amount, stock_investor_flows.program_net_amount),
                    program_arbitrage_net_qty=COALESCE(excluded.program_arbitrage_net_qty, stock_investor_flows.program_arbitrage_net_qty),
                    program_non_arbitrage_net_qty=COALESCE(excluded.program_non_arbitrage_net_qty, stock_investor_flows.program_non_arbitrage_net_qty),
                    source=excluded.source,
                    data_source_type=excluded.data_source_type,
                    source_method=excluded.source_method,
                    is_real_investor_flow=excluded.is_real_investor_flow,
                    collection_status=excluded.collection_status,
                    raw_json=NULL,
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

    def get_latest_subject_dates(self, stock_ids: list[int]) -> dict[int, dict[str, str | None]]:
        if not stock_ids:
            return {}
        params = {f"stock_id_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        placeholders = ", ".join(f":stock_id_{index}" for index in range(len(stock_ids)))
        rows = self.db.execute(
            text(
                f"""
                SELECT stock_id,
                       MAX(CASE WHEN is_real_investor_flow=1 AND (
                           individual_net_qty IS NOT NULL OR individual_net_amount IS NOT NULL OR
                           foreign_net_qty IS NOT NULL OR foreign_net_amount IS NOT NULL OR
                           institution_net_qty IS NOT NULL OR institution_net_amount IS NOT NULL
                       ) THEN flow_date END) AS investor_latest_date,
                       MAX(CASE WHEN is_real_investor_flow=1 AND (
                           program_net_qty IS NOT NULL OR program_net_amount IS NOT NULL
                       ) THEN flow_date END) AS program_latest_date
                FROM stock_investor_flows
                WHERE stock_id IN ({placeholders})
                GROUP BY stock_id
                """
            ),
            params,
        ).mappings().all()
        return {
            int(row["stock_id"]): {
                "investor_latest_date": row["investor_latest_date"],
                "program_latest_date": row["program_latest_date"],
            }
            for row in rows
        }

    def get_dates_in_window(self, stock_id: int, start_date: str, end_date: str) -> set[str]:
        rows = self.db.execute(
            text(
                """
                SELECT flow_date
                FROM stock_investor_flows
                WHERE stock_id=:stock_id AND flow_date BETWEEN :start_date AND :end_date
                """
            ),
            {"stock_id": stock_id, "start_date": start_date, "end_date": end_date},
        ).scalars().all()
        return {str(value) for value in rows}

    def commit(self) -> None:
        self.db.commit()
