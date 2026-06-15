from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst


class TradeTrainingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._simulation_trade_review_column_checked = False

    def _ensure_trade_method_review_column(self) -> None:
        if self._simulation_trade_review_column_checked:
            return
        rows = self.db.execute(text("PRAGMA table_info(simulation_trades)")).mappings().all()
        column_names = {str(row["name"]) for row in rows}
        if rows and "method_review_json" not in column_names:
            self.db.execute(text("ALTER TABLE simulation_trades ADD COLUMN method_review_json TEXT"))
            self.db.commit()
        self._simulation_trade_review_column_checked = True

    @staticmethod
    def _decode_trade(row: dict[str, Any]) -> dict[str, Any]:
        raw = row.get("method_review_json")
        if raw:
            try:
                data = json.loads(str(raw))
                row["method_review"] = data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                row["method_review"] = None
        else:
            row["method_review"] = None
        row.pop("method_review_json", None)
        return row

    def list_training_stocks(self, q: str | None, limit: int) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        where = ""
        if q:
            where = "WHERE s.stock_code LIKE :q OR s.stock_name LIKE :q"
            params["q"] = f"%{q.strip()}%"
        rows = self.db.execute(
            text(
                f"""
                WITH source_rank AS (
                    SELECT
                        p.stock_id,
                        COALESCE(p.source, '') AS source,
                        COUNT(*) AS price_count,
                        MIN(p.trade_date) AS first_date,
                        MAX(p.trade_date) AS last_date,
                        ROW_NUMBER() OVER (
                            PARTITION BY p.stock_id
                            ORDER BY COUNT(*) DESC, MAX(p.trade_date) DESC,
                                     CASE COALESCE(p.source, '') WHEN 'kiwoom_rest' THEN 0 WHEN 'pykrx' THEN 1 ELSE 2 END
                        ) AS rn
                    FROM stock_daily_prices p
                    GROUP BY p.stock_id, COALESCE(p.source, '')
                )
                SELECT
                    s.id AS stock_id,
                    s.stock_code,
                    s.stock_name,
                    s.market,
                    source_rank.price_count,
                    source_rank.first_date,
                    source_rank.last_date,
                    NULLIF(source_rank.source, '') AS source
                FROM source_rank
                JOIN stocks s ON s.id = source_rank.stock_id
                {where}
                AND source_rank.rn = 1
                ORDER BY source_rank.last_date DESC, source_rank.price_count DESC, s.stock_name ASC
                LIMIT :limit
                """
                if where
                else """
                WITH source_rank AS (
                    SELECT
                        p.stock_id,
                        COALESCE(p.source, '') AS source,
                        COUNT(*) AS price_count,
                        MIN(p.trade_date) AS first_date,
                        MAX(p.trade_date) AS last_date,
                        ROW_NUMBER() OVER (
                            PARTITION BY p.stock_id
                            ORDER BY COUNT(*) DESC, MAX(p.trade_date) DESC,
                                     CASE COALESCE(p.source, '') WHEN 'kiwoom_rest' THEN 0 WHEN 'pykrx' THEN 1 ELSE 2 END
                        ) AS rn
                    FROM stock_daily_prices p
                    GROUP BY p.stock_id, COALESCE(p.source, '')
                )
                SELECT
                    s.id AS stock_id,
                    s.stock_code,
                    s.stock_name,
                    s.market,
                    source_rank.price_count,
                    source_rank.first_date,
                    source_rank.last_date,
                    NULLIF(source_rank.source, '') AS source
                FROM source_rank
                JOIN stocks s ON s.id = source_rank.stock_id
                WHERE source_rank.rn = 1
                ORDER BY source_rank.last_date DESC, source_rank.price_count DESC, s.stock_name ASC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

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
        if not row:
            return None
        return str(row["source"] or "")

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
                SELECT
                    trade_date,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    trading_value
                FROM stock_daily_prices
                WHERE {" AND ".join(clauses)}
                ORDER BY trade_date ASC, id ASC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = now_kst()
        params = {
            **payload,
            "method_id": payload.get("method_id"),
            "options_json": json.dumps(payload.get("options") or {}, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
        }
        cursor = self.db.execute(
            text(
                """
                INSERT INTO simulation_sessions (
                    stock_code, stock_name, method_id, start_date, end_date, current_date, current_index,
                    initial_cash, cash, position_qty, avg_price, realized_profit, status,
                    options_json, created_at, updated_at
                )
                VALUES (
                    :stock_code, :stock_name, :method_id, :start_date, :end_date, :current_date, :current_index,
                    :initial_cash, :cash, :position_qty, :avg_price, :realized_profit, :status,
                    :options_json, :created_at, :updated_at
                )
                """
            ),
            params,
        )
        self.db.commit()
        return self.get_session(int(cursor.lastrowid))  # type: ignore[arg-type]

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM simulation_sessions WHERE id = :id"),
            {"id": session_id},
        ).mappings().first()
        return dict(row) if row else None

    def get_trade_method(self, method_id: int | None) -> dict[str, Any] | None:
        if not method_id:
            return None
        row = self.db.execute(
            text(
                """
                SELECT
                    id,
                    method_name,
                    core_concept,
                    description,
                    buy_condition,
                    sell_condition,
                    position_sizing_rule,
                    entry_rule,
                    exit_rule,
                    stop_loss_rule,
                    take_profit_rule,
                    checklist,
                    is_active,
                    sort_order,
                    created_at,
                    updated_at
                FROM trade_methods
                WHERE id = :id
                """
            ),
            {"id": method_id},
        ).mappings().first()
        return dict(row) if row else None

    def update_session(self, session_id: int, values: dict[str, Any]) -> dict[str, Any]:
        values = {**values, "updated_at": now_kst()}
        assignments = ", ".join(f"{key} = :{key}" for key in values)
        self.db.execute(
            text(f"UPDATE simulation_sessions SET {assignments} WHERE id = :id"),
            {**values, "id": session_id},
        )
        self.db.commit()
        return self.get_session(session_id) or {}

    def insert_trade(self, values: dict[str, Any]) -> dict[str, Any]:
        self._ensure_trade_method_review_column()
        cursor = self.db.execute(
            text(
                """
                INSERT INTO simulation_trades (
                    session_id, trade_date, side, price, quantity, fee, amount,
                    realized_profit, reason, method_review_json, created_at
                )
                VALUES (
                    :session_id, :trade_date, :side, :price, :quantity, :fee, :amount,
                    :realized_profit, :reason, :method_review_json, :created_at
                )
                """
            ),
            {
                **values,
                "method_review_json": json.dumps(values.get("method_review") or {}, ensure_ascii=False) if values.get("method_review") else None,
                "created_at": now_kst(),
            },
        )
        self.db.commit()
        row = self.db.execute(
            text("SELECT * FROM simulation_trades WHERE id = :id"),
            {"id": int(cursor.lastrowid)},  # type: ignore[arg-type]
        ).mappings().one()
        return self._decode_trade(dict(row))

    def list_trades(self, session_id: int) -> list[dict[str, Any]]:
        self._ensure_trade_method_review_column()
        rows = self.db.execute(
            text(
                """
                SELECT *
                FROM simulation_trades
                WHERE session_id = :session_id
                ORDER BY trade_date ASC, id ASC
                """
            ),
            {"session_id": session_id},
        ).mappings().all()
        return [self._decode_trade(dict(row)) for row in rows]

    def list_snapshots(self, session_id: int, end_date: str | None = None) -> list[dict[str, Any]]:
        clauses = ["session_id = :session_id"]
        params: dict[str, Any] = {"session_id": session_id}
        if end_date:
            clauses.append("trade_date <= :end_date")
            params["end_date"] = end_date
        rows = self.db.execute(
            text(
                f"""
                SELECT trade_date, cash, evaluation_amount, total_asset, unrealized_profit, created_at
                FROM simulation_snapshots
                WHERE {" AND ".join(clauses)}
                ORDER BY trade_date ASC, id ASC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def insert_snapshot(self, values: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO simulation_snapshots (
                    session_id, trade_date, cash, position_qty, avg_price,
                    evaluation_amount, total_asset, unrealized_profit, created_at
                )
                VALUES (
                    :session_id, :trade_date, :cash, :position_qty, :avg_price,
                    :evaluation_amount, :total_asset, :unrealized_profit, :created_at
                )
                """
            ),
            {**values, "created_at": now_kst()},
        )
        self.db.commit()

    def get_review(self, session_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT *
                FROM simulation_reviews
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        ).mappings().first()
        return dict(row) if row else None

    def upsert_review(self, session_id: int, values: dict[str, Any]) -> dict[str, Any]:
        now = now_kst()
        existing = self.get_review(session_id)
        params = {
            "session_id": session_id,
            "review_status": values.get("review_status") or "미복기",
            "self_review_text": values.get("self_review_text") or "",
            "gpt_prompt_text": values.get("gpt_prompt_text") or "",
            "gpt_review_text": values.get("gpt_review_text") or "",
            "improvement_point": values.get("improvement_point") or "",
            "next_training_goal": values.get("next_training_goal") or "",
            "main_mistake": values.get("main_mistake") or "",
            "discipline_score": values.get("discipline_score"),
            "reviewed_at": now if values.get("review_status") == "복기완료" else values.get("reviewed_at"),
            "updated_at": now,
        }
        if existing:
            if params["reviewed_at"] is None and existing.get("reviewed_at"):
                params["reviewed_at"] = existing.get("reviewed_at")
            self.db.execute(
                text(
                    """
                    UPDATE simulation_reviews
                    SET review_status = :review_status,
                        self_review_text = :self_review_text,
                        gpt_prompt_text = :gpt_prompt_text,
                        gpt_review_text = :gpt_review_text,
                        improvement_point = :improvement_point,
                        next_training_goal = :next_training_goal,
                        main_mistake = :main_mistake,
                        discipline_score = :discipline_score,
                        reviewed_at = :reviewed_at,
                        updated_at = :updated_at
                    WHERE session_id = :session_id
                    """
                ),
                params,
            )
        else:
            self.db.execute(
                text(
                    """
                    INSERT INTO simulation_reviews (
                        session_id, review_status, self_review_text, gpt_prompt_text,
                        gpt_review_text, improvement_point, next_training_goal,
                        main_mistake, discipline_score, reviewed_at, created_at, updated_at
                    )
                    VALUES (
                        :session_id, :review_status, :self_review_text, :gpt_prompt_text,
                        :gpt_review_text, :improvement_point, :next_training_goal,
                        :main_mistake, :discipline_score, :reviewed_at, :updated_at, :updated_at
                    )
                    """
                ),
                params,
            )
        self.db.commit()
        return self.get_review(session_id) or {}
