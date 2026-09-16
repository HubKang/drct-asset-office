from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class DashboardReadinessService:
    """Return only the aggregate fields used by the dashboard refresh cards."""

    THEME_FLOW_COLLECTOR = "market_theme_price_flow_refresh"

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                SELECT
                  (
                    SELECT MAX(r.return_date)
                    FROM market_theme_daily_returns r
                    JOIN market_themes t ON t.id = r.theme_id
                    WHERE t.is_active = 1 AND t.theme_level = 'THEME'
                  ) AS theme_data_date,
                  (
                    SELECT MAX(r.last_refreshed_at)
                    FROM market_theme_daily_returns r
                    JOIN market_themes t ON t.id = r.theme_id
                    WHERE t.is_active = 1 AND t.theme_level = 'THEME'
                  ) AS theme_last_success_at,
                  (
                    SELECT COUNT(*)
                    FROM market_theme_stocks ts
                    JOIN market_themes t ON t.id = ts.theme_id
                    WHERE ts.is_active = 1 AND t.is_active = 1 AND t.theme_level = 'THEME'
                  ) AS theme_linked_stock_count,
                  (
                    SELECT cr.status
                    FROM collection_runs cr
                    WHERE cr.collector_name = :theme_collector
                    ORDER BY cr.id DESC
                    LIMIT 1
                  ) AS theme_run_status,
                  MAX(
                    COALESCE((
                      SELECT MAX(p.price_date)
                      FROM market_index_daily_prices p
                      JOIN market_indexes i ON i.index_code = p.index_code
                      WHERE i.is_active = 1
                    ), ''),
                    COALESCE((
                      SELECT MAX(v.value_date)
                      FROM market_indicator_values v
                      JOIN market_indicators i ON i.indicator_code = v.indicator_code
                      WHERE i.is_active = 1
                    ), '')
                  ) AS market_data_date,
                  (
                    (SELECT COUNT(*) FROM market_indexes WHERE is_active = 1)
                    + (SELECT COUNT(*) FROM market_indicators WHERE is_active = 1)
                  ) AS market_active_indicator_count,
                  COALESCE(
                    (
                      SELECT COALESCE(r.finished_at, r.started_at)
                      FROM market_data_collection_runs r
                      WHERE r.run_type = 'INCREMENTAL_ALL'
                      ORDER BY r.id DESC
                      LIMIT 1
                    ),
                    (
                      SELECT COALESCE(r.finished_at, r.started_at)
                      FROM market_data_collection_runs r
                      ORDER BY r.id DESC
                      LIMIT 1
                    )
                  ) AS market_last_run_at,
                  COALESCE(
                    (
                      SELECT r.status
                      FROM market_data_collection_runs r
                      WHERE r.run_type = 'INCREMENTAL_ALL'
                      ORDER BY r.id DESC
                      LIMIT 1
                    ),
                    (
                      SELECT r.status
                      FROM market_data_collection_runs r
                      ORDER BY r.id DESC
                      LIMIT 1
                    )
                  ) AS market_run_status
                """
            ),
            {"theme_collector": self.THEME_FLOW_COLLECTOR},
        ).mappings().one()

        market_data_date = str(row["market_data_date"] or "").strip() or None
        return {
            "theme": {
                "data_date": row["theme_data_date"],
                "last_success_at": row["theme_last_success_at"],
                "linked_stock_count": int(row["theme_linked_stock_count"] or 0),
                "run_status": row["theme_run_status"],
            },
            "market": {
                "data_date": market_data_date,
                "last_run_at": row["market_last_run_at"],
                "active_indicator_count": int(row["market_active_indicator_count"] or 0),
                "run_status": row["market_run_status"],
            },
        }
