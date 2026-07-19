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
        self._training_account_table_checked = False

    def _commit_unless_atomic_order(self) -> None:
        if not self.db.info.get("trade_training_atomic_order"):
            self.db.commit()

    def ensure_training_account_table(self) -> None:
        if self._training_account_table_checked:
            return
        self.db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS trade_training_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    initial_capital REAL NOT NULL,
                    cash_balance REAL NOT NULL,
                    realized_equity REAL NOT NULL,
                    commission_rate REAL NOT NULL DEFAULT 0.001,
                    risk_per_trade_pct REAL NOT NULL DEFAULT 1.0,
                    max_open_risk_pct REAL NOT NULL DEFAULT 3.0,
                    max_position_count INTEGER NOT NULL DEFAULT 5,
                    display_days_default INTEGER NOT NULL DEFAULT 80,
                    moving_average_periods_default TEXT NOT NULL DEFAULT '[5,10,20,60,120]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
        )
        self.db.execute(text("CREATE INDEX IF NOT EXISTS idx_trade_training_accounts_status ON trade_training_accounts(status)"))
        self.db.execute(text("CREATE INDEX IF NOT EXISTS idx_trade_training_accounts_updated ON trade_training_accounts(updated_at)"))
        self.db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS trade_training_account_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    training_account_id INTEGER NOT NULL,
                    simulation_session_id INTEGER,
                    simulation_trade_id INTEGER,
                    event_type TEXT NOT NULL,
                    event_key TEXT NOT NULL,
                    cash_delta REAL NOT NULL DEFAULT 0,
                    cash_before REAL NOT NULL,
                    cash_after REAL NOT NULL,
                    realized_pnl_delta REAL NOT NULL DEFAULT 0,
                    realized_equity_after REAL,
                    description TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        self.db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_trade_training_account_ledger_event_key ON trade_training_account_ledger(event_key)"))
        self.db.execute(text("CREATE INDEX IF NOT EXISTS idx_trade_training_account_ledger_account ON trade_training_account_ledger(training_account_id)"))
        session_columns = {str(row["name"]) for row in self.db.execute(text("PRAGMA table_info(simulation_sessions)")).mappings().all()}
        if session_columns and "training_account_id" not in session_columns:
            self.db.execute(text("ALTER TABLE simulation_sessions ADD COLUMN training_account_id INTEGER"))
        self.db.execute(text("CREATE INDEX IF NOT EXISTS idx_simulation_sessions_training_account ON simulation_sessions(training_account_id)"))
        trade_columns = {str(row["name"]) for row in self.db.execute(text("PRAGMA table_info(simulation_trades)")).mappings().all()}
        if trade_columns and "client_order_id" not in trade_columns:
            self.db.execute(text("ALTER TABLE simulation_trades ADD COLUMN client_order_id TEXT"))
        self.db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_simulation_trades_client_order ON simulation_trades(session_id, client_order_id) WHERE client_order_id IS NOT NULL"))
        rows = self.db.execute(
            text(
                """
                SELECT id, options_json
                FROM simulation_sessions
                WHERE training_account_id IS NULL
                  AND options_json IS NOT NULL
                """
            )
        ).mappings().all()
        for row in rows:
            try:
                options = json.loads(str(row["options_json"] or "{}"))
            except json.JSONDecodeError:
                continue
            account_id = options.get("training_account_id")
            if account_id:
                self.db.execute(
                    text("UPDATE simulation_sessions SET training_account_id = :account_id WHERE id = :id"),
                    {"account_id": int(account_id), "id": int(row["id"])},
                )
        self.db.commit()
        self._training_account_table_checked = True

    @staticmethod
    def _decode_training_account(row: dict[str, Any]) -> dict[str, Any]:
        raw = row.get("moving_average_periods_default")
        try:
            decoded = json.loads(str(raw or "[]"))
            row["moving_average_periods_default"] = decoded if isinstance(decoded, list) else []
        except json.JSONDecodeError:
            row["moving_average_periods_default"] = []
        return row

    def list_training_accounts(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        self.ensure_training_account_table()
        params: dict[str, Any] = {}
        where = ""
        if status_filter:
            where = "WHERE status = :status"
            params["status"] = status_filter
        rows = self.db.execute(
            text(
                f"""
                SELECT *
                FROM trade_training_accounts
                {where}
                ORDER BY updated_at DESC, id DESC
                """
            ),
            params,
        ).mappings().all()
        return [self._decode_training_account(dict(row)) for row in rows]

    def create_training_account(self, values: dict[str, Any]) -> dict[str, Any]:
        self.ensure_training_account_table()
        now = now_kst()
        params = {
            **values,
            "status": "ACTIVE",
            "cash_balance": values["initial_capital"],
            "realized_equity": values["initial_capital"],
            "moving_average_periods_default": json.dumps(values.get("moving_average_periods_default") or [], ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
        }
        cursor = self.db.execute(
            text(
                """
                INSERT INTO trade_training_accounts (
                    name, description, status, initial_capital, cash_balance, realized_equity,
                    commission_rate, risk_per_trade_pct, max_open_risk_pct, max_position_count,
                    display_days_default, moving_average_periods_default, created_at, updated_at
                )
                VALUES (
                    :name, :description, :status, :initial_capital, :cash_balance, :realized_equity,
                    :commission_rate, :risk_per_trade_pct, :max_open_risk_pct, :max_position_count,
                    :display_days_default, :moving_average_periods_default, :created_at, :updated_at
                )
                """
            ),
            params,
        )
        self.db.commit()
        return self.get_training_account(int(cursor.lastrowid)) or {}

    def get_training_account(self, account_id: int) -> dict[str, Any] | None:
        self.ensure_training_account_table()
        row = self.db.execute(text("SELECT * FROM trade_training_accounts WHERE id = :id"), {"id": account_id}).mappings().first()
        return self._decode_training_account(dict(row)) if row else None

    def update_training_account(self, account_id: int, values: dict[str, Any]) -> dict[str, Any]:
        self.ensure_training_account_table()
        cleaned = {key: value for key, value in values.items() if value is not None}
        if "moving_average_periods_default" in cleaned:
            cleaned["moving_average_periods_default"] = json.dumps(cleaned["moving_average_periods_default"], ensure_ascii=False)
        cleaned["updated_at"] = now_kst()
        assignments = ", ".join(f"{key} = :{key}" for key in cleaned)
        self.db.execute(text(f"UPDATE trade_training_accounts SET {assignments} WHERE id = :id"), {**cleaned, "id": account_id})
        self._commit_unless_atomic_order()
        return self.get_training_account(account_id) or {}

    def delete_training_account(self, account_id: int) -> dict[str, int]:
        self.ensure_training_account_table()
        session_ids = [
            int(row["id"])
            for row in self.db.execute(
                text("SELECT id FROM simulation_sessions WHERE training_account_id = :account_id"),
                {"account_id": account_id},
            ).mappings().all()
        ]
        counts = {
            "session_count": len(session_ids),
            "trade_count": 0,
            "snapshot_count": 0,
            "review_count": 0,
        }
        if session_ids:
            id_params = {f"id_{idx}": session_id for idx, session_id in enumerate(session_ids)}
            id_clause = ", ".join(f":id_{idx}" for idx in range(len(session_ids)))
            counts["trade_count"] = int(
                self.db.execute(text(f"SELECT COUNT(*) FROM simulation_trades WHERE session_id IN ({id_clause})"), id_params).scalar() or 0
            )
            counts["snapshot_count"] = int(
                self.db.execute(text(f"SELECT COUNT(*) FROM simulation_snapshots WHERE session_id IN ({id_clause})"), id_params).scalar() or 0
            )
            counts["review_count"] = int(
                self.db.execute(text(f"SELECT COUNT(*) FROM simulation_reviews WHERE session_id IN ({id_clause})"), id_params).scalar() or 0
            )
            self.db.execute(text(f"DELETE FROM simulation_reviews WHERE session_id IN ({id_clause})"), id_params)
            self.db.execute(text(f"DELETE FROM simulation_snapshots WHERE session_id IN ({id_clause})"), id_params)
            self.db.execute(text(f"DELETE FROM simulation_trades WHERE session_id IN ({id_clause})"), id_params)
            self.db.execute(text(f"DELETE FROM simulation_sessions WHERE id IN ({id_clause})"), id_params)
        self.db.execute(text("DELETE FROM trade_training_account_ledger WHERE training_account_id = :account_id"), {"account_id": account_id})
        self.db.execute(text("DELETE FROM trade_training_accounts WHERE id = :account_id"), {"account_id": account_id})
        self._commit_unless_atomic_order()
        return counts

    def update_training_account_balances(self, account_id: int, cash_balance: float, realized_equity: float | None = None) -> dict[str, Any]:
        self.update_training_account_balances_no_commit(account_id, cash_balance=cash_balance, realized_equity=realized_equity)
        self._commit_unless_atomic_order()
        return self.get_training_account(account_id) or {}

    def update_training_account_balances_no_commit(self, account_id: int, cash_balance: float, realized_equity: float | None = None) -> None:
        self.ensure_training_account_table()
        values: dict[str, Any] = {"cash_balance": round(float(cash_balance), 4), "updated_at": now_kst(), "id": account_id}
        realized_sql = ""
        if realized_equity is not None:
            values["realized_equity"] = round(float(realized_equity), 4)
            realized_sql = ", realized_equity = :realized_equity"
        self.db.execute(
            text(f"UPDATE trade_training_accounts SET cash_balance = :cash_balance{realized_sql}, updated_at = :updated_at WHERE id = :id"),
            values,
        )

    def insert_account_ledger(self, values: dict[str, Any]) -> None:
        self.insert_account_ledger_no_commit(values)
        self._commit_unless_atomic_order()

    def insert_account_ledger_no_commit(self, values: dict[str, Any]) -> None:
        self.ensure_training_account_table()
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO trade_training_account_ledger (
                    training_account_id, simulation_session_id, simulation_trade_id, event_type, event_key,
                    cash_delta, cash_before, cash_after, realized_pnl_delta, realized_equity_after,
                    description, metadata_json, created_at
                )
                VALUES (
                    :training_account_id, :simulation_session_id, :simulation_trade_id, :event_type, :event_key,
                    :cash_delta, :cash_before, :cash_after, :realized_pnl_delta, :realized_equity_after,
                    :description, :metadata_json, :created_at
                )
                """
            ),
            {
                **values,
                "metadata_json": json.dumps(values.get("metadata") or {}, ensure_ascii=False),
                "created_at": now_kst(),
            },
        )

    def count_account_ledger_events(self, account_id: int) -> int:
        self.ensure_training_account_table()
        return int(
            self.db.execute(
                text("SELECT COUNT(*) FROM trade_training_account_ledger WHERE training_account_id = :account_id"),
                {"account_id": account_id},
            ).scalar()
            or 0
        )

    def list_account_trade_events(self, account_id: int) -> list[dict[str, Any]]:
        self.ensure_training_account_table()
        rows = self.db.execute(
            text(
                """
                SELECT
                    t.*,
                    s.training_account_id,
                    s.stock_code,
                    s.stock_name,
                    s.current_date,
                    s.current_index,
                    s.start_date,
                    s.end_date,
                    s.status AS session_status,
                    s.options_json AS session_options_json
                FROM simulation_trades t
                JOIN simulation_sessions s ON s.id = t.session_id
                WHERE s.training_account_id = :account_id
                ORDER BY COALESCE(t.created_at, ''), t.id
                """
            ),
            {"account_id": account_id},
        ).mappings().all()
        return [self._decode_trade(dict(row)) for row in rows]

    def replace_account_ledger_and_balances(
        self,
        account_id: int,
        ledger_events: list[dict[str, Any]],
        cash_balance: float,
        realized_equity: float,
        session_updates: list[dict[str, Any]] | None = None,
    ) -> None:
        self.ensure_training_account_table()
        self.db.execute(text("DELETE FROM trade_training_account_ledger WHERE training_account_id = :account_id"), {"account_id": account_id})
        for values in session_updates or []:
            self.db.execute(
                text(
                    """
                    UPDATE simulation_sessions
                    SET cash = :cash,
                        position_qty = :position_qty,
                        avg_price = :avg_price,
                        realized_profit = :realized_profit,
                        updated_at = :updated_at
                    WHERE id = :session_id
                    """
                ),
                {**values, "updated_at": now_kst()},
            )
        for event in ledger_events:
            self.db.execute(
                text(
                    """
                    INSERT INTO trade_training_account_ledger (
                        training_account_id, simulation_session_id, simulation_trade_id, event_type, event_key,
                        cash_delta, cash_before, cash_after, realized_pnl_delta, realized_equity_after,
                        description, metadata_json, created_at
                    )
                    VALUES (
                        :training_account_id, :simulation_session_id, :simulation_trade_id, :event_type, :event_key,
                        :cash_delta, :cash_before, :cash_after, :realized_pnl_delta, :realized_equity_after,
                        :description, :metadata_json, :created_at
                    )
                    """
                ),
                {
                    **event,
                    "metadata_json": json.dumps(event.get("metadata") or {}, ensure_ascii=False),
                    "created_at": event.get("created_at") or now_kst(),
                },
            )
        self.db.execute(
            text(
                """
                UPDATE trade_training_accounts
                SET cash_balance = :cash_balance,
                    realized_equity = :realized_equity,
                    updated_at = :updated_at
                WHERE id = :account_id
                """
            ),
            {
                "account_id": account_id,
                "cash_balance": round(float(cash_balance), 4),
                "realized_equity": round(float(realized_equity), 4),
                "updated_at": now_kst(),
            },
        )
        self.db.commit()

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
        self.ensure_training_account_table()
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
                    stock_code, stock_name, method_id, training_account_id, start_date, end_date, current_date, current_index,
                    initial_cash, cash, position_qty, avg_price, realized_profit, status,
                    options_json, created_at, updated_at
                )
                VALUES (
                    :stock_code, :stock_name, :method_id, :training_account_id, :start_date, :end_date, :current_date, :current_index,
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
        self.ensure_training_account_table()
        row = self.db.execute(
            text("SELECT * FROM simulation_sessions WHERE id = :id"),
            {"id": session_id},
        ).mappings().first()
        return dict(row) if row else None

    def list_account_sessions(self, account_id: int, status_filter: str | None = None) -> list[dict[str, Any]]:
        self.ensure_training_account_table()
        params: dict[str, Any] = {"account_id": account_id}
        where = "WHERE s.training_account_id = :account_id"
        if status_filter:
            where += " AND s.status = :status"
            params["status"] = status_filter
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    s.*,
                    COUNT(t.id) AS trade_count,
                    COALESCE(SUM(CASE WHEN t.side = 'BUY' THEN 1 ELSE 0 END), 0) AS buy_count,
                    COALESCE(SUM(CASE WHEN t.side = 'SELL' THEN 1 ELSE 0 END), 0) AS sell_count
                FROM simulation_sessions s
                LEFT JOIN simulation_trades t ON t.session_id = s.id
                {where}
                GROUP BY s.id
                ORDER BY COALESCE(s.updated_at, s.created_at) DESC, s.id DESC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

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
        self.update_session_no_commit(session_id, values)
        self._commit_unless_atomic_order()
        return self.get_session(session_id) or {}

    def update_session_no_commit(self, session_id: int, values: dict[str, Any]) -> None:
        values = {**values, "updated_at": now_kst()}
        assignments = ", ".join(f"{key} = :{key}" for key in values)
        self.db.execute(
            text(f"UPDATE simulation_sessions SET {assignments} WHERE id = :id"),
            {**values, "id": session_id},
        )

    def insert_trade(self, values: dict[str, Any]) -> dict[str, Any]:
        trade = self.insert_trade_no_commit(values)
        self._commit_unless_atomic_order()
        return trade

    def insert_trade_no_commit(self, values: dict[str, Any]) -> dict[str, Any]:
        self._ensure_trade_method_review_column()
        self.ensure_training_account_table()
        cursor = self.db.execute(
            text(
                """
                INSERT INTO simulation_trades (
                    session_id, trade_date, side, price, quantity, fee, amount,
                    realized_profit, reason, method_review_json, client_order_id, created_at
                )
                VALUES (
                    :session_id, :trade_date, :side, :price, :quantity, :fee, :amount,
                    :realized_profit, :reason, :method_review_json, :client_order_id, :created_at
                )
                """
            ),
            {
                **values,
                "method_review_json": json.dumps(values.get("method_review") or {}, ensure_ascii=False) if values.get("method_review") else None,
                "client_order_id": values.get("client_order_id"),
                "created_at": now_kst(),
            },
        )
        row = self.db.execute(
            text("SELECT * FROM simulation_trades WHERE id = :id"),
            {"id": int(cursor.lastrowid)},  # type: ignore[arg-type]
        ).mappings().one()
        return self._decode_trade(dict(row))

    def get_trade_by_client_order_id(self, session_id: int, client_order_id: str | None) -> dict[str, Any] | None:
        if not client_order_id:
            return None
        self._ensure_trade_method_review_column()
        self.ensure_training_account_table()
        row = self.db.execute(
            text(
                """
                SELECT *
                FROM simulation_trades
                WHERE session_id = :session_id
                  AND client_order_id = :client_order_id
                LIMIT 1
                """
            ),
            {"session_id": session_id, "client_order_id": client_order_id},
        ).mappings().first()
        return self._decode_trade(dict(row)) if row else None

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

    def list_calendar_sessions(self, month: str) -> list[dict[str, Any]]:
        month_start = f"{month}-01"
        rows = self.db.execute(
            text(
                """
                WITH calendar_rows AS (
                    SELECT
                        s.id,
                        s.stock_code,
                        s.stock_name,
                        s.method_id,
                        COALESCE(m.method_name, '자유훈련') AS trade_method_name,
                        s.current_date,
                        s.start_date,
                        s.end_date,
                        s.initial_cash,
                        s.cash,
                        s.realized_profit,
                        s.status,
                        s.created_at AS session_created_at,
                        s.updated_at AS session_updated_at,
                        r.id AS review_id,
                        r.review_status,
                        r.reviewed_at,
                        r.created_at AS review_created_at,
                        r.updated_at AS review_updated_at,
                        COALESCE(r.updated_at, r.created_at, r.reviewed_at, s.updated_at, s.created_at) AS activity_at
                    FROM simulation_sessions s
                    LEFT JOIN trade_methods m ON m.id = s.method_id
                    LEFT JOIN simulation_reviews r ON r.session_id = s.id
                    WHERE s.status = '완료'
                       OR r.id IS NOT NULL
                )
                SELECT
                    *,
                    date(activity_at) AS activity_date
                FROM calendar_rows
                WHERE date(activity_at) >= date(:month_start)
                  AND date(activity_at) < date(:month_start, '+1 month')
                ORDER BY activity_date ASC, id ASC
                """
            ),
            {"month_start": month_start},
        ).mappings().all()
        return [dict(row) for row in rows]
