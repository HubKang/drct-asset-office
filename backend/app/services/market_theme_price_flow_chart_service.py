from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.market_theme_stock_schema import (
    MarketThemePriceFlowChartResponse,
    MarketThemePriceFlowDataQuality,
    MarketThemePriceFlowEvent,
    MarketThemePriceFlowEventItem,
    MarketThemePriceFlowLatestDates,
    MarketThemePriceFlowSeriesItem,
    MarketThemePriceFlowSummary,
)


class MarketThemePriceFlowChartService:
    PERIOD_DAYS = {"1M": 20, "3M": 63, "6M": 126}
    UNITS = {"QUANTITY", "AMOUNT"}
    VIEWS = {"ACTUAL", "NORMALIZED"}

    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)

    @staticmethod
    def _safe_float(value: Any, digits: int = 4) -> float | None:
        if value is None:
            return None
        number = float(value)
        return round(number, digits) if math.isfinite(number) else None

    @staticmethod
    def _as_int(value: Any) -> int | None:
        return None if value is None else int(value)

    @staticmethod
    def _normalized(values: list[float | int | None]) -> list[float | None]:
        finite = [abs(float(value)) for value in values if value is not None and math.isfinite(float(value))]
        maximum = max(finite, default=0.0)
        if maximum == 0:
            return [0.0 if value is not None else None for value in values]
        return [
            round(float(value) / maximum * 100, 4)
            if value is not None and math.isfinite(float(value))
            else None
            for value in values
        ]

    @staticmethod
    def _streak(values: list[int | None]) -> int:
        if not values or values[-1] in (None, 0):
            return 0
        latest_sign = 1 if int(values[-1]) > 0 else -1
        count = 0
        for value in reversed(values):
            if value is None or value == 0:
                break
            sign = 1 if value > 0 else -1
            if sign != latest_sign:
                break
            count += 1
        return count * latest_sign

    def _latest_dates(self, stock_id: int) -> MarketThemePriceFlowLatestDates:
        row = self.db.execute(
            text(
                """
                SELECT
                    (SELECT MAX(trade_date) FROM stock_daily_prices WHERE stock_id=:stock_id) AS price_latest,
                    (SELECT MAX(flow_date) FROM stock_investor_flows
                     WHERE stock_id=:stock_id AND (
                        individual_net_qty IS NOT NULL OR individual_net_amount IS NOT NULL OR
                        foreign_net_qty IS NOT NULL OR foreign_net_amount IS NOT NULL OR
                        institution_net_qty IS NOT NULL OR institution_net_amount IS NOT NULL
                     )) AS investor_latest,
                    (SELECT MAX(flow_date) FROM stock_investor_flows
                     WHERE stock_id=:stock_id AND (
                        program_net_qty IS NOT NULL OR program_net_amount IS NOT NULL
                     )) AS program_latest
                """
            ),
            {"stock_id": stock_id},
        ).mappings().one()
        values = [row["price_latest"], row["investor_latest"], row["program_latest"]]
        common = min((str(value) for value in values), default=None) if all(values) else None
        return MarketThemePriceFlowLatestDates(
            price=str(row["price_latest"]) if row["price_latest"] else None,
            investor=str(row["investor_latest"]) if row["investor_latest"] else None,
            program=str(row["program_latest"]) if row["program_latest"] else None,
            common=common,
        )

    def _event_rows(
        self, stock_id: int, start_date: str, end_date: str, theme_id: int | None
    ) -> list[MarketThemePriceFlowEvent]:
        rows = self.db.execute(
            text(
                """
                WITH event_theme_pairs AS (
                    SELECT event_id, market_theme_id
                    FROM market_trend_event_theme_links
                    WHERE COALESCE(is_active, 1)=1 AND COALESCE(deleted_at, '')=''
                    UNION
                    SELECT events.id, events.theme_id
                    FROM market_trend_events events
                    WHERE events.theme_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM market_trend_event_theme_links links WHERE links.event_id=events.id
                      )
                )
                SELECT events.id AS event_id, events.trade_date AS event_date,
                       pairs.market_theme_id AS theme_id, themes.theme_name,
                       NULLIF(TRIM(events.user_memo), '') AS memo
                FROM market_trend_events events
                LEFT JOIN event_theme_pairs pairs ON pairs.event_id=events.id
                LEFT JOIN market_themes themes ON themes.id=pairs.market_theme_id
                WHERE events.stock_id=:stock_id
                  AND events.trade_date BETWEEN :start_date AND :end_date
                  AND COALESCE(events.is_active, 1)=1
                  AND COALESCE(events.deleted_at, '')=''
                ORDER BY events.trade_date ASC, events.id ASC, pairs.market_theme_id ASC
                """
            ),
            {"stock_id": stock_id, "start_date": start_date, "end_date": end_date},
        ).mappings().all()
        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"event_ids": set(), "items": [], "seen": set()})
        for row in rows:
            event_date = str(row["event_date"])
            group = grouped[event_date]
            group["event_ids"].add(int(row["event_id"]))
            item_key = (row["event_id"], row["theme_id"], row["memo"])
            if item_key in group["seen"]:
                continue
            group["seen"].add(item_key)
            linked_theme_id = int(row["theme_id"]) if row["theme_id"] is not None else None
            group["items"].append(MarketThemePriceFlowEventItem(
                theme_id=linked_theme_id,
                theme_name=str(row["theme_name"]) if row["theme_name"] else None,
                memo=str(row["memo"]) if row["memo"] else None,
                is_current_theme=theme_id is not None and linked_theme_id == theme_id,
            ))
        return [
            MarketThemePriceFlowEvent(
                event_date=event_date,
                event_count=len(group["event_ids"]),
                is_current_theme=any(item.is_current_theme for item in group["items"]),
                items=group["items"],
            )
            for event_date, group in sorted(grouped.items())
        ]

    def get_chart(
        self,
        stock_id: int,
        *,
        period: str,
        unit: str,
        view: str,
        theme_id: int | None = None,
    ) -> MarketThemePriceFlowChartResponse:
        period_code = period.upper()
        unit_code = unit.upper()
        view_code = view.upper()
        if period_code not in self.PERIOD_DAYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="period must be 1M, 3M, or 6M")
        if unit_code not in self.UNITS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unit must be QUANTITY or AMOUNT")
        if view_code not in self.VIEWS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="view must be ACTUAL or NORMALIZED")
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        requested_days = self.PERIOD_DAYS[period_code]
        latest_dates = self._latest_dates(stock_id)
        price_rows: list[dict[str, Any]] = []
        if latest_dates.common:
            rows_desc = self.db.execute(
                text(
                    """
                    SELECT trade_date, close_price, change_rate
                    FROM stock_daily_prices
                    WHERE stock_id=:stock_id AND trade_date<=:end_date
                    ORDER BY trade_date DESC
                    LIMIT :limit
                    """
                ),
                {"stock_id": stock_id, "end_date": latest_dates.common, "limit": requested_days},
            ).mappings().all()
            price_rows = [dict(row) for row in reversed(rows_desc)]

        start_date = str(price_rows[0]["trade_date"]) if price_rows else None
        end_date = str(price_rows[-1]["trade_date"]) if price_rows else latest_dates.common
        flow_map: dict[str, dict[str, Any]] = {}
        if start_date and end_date:
            flow_rows = self.db.execute(
                text(
                    """
                    SELECT flow_date,
                           individual_net_qty, individual_net_amount,
                           foreign_net_qty, foreign_net_amount,
                           institution_net_qty, institution_net_amount,
                           program_net_qty, program_net_amount
                    FROM stock_investor_flows
                    WHERE stock_id=:stock_id AND flow_date BETWEEN :start_date AND :end_date
                    ORDER BY flow_date ASC
                    """
                ),
                {"stock_id": stock_id, "start_date": start_date, "end_date": end_date},
            ).mappings().all()
            flow_map = {str(row["flow_date"]): dict(row) for row in flow_rows}

        suffix = "qty" if unit_code == "QUANTITY" else "amount"
        cumulative = {name: 0 for name in ("individual", "foreign", "institution", "program")}
        has_value = {name: False for name in cumulative}
        daily_values: dict[str, list[int | None]] = {name: [] for name in cumulative}
        series_payload: list[dict[str, Any]] = []
        first_close = next((float(row["close_price"]) for row in price_rows if row["close_price"] not in (None, 0)), None)
        missing_price = missing_investor = missing_program = valid_days = 0
        for price_row in price_rows:
            trade_date = str(price_row["trade_date"])
            close = self._safe_float(price_row["close_price"], 2)
            flow = flow_map.get(trade_date, {})
            day: dict[str, int | None] = {
                name: self._as_int(flow.get(f"{name}_net_{suffix}")) for name in cumulative
            }
            cumulatives: dict[str, int | None] = {}
            for name, value in day.items():
                daily_values[name].append(value)
                if value is None:
                    cumulatives[name] = None
                else:
                    cumulative[name] += value
                    has_value[name] = True
                    cumulatives[name] = cumulative[name]
            price_return = (
                self._safe_float((float(close) / first_close - 1) * 100, 4)
                if close is not None and first_close not in (None, 0)
                else None
            )
            investor_missing = any(day[name] is None for name in ("individual", "foreign", "institution"))
            program_missing = day["program"] is None
            missing_price += int(close is None)
            missing_investor += int(investor_missing)
            missing_program += int(program_missing)
            valid_days += int(close is not None and not investor_missing and not program_missing)
            series_payload.append({
                "trade_date": trade_date,
                "close_price": close,
                "daily_return_pct": self._safe_float(price_row["change_rate"], 4),
                "price_return_pct": price_return,
                **{f"{name}_daily": day[name] for name in cumulative},
                **{f"{name}_cumulative": cumulatives[name] for name in cumulative},
            })

        normalization_fields = {
            "price": "price_return_pct",
            "individual": "individual_cumulative",
            "foreign": "foreign_cumulative",
            "institution": "institution_cumulative",
            "program": "program_cumulative",
        }
        for name, field_name in normalization_fields.items():
            normalized = self._normalized([row.get(field_name) for row in series_payload])
            for index, value in enumerate(normalized):
                series_payload[index][f"normalized_{name}"] = value

        actual_days = len(price_rows)
        latest_values = [latest_dates.price, latest_dates.investor, latest_dates.program]
        if not series_payload or not any(has_value.values()):
            quality_status = "EMPTY"
        elif len(set(value for value in latest_values if value)) > 1:
            quality_status = "LATEST_MISMATCH"
        elif missing_price or missing_investor or missing_program:
            quality_status = "PARTIAL"
        elif actual_days < requested_days:
            quality_status = "PERIOD_SHORT"
        else:
            quality_status = "ENOUGH"
        data_quality = MarketThemePriceFlowDataQuality(
            status=quality_status,
            valid_days=valid_days,
            missing_price_days=missing_price,
            missing_investor_days=missing_investor,
            missing_program_days=missing_program,
            completeness_ratio=round(valid_days / actual_days, 4) if actual_days else 0.0,
        )
        summary = MarketThemePriceFlowSummary(
            price_return_pct=series_payload[-1].get("price_return_pct") if series_payload else None,
            **{f"{name}_cumulative": cumulative[name] if has_value[name] else None for name in cumulative},
            **{f"{name}_positive_days": sum(1 for value in daily_values[name] if value is not None and value > 0) for name in cumulative},
            **{f"{name}_streak": self._streak(daily_values[name]) for name in cumulative},
        )
        events = self._event_rows(stock_id, start_date, end_date, theme_id) if start_date and end_date else []
        return MarketThemePriceFlowChartResponse(
            stock={
                "stock_id": stock.id, "stock_code": stock.stock_code,
                "stock_name": stock.stock_name, "market": stock.market,
            },
            requested_unit=unit_code,
            requested_view=view_code,
            period={
                "code": period_code, "requested_trading_days": requested_days,
                "actual_trading_days": actual_days, "start_date": start_date, "end_date": end_date,
            },
            latest_dates=latest_dates,
            data_quality=data_quality,
            summary=summary,
            series=[MarketThemePriceFlowSeriesItem(**row) for row in series_payload],
            events=events,
        )
