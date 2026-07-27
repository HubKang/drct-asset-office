from __future__ import annotations

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from backend.app.entities.market_theme import MarketTheme
from backend.app.entities.market_theme_stock import MarketThemeStock
from backend.app.entities.stock import Stock


class MarketThemeStockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, row: MarketThemeStock) -> MarketThemeStock:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, mapping_id: int) -> MarketThemeStock | None:
        return self.db.get(MarketThemeStock, mapping_id)

    def get_by_theme_stock(self, theme_id: int, stock_id: int) -> MarketThemeStock | None:
        stmt = select(MarketThemeStock).where(
            MarketThemeStock.theme_id == theme_id,
            MarketThemeStock.stock_id == stock_id,
        )
        return self.db.scalar(stmt)

    def update(self, row: MarketThemeStock) -> MarketThemeStock:
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_with_stock(self, theme_id: int) -> list[tuple[MarketThemeStock, Stock]]:
        stmt: Select[tuple[MarketThemeStock, Stock]] = (
            select(MarketThemeStock, Stock)
            .join(Stock, Stock.id == MarketThemeStock.stock_id)
            .where(MarketThemeStock.theme_id == theme_id)
            .order_by(MarketThemeStock.is_active.desc(), MarketThemeStock.is_primary.desc(), Stock.stock_name.asc())
        )
        return list(self.db.execute(stmt).all())

    def list_with_supply_summary(
        self,
        theme_id: int,
        *,
        as_of_date: str,
        recent_start_date: str,
    ) -> list[dict[str, object]]:
        rows = self.db.execute(
            text(
                """
                WITH event_theme_pairs AS (
                    SELECT event_id, market_theme_id
                    FROM market_trend_event_theme_links
                    WHERE COALESCE(is_active, 1) = 1
                      AND COALESCE(deleted_at, '') = ''
                    UNION
                    SELECT id AS event_id, theme_id AS market_theme_id
                    FROM market_trend_events events
                    WHERE theme_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM market_trend_event_theme_links links
                          WHERE links.event_id = events.id
                      )
                ),
                supply_days AS (
                    SELECT DISTINCT
                        pairs.market_theme_id AS theme_id,
                        events.stock_id,
                        events.trade_date AS supply_date
                    FROM event_theme_pairs pairs
                    JOIN market_trend_events events ON events.id = pairs.event_id
                    WHERE COALESCE(events.is_active, 1) = 1
                      AND COALESCE(events.deleted_at, '') = ''
                      AND events.trade_date <= :as_of_date
                ),
                supply_summary AS (
                    SELECT
                        theme_id,
                        stock_id,
                        COUNT(*) AS supply_day_count,
                        SUM(CASE WHEN supply_date >= :recent_start_date THEN 1 ELSE 0 END) AS recent_30d_supply_day_count,
                        MIN(supply_date) AS first_supply_date,
                        MAX(supply_date) AS last_supply_date
                    FROM supply_days
                    WHERE theme_id = :theme_id
                    GROUP BY theme_id, stock_id
                )
                SELECT
                    mapping.id AS mapping_id,
                    mapping.theme_id,
                    mapping.stock_id,
                    stock.stock_code,
                    stock.stock_name,
                    stock.market,
                    mapping.mapping_source,
                    mapping.confidence_score,
                    mapping.is_primary,
                    mapping.is_active,
                    mapping.created_at,
                    mapping.updated_at,
                    COALESCE(summary.supply_day_count, 0) AS supply_day_count,
                    COALESCE(summary.recent_30d_supply_day_count, 0) AS recent_30d_supply_day_count,
                    summary.first_supply_date,
                    summary.last_supply_date
                FROM market_theme_stocks mapping
                JOIN stocks stock ON stock.id = mapping.stock_id
                LEFT JOIN supply_summary summary
                  ON summary.theme_id = mapping.theme_id
                 AND summary.stock_id = mapping.stock_id
                WHERE mapping.theme_id = :theme_id
                ORDER BY mapping.is_active DESC, mapping.is_primary DESC, stock.stock_name ASC
                """
            ),
            {
                "theme_id": theme_id,
                "as_of_date": as_of_date,
                "recent_start_date": recent_start_date,
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_supply_summary(
        self,
        theme_id: int,
        stock_id: int,
        *,
        as_of_date: str,
        recent_start_date: str,
    ) -> dict[str, object] | None:
        base = self.db.execute(
            text(
                """
                SELECT theme.id AS theme_id, theme.theme_name,
                       stock.id AS stock_id, stock.stock_code, stock.stock_name
                FROM market_themes theme
                JOIN stocks stock ON stock.id = :stock_id
                WHERE theme.id = :theme_id
                """
            ),
            {"theme_id": theme_id, "stock_id": stock_id},
        ).mappings().first()
        if not base:
            return None

        linked_themes = self.db.execute(
            text(
                """
                SELECT theme.id AS theme_id, theme.theme_name
                FROM market_theme_stocks mapping
                JOIN market_themes theme ON theme.id = mapping.theme_id
                WHERE mapping.stock_id = :stock_id
                  AND COALESCE(mapping.is_active, 1) = 1
                  AND COALESCE(theme.is_active, 1) = 1
                ORDER BY theme.theme_name ASC
                """
            ),
            {"stock_id": stock_id},
        ).mappings().all()
        date_rows = self.db.execute(
            text(
                """
                WITH event_theme_pairs AS (
                    SELECT event_id, market_theme_id
                    FROM market_trend_event_theme_links
                    WHERE COALESCE(is_active, 1) = 1
                      AND COALESCE(deleted_at, '') = ''
                    UNION
                    SELECT id AS event_id, theme_id AS market_theme_id
                    FROM market_trend_events events
                    WHERE theme_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM market_trend_event_theme_links links
                          WHERE links.event_id = events.id
                      )
                )
                SELECT DISTINCT pairs.market_theme_id AS theme_id, events.trade_date AS supply_date
                FROM event_theme_pairs pairs
                JOIN market_trend_events events ON events.id = pairs.event_id
                WHERE events.stock_id = :stock_id
                  AND COALESCE(events.is_active, 1) = 1
                  AND COALESCE(events.deleted_at, '') = ''
                  AND events.trade_date <= :as_of_date
                ORDER BY events.trade_date DESC
                """
            ),
            {"stock_id": stock_id, "as_of_date": as_of_date},
        ).mappings().all()
        overall_date_rows = self.db.execute(
            text(
                """
                SELECT DISTINCT trade_date AS supply_date
                FROM market_trend_events
                WHERE stock_id = :stock_id
                  AND COALESCE(is_active, 1) = 1
                  AND COALESCE(deleted_at, '') = ''
                  AND trade_date <= :as_of_date
                ORDER BY trade_date DESC
                """
            ),
            {"stock_id": stock_id, "as_of_date": as_of_date},
        ).mappings().all()
        memo_rows = self.db.execute(
            text(
                """
                SELECT trade_date AS detected_date,
                       TRIM(user_memo) AS memo,
                       COALESCE(detection_source, 'market_trend_event') AS source
                FROM market_trend_events
                WHERE stock_id = :stock_id
                  AND TRIM(COALESCE(user_memo, '')) <> ''
                  AND COALESCE(is_active, 1) = 1
                  AND COALESCE(deleted_at, '') = ''
                  AND trade_date <= :as_of_date
                ORDER BY trade_date DESC, updated_at DESC, id DESC
                """
            ),
            {"stock_id": stock_id, "as_of_date": as_of_date},
        ).mappings().all()

        dates_by_theme: dict[int, list[str]] = {}
        for row in date_rows:
            linked_theme_id = int(row["theme_id"])
            supply_date = str(row["supply_date"])
            dates_by_theme.setdefault(linked_theme_id, []).append(supply_date)
        current_theme_dates = dates_by_theme.get(theme_id, [])
        overall_stock_dates = [str(row["supply_date"]) for row in overall_date_rows]
        linked_theme_supply_summaries = [
            {
                "theme_id": int(row["theme_id"]),
                "theme_name": str(row["theme_name"]),
                "supply_count": len(dates_by_theme.get(int(row["theme_id"]), [])),
                "supply_dates": dates_by_theme.get(int(row["theme_id"]), []),
                "is_current_theme": int(row["theme_id"]) == theme_id,
            }
            for row in linked_themes
        ]
        linked_theme_supply_summaries.sort(
            key=lambda item: (
                not bool(item["is_current_theme"]),
                -int(item["supply_count"]),
                str(item["theme_name"]),
            )
        )
        current_theme_date_set = set(current_theme_dates)
        seen_memos: set[tuple[str, str]] = set()
        stock_memos: list[dict[str, object]] = []
        for row in memo_rows:
            detected_date = str(row["detected_date"] or "")[:10]
            memo = str(row["memo"] or "").strip()
            key = (detected_date, memo)
            if not detected_date or not memo or key in seen_memos:
                continue
            seen_memos.add(key)
            stock_memos.append(
                {
                    "detected_date": detected_date,
                    "memo": memo,
                    "source": str(row["source"] or "market_trend_event"),
                    "is_current_theme_supply_date": detected_date in current_theme_date_set,
                }
            )

        return {
            **dict(base),
            "supply_day_count": len(current_theme_dates),
            "recent_30d_supply_day_count": sum(day >= recent_start_date for day in current_theme_dates),
            "first_supply_date": current_theme_dates[-1] if current_theme_dates else None,
            "last_supply_date": current_theme_dates[0] if current_theme_dates else None,
            "all_theme_supply_day_count": len(overall_stock_dates),
            "recent_supply_dates": current_theme_dates,
            "current_theme": {
                "theme_id": theme_id,
                "theme_name": str(base["theme_name"]),
                "color": "#dc2626",
            },
            "linked_theme_supply_summaries": linked_theme_supply_summaries,
            "period_start_date": recent_start_date,
            "period_end_date": as_of_date,
            "recent_30d_theme_supply_count": sum(day >= recent_start_date for day in current_theme_dates),
            "current_theme_supply_count": len(current_theme_dates),
            "overall_stock_supply_count": len(overall_stock_dates),
            "latest_current_theme_supply_date": current_theme_dates[0] if current_theme_dates else None,
            "first_current_theme_supply_date": current_theme_dates[-1] if current_theme_dates else None,
            "current_theme_supply_dates": current_theme_dates,
            "overall_stock_supply_dates": overall_stock_dates,
            "stock_memos": stock_memos,
        }
    def list_themes_by_stock_code(self, stock_code: str) -> list[tuple[MarketThemeStock, MarketTheme, Stock]]:
        normalized = (stock_code or "").strip()
        if not normalized:
            return []
        stmt: Select[tuple[MarketThemeStock, MarketTheme, Stock]] = (
            select(MarketThemeStock, MarketTheme, Stock)
            .join(Stock, Stock.id == MarketThemeStock.stock_id)
            .join(MarketTheme, MarketTheme.id == MarketThemeStock.theme_id)
            .where(
                Stock.stock_code == normalized,
                Stock.is_active == 1,
                MarketThemeStock.is_active == 1,
                MarketTheme.is_active == 1,
            )
            .order_by(MarketThemeStock.is_primary.desc(), MarketTheme.sort_order.asc(), MarketTheme.theme_name.asc())
        )
        return list(self.db.execute(stmt).all())
