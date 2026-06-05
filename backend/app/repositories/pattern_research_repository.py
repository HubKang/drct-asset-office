from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst


class PatternResearchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=False)

    @staticmethod
    def _json_loads(raw: Any, fallback: Any) -> Any:
        try:
            return json.loads(str(raw or ""))
        except (TypeError, json.JSONDecodeError):
            return fallback

    def list_stocks(self, keyword: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
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
                    s.id AS stock_id,
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

    def get_stock_by_code(self, stock_code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT id AS stock_id, stock_code, stock_name, market FROM stocks WHERE stock_code = :stock_code"),
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

    def list_prices(self, stock_id: int, source: str | None, end_date: str | None = None) -> list[dict[str, Any]]:
        clauses = ["stock_id = :stock_id"]
        params: dict[str, Any] = {"stock_id": stock_id}
        if source is not None:
            clauses.append("COALESCE(source, '') = :source")
            params["source"] = source
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

    def create_run_with_samples(
        self,
        run_values: dict[str, Any],
        parsed_goal: dict[str, Any],
        summary: dict[str, Any],
        gpt_prompt_text: str,
        samples: list[dict[str, Any]],
    ) -> int:
        now = now_kst()
        cursor = self.db.execute(
            text(
                """
                INSERT INTO pattern_research_runs (
                    research_name, stock_codes_json, start_date, end_date, goal_text, parsed_goal_json,
                    target_return_pct, target_days, stop_loss_pct, max_holding_days,
                    summary_json, gpt_prompt_text, status, created_at, updated_at
                )
                VALUES (
                    :research_name, :stock_codes_json, :start_date, :end_date, :goal_text, :parsed_goal_json,
                    :target_return_pct, :target_days, :stop_loss_pct, :max_holding_days,
                    :summary_json, :gpt_prompt_text, 'completed', :created_at, :updated_at
                )
                """
            ),
            {
                **run_values,
                "stock_codes_json": self._json_dumps(run_values.get("stock_codes")),
                "parsed_goal_json": self._json_dumps(parsed_goal),
                "summary_json": self._json_dumps(summary),
                "gpt_prompt_text": gpt_prompt_text,
                "created_at": now,
                "updated_at": now,
            },
        )
        run_id = int(cursor.lastrowid)
        for sample in samples:
            self.db.execute(
                text(
                    """
                    INSERT INTO pattern_research_samples (
                        run_id, stock_code, stock_name, trade_date, entry_price,
                        max_future_return_pct, min_future_return_pct, future_return_pct,
                        target_hit, stop_hit, result_label, features_json, pattern_tags_json, created_at
                    )
                    VALUES (
                        :run_id, :stock_code, :stock_name, :trade_date, :entry_price,
                        :max_future_return_pct, :min_future_return_pct, :future_return_pct,
                        :target_hit, :stop_hit, :result_label, :features_json, :pattern_tags_json, :created_at
                    )
                    """
                ),
                {
                    **sample,
                    "run_id": run_id,
                    "features_json": self._json_dumps(sample.get("features")),
                    "pattern_tags_json": self._json_dumps(sample.get("pattern_tags")),
                    "created_at": now,
                },
            )
        self.db.commit()
        return run_id

    def _decode_run(self, row: dict[str, Any]) -> dict[str, Any]:
        decoded = dict(row)
        decoded["stock_codes"] = self._json_loads(decoded.pop("stock_codes_json", "[]"), [])
        decoded["parsed_goal"] = self._json_loads(decoded.pop("parsed_goal_json", "{}"), {})
        decoded["summary"] = self._json_loads(decoded.pop("summary_json", "{}"), {})
        return decoded

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM pattern_research_runs WHERE id = :id"), {"id": run_id}).mappings().first()
        return self._decode_run(dict(row)) if row else None

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text("SELECT * FROM pattern_research_runs ORDER BY created_at DESC, id DESC LIMIT :limit"),
            {"limit": limit},
        ).mappings().all()
        return [self._decode_run(dict(row)) for row in rows]

    def list_samples(self, run_id: int, label: str | None = None, limit: int = 300) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"run_id": run_id, "limit": limit}
        where = "run_id = :run_id"
        if label:
            where += " AND result_label = :label"
            params["label"] = label
        rows = self.db.execute(
            text(f"SELECT * FROM pattern_research_samples WHERE {where} ORDER BY trade_date ASC, id ASC LIMIT :limit"),
            params,
        ).mappings().all()
        result = []
        for row in rows:
            decoded = dict(row)
            decoded["features"] = self._json_loads(decoded.pop("features_json", "{}"), {})
            decoded["pattern_tags"] = self._json_loads(decoded.pop("pattern_tags_json", "[]"), [])
            result.append(decoded)
        return result
