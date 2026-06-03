from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst


class BacktestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value or {}, ensure_ascii=False)

    @staticmethod
    def _decode_rule(row: dict[str, Any]) -> dict[str, Any]:
        decoded = dict(row)
        for key in ("buy_conditions_json", "sell_conditions_json", "position_rule_json"):
            raw = decoded.get(key)
            try:
                decoded[key] = json.loads(str(raw or "{}"))
            except json.JSONDecodeError:
                decoded[key] = {}
        return decoded

    @staticmethod
    def _decode_trade(row: dict[str, Any]) -> dict[str, Any]:
        decoded = dict(row)
        for key in ("buy_signal_json", "sell_signal_json"):
            raw = decoded.get(key)
            if raw is None:
                decoded[key] = None
                continue
            try:
                decoded[key] = json.loads(str(raw or "{}"))
            except json.JSONDecodeError:
                decoded[key] = None
        return decoded

    def list_rules(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        where = "" if include_inactive else "WHERE is_active = 1"
        rows = self.db.execute(
            text(
                f"""
                SELECT *
                FROM backtest_rules
                {where}
                ORDER BY is_active DESC, updated_at DESC, id DESC
                """
            )
        ).mappings().all()
        return [self._decode_rule(dict(row)) for row in rows]

    def get_rule(self, rule_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM backtest_rules WHERE id = :id"),
            {"id": rule_id},
        ).mappings().first()
        return self._decode_rule(dict(row)) if row else None

    def create_rule(self, values: dict[str, Any]) -> dict[str, Any]:
        now = now_kst()
        cursor = self.db.execute(
            text(
                """
                INSERT INTO backtest_rules (
                    rule_name, description, trade_method_id, buy_conditions_json, sell_conditions_json,
                    position_rule_json, fee_rate, slippage_rate, is_active, created_at, updated_at
                )
                VALUES (
                    :rule_name, :description, :trade_method_id, :buy_conditions_json, :sell_conditions_json,
                    :position_rule_json, :fee_rate, :slippage_rate, 1, :created_at, :updated_at
                )
                """
            ),
            {
                "rule_name": values["rule_name"],
                "description": values.get("description"),
                "trade_method_id": values.get("trade_method_id"),
                "buy_conditions_json": self._json_dumps(values.get("buy_conditions_json")),
                "sell_conditions_json": self._json_dumps(values.get("sell_conditions_json")),
                "position_rule_json": self._json_dumps(values.get("position_rule_json")),
                "fee_rate": float(values.get("fee_rate") or 0),
                "slippage_rate": float(values.get("slippage_rate") or 0),
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        return self.get_rule(int(cursor.lastrowid)) or {}

    def update_rule(self, rule_id: int, values: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for key in ("rule_name", "description", "trade_method_id", "fee_rate", "slippage_rate", "is_active"):
            if key in values:
                updates[key] = values[key]
        for key in ("buy_conditions_json", "sell_conditions_json", "position_rule_json"):
            if key in values:
                updates[key] = self._json_dumps(values[key])
        updates["updated_at"] = now_kst()
        assignments = ", ".join(f"{key} = :{key}" for key in updates)
        self.db.execute(text(f"UPDATE backtest_rules SET {assignments} WHERE id = :id"), {**updates, "id": rule_id})
        self.db.commit()
        return self.get_rule(rule_id) or {}

    def deactivate_rule(self, rule_id: int) -> dict[str, Any]:
        return self.update_rule(rule_id, {"is_active": 0})

    def list_backtest_stocks(self, keyword: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        where = ""
        if keyword:
            where = "WHERE s.stock_code LIKE :keyword OR s.stock_name LIKE :keyword"
            params["keyword"] = f"%{keyword.strip()}%"
        rows = self.db.execute(
            text(
                f"""
                WITH source_rank AS (
                    SELECT
                        p.stock_id,
                        COALESCE(p.source, '') AS source,
                        COUNT(*) AS price_count,
                        MIN(p.trade_date) AS first_price_date,
                        MAX(p.trade_date) AS last_price_date,
                        ROW_NUMBER() OVER (
                            PARTITION BY p.stock_id
                            ORDER BY COUNT(*) DESC, MAX(p.trade_date) DESC,
                                     CASE COALESCE(p.source, '') WHEN 'kiwoom_rest' THEN 0 WHEN 'pykrx' THEN 1 ELSE 2 END
                        ) AS rn
                    FROM stock_daily_prices p
                    GROUP BY p.stock_id, COALESCE(p.source, '')
                )
                SELECT
                    s.stock_code,
                    s.stock_name,
                    s.market,
                    source_rank.first_price_date,
                    source_rank.last_price_date,
                    source_rank.price_count,
                    NULLIF(source_rank.source, '') AS source
                FROM source_rank
                JOIN stocks s ON s.id = source_rank.stock_id
                {where}
                {"AND" if where else "WHERE"} source_rank.rn = 1
                ORDER BY source_rank.last_price_date DESC, source_rank.price_count DESC, s.stock_name ASC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def table_columns(self, table_name: str) -> set[str]:
        rows = self.db.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {str(row[1]) for row in rows}

    def get_stock_by_code(self, stock_code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT id AS stock_id, stock_code, stock_name, market
                FROM stocks
                WHERE stock_code = :stock_code
                """
            ),
            {"stock_code": stock_code},
        ).mappings().first()
        return dict(row) if row else None

    def resolve_price_source(self, stock_id: int) -> str | None:
        row = self.db.execute(
            text(
                """
                SELECT COALESCE(source, '') AS source
                FROM stock_daily_prices
                WHERE stock_id = :stock_id
                GROUP BY COALESCE(source, '')
                ORDER BY COUNT(*) DESC, MAX(trade_date) DESC,
                         CASE COALESCE(source, '') WHEN 'kiwoom_rest' THEN 0 WHEN 'pykrx' THEN 1 ELSE 2 END
                LIMIT 1
                """
            ),
            {"stock_id": stock_id},
        ).mappings().first()
        return str(row["source"] or "") if row else None

    def list_prices(
        self,
        stock_id: int,
        source: str | None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["stock_id = :stock_id"]
        params: dict[str, Any] = {"stock_id": stock_id}
        if source is not None:
            clauses.append("COALESCE(source, '') = :source")
            params["source"] = source
        if start_date:
            clauses.append("trade_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            clauses.append("trade_date <= :end_date")
            params["end_date"] = end_date
        rows = self.db.execute(
            text(
                f"""
                SELECT trade_date, open_price, high_price, low_price, close_price, volume, trading_value
                FROM stock_daily_prices
                WHERE {" AND ".join(clauses)}
                ORDER BY trade_date ASC, id ASC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def create_run_with_results(
        self,
        run_values: dict[str, Any],
        summary: dict[str, Any],
        trades: list[dict[str, Any]],
        equity_curve: list[dict[str, Any]],
    ) -> int:
        now = now_kst()
        cursor = self.db.execute(
            text(
                """
                INSERT INTO backtest_runs (
                    rule_id, stock_code, stock_name, start_date, end_date, initial_cash,
                    final_asset, total_profit, total_return_rate, max_drawdown, trade_count,
                    win_count, loss_count, breakeven_count, win_rate, avg_profit_rate,
                    avg_loss_rate, profit_factor, avg_holding_days, total_fee, status, message, created_at
                )
                VALUES (
                    :rule_id, :stock_code, :stock_name, :start_date, :end_date, :initial_cash,
                    :final_asset, :total_profit, :total_return_rate, :max_drawdown, :trade_count,
                    :win_count, :loss_count, :breakeven_count, :win_rate, :avg_profit_rate,
                    :avg_loss_rate, :profit_factor, :avg_holding_days, :total_fee, :status, :message, :created_at
                )
                """
            ),
            {
                **run_values,
                **summary,
                "status": "completed",
                "created_at": now,
            },
        )
        run_id = int(cursor.lastrowid)
        for trade in trades:
            self.db.execute(
                text(
                    """
                    INSERT INTO backtest_trades (
                        run_id, buy_date, sell_date, buy_price, sell_price, quantity,
                        buy_amount, sell_amount, fee, profit, profit_rate, holding_days,
                        exit_reason, buy_signal_json, sell_signal_json, created_at
                    )
                    VALUES (
                        :run_id, :buy_date, :sell_date, :buy_price, :sell_price, :quantity,
                        :buy_amount, :sell_amount, :fee, :profit, :profit_rate, :holding_days,
                        :exit_reason, :buy_signal_json, :sell_signal_json, :created_at
                    )
                    """
                ),
                {
                    **trade,
                    "run_id": run_id,
                    "buy_signal_json": self._json_dumps(trade.get("buy_signal_json")),
                    "sell_signal_json": self._json_dumps(trade.get("sell_signal_json")),
                    "created_at": now,
                },
            )
        for point in equity_curve:
            self.db.execute(
                text(
                    """
                    INSERT INTO backtest_equity_curve (
                        run_id, trade_date, cash, position_qty, position_value,
                        total_asset, drawdown_rate, created_at
                    )
                    VALUES (
                        :run_id, :trade_date, :cash, :position_qty, :position_value,
                        :total_asset, :drawdown_rate, :created_at
                    )
                    """
                ),
                {**point, "run_id": run_id, "created_at": now},
            )
        self.db.commit()
        return run_id

    def list_runs(
        self,
        rule_id: int | None = None,
        stock_code: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: dict[str, Any] = {"limit": limit}
        if rule_id:
            clauses.append("r.rule_id = :rule_id")
            params["rule_id"] = rule_id
        if stock_code:
            clauses.append("r.stock_code = :stock_code")
            params["stock_code"] = stock_code
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT r.*, br.rule_name
                FROM backtest_runs r
                LEFT JOIN backtest_rules br ON br.id = r.rule_id
                {where}
                ORDER BY r.created_at DESC, r.id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT r.*, br.rule_name
                FROM backtest_runs r
                LEFT JOIN backtest_rules br ON br.id = r.rule_id
                WHERE r.id = :id
                """
            ),
            {"id": run_id},
        ).mappings().first()
        return dict(row) if row else None

    def list_trades(self, run_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text("SELECT * FROM backtest_trades WHERE run_id = :run_id ORDER BY buy_date ASC, id ASC"),
            {"run_id": run_id},
        ).mappings().all()
        return [self._decode_trade(dict(row)) for row in rows]

    def list_equity_curve(self, run_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text("SELECT * FROM backtest_equity_curve WHERE run_id = :run_id ORDER BY trade_date ASC, id ASC"),
            {"run_id": run_id},
        ).mappings().all()
        return [dict(row) for row in rows]
