from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.schemas.external_kiwoom_schema import (
    MarketThemeReturnStockItem,
    MonthlyThemeCellDetailPeriod,
    MonthlyThemeCellDetailResponse,
    MonthlyThemeCellDetailSummary,
    MonthlyThemeCellDetailTheme,
)
from backend.app.services.external_kiwoom_service import ExternalKiwoomService, normalize_stock_code
from backend.app.services.market_theme_flow_analysis_service import MarketThemeFlowAnalysisService


class MonthlyThemeCellDetailService:
    """Read-only detail for a saved monthly supply-theme heatmap cell."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _parse_date(value: str, field_name: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be YYYY-MM-DD",
            ) from exc

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    @staticmethod
    def _to_100m(value: int | float | None) -> float | None:
        return None if value is None else round(float(value) / 100_000_000, 4)

    def get_detail(
        self,
        *,
        theme_id: int,
        event_date: str,
        period_from: str,
        period_to: str,
    ) -> MonthlyThemeCellDetailResponse:
        selected_day = self._parse_date(event_date, "event_date")
        start_day = self._parse_date(period_from, "period_from")
        end_day = self._parse_date(period_to, "period_to")
        if start_day > end_day or not (start_day <= selected_day <= end_day):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="period_from <= event_date <= period_to is required",
            )

        theme = self.db.execute(
            text(
                """
                SELECT mt.id, mt.theme_name,
                       CASE WHEN mt.theme_level='THEME_GROUP' THEN mt.theme_name ELSE parent.theme_name END AS group_name
                FROM market_themes mt
                LEFT JOIN market_themes parent ON parent.id=mt.parent_theme_id
                WHERE mt.id=:theme_id
                """
            ),
            {"theme_id": theme_id},
        ).mappings().first()
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")

        aggregation = ExternalKiwoomService(self.db)._build_supply_theme_aggregation(start_day, end_day)
        period_records = [
            row for row in aggregation["records"]
            if int(row["market_theme_id"]) == theme_id
        ]
        selected_heatmap_records = [
            row for row in period_records if str(row["trade_date"]) == event_date
        ]

        historical_period_rows = self._load_historical_event_stocks(
            theme_id=theme_id,
            period_from=period_from,
            period_to=period_to,
        )
        # The heatmap is classified with the current active stock-theme mapping.
        # Use the exact saved event rows that contributed to the selected cell so
        # the drawer cannot disagree with a visible heatmap value after a stock is
        # reclassified. Historical appearance dates intentionally remain based on
        # the event-time theme links below.
        stocks = self._build_stock_items(
            theme_id=theme_id,
            event_rows=selected_heatmap_records,
            event_date=event_date,
        )

        appearance_dates = sorted({str(row["trade_date"]) for row in historical_period_rows})
        unique_stock_keys = {
            str(row.get("stock_id") or row.get("stock_code") or row.get("stock_name"))
            for row in historical_period_rows
        }
        selected_rates = [
            float(row["change_rate"])
            for row in selected_heatmap_records
            if row.get("change_rate") is not None
        ]
        daily_rates: dict[str, list[float]] = defaultdict(list)
        for row in period_records:
            if row.get("change_rate") is not None:
                daily_rates[str(row["trade_date"])].append(float(row["change_rate"]))
        monthly_daily_averages = [self._mean(values) for values in daily_rates.values()]
        monthly_avg = self._mean([value for value in monthly_daily_averages if value is not None])

        stock_rates = [stock.change_rate for stock in stocks]
        trading_values = [stock.trading_value_100m for stock in stocks if stock.trading_value_100m is not None]
        flow_ready = sum(
            1
            for stock in stocks
            if stock.flow_summary is not None and stock.flow_summary.has_investor_data
        )
        summary = MonthlyThemeCellDetailSummary(
            appearance_days=len(appearance_dates),
            unique_stock_count=len(unique_stock_keys),
            selected_stock_count=len(stocks),
            selected_avg_change_rate=self._mean(selected_rates),
            selected_trading_value_100m=round(sum(trading_values), 4) if trading_values else None,
            rise_count=sum(1 for value in stock_rates if value is not None and value > 0),
            fall_count=sum(1 for value in stock_rates if value is not None and value < 0),
            flat_count=sum(1 for value in stock_rates if value == 0),
            missing_change_count=sum(1 for value in stock_rates if value is None),
            flow_ready_count=flow_ready,
            flow_total_count=len(stocks),
            first_appearance_date=appearance_dates[0] if appearance_dates else None,
            latest_appearance_date=appearance_dates[-1] if appearance_dates else None,
            recent_appearance_dates=appearance_dates,
            monthly_avg_change_rate=monthly_avg,
        )
        return MonthlyThemeCellDetailResponse(
            theme=MonthlyThemeCellDetailTheme(
                id=int(theme["id"]),
                name=str(theme["theme_name"]),
                group_name=str(theme["group_name"]) if theme["group_name"] else None,
            ),
            selected_date=event_date,
            period=MonthlyThemeCellDetailPeriod(from_date=period_from, to_date=period_to),
            summary=summary,
            stocks=stocks,
            queried_at=now_kst(),
        )

    def _load_historical_event_stocks(
        self,
        *,
        theme_id: int,
        period_from: str,
        period_to: str,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                WITH event_theme_pairs AS (
                    SELECT event_id, market_theme_id FROM market_trend_event_theme_links
                    UNION
                    SELECT id AS event_id, theme_id AS market_theme_id
                    FROM market_trend_events WHERE theme_id IS NOT NULL
                )
                SELECT mte.id AS event_id, mte.trade_date,
                       COALESCE(mte.stock_id, s.id) AS stock_id,
                       COALESCE(mte.stock_code, s.stock_code) AS stock_code,
                       COALESCE(mte.stock_name, s.stock_name, mte.stock_code) AS stock_name,
                       mte.change_rate, mte.trading_value
                FROM market_trend_events mte
                JOIN event_theme_pairs pair ON pair.event_id=mte.id
                LEFT JOIN stocks s ON s.id=mte.stock_id OR (mte.stock_id IS NULL AND s.stock_code=mte.stock_code)
                WHERE pair.market_theme_id=:theme_id
                  AND mte.trade_date BETWEEN :period_from AND :period_to
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1)=1
                  AND COALESCE(mte.deleted_at, '')=''
                ORDER BY mte.trade_date, mte.id
                """
            ),
            {"theme_id": theme_id, "period_from": period_from, "period_to": period_to},
        ).mappings().all()
        return [dict(row) for row in rows]

    def _build_stock_items(
        self,
        *,
        theme_id: int,
        event_rows: list[dict[str, Any]],
        event_date: str,
    ) -> list[MarketThemeReturnStockItem]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in event_rows:
            code = normalize_stock_code(row.get("stock_code"))
            stock_id = int(row["stock_id"]) if row.get("stock_id") is not None else None
            key = f"id:{stock_id}" if stock_id is not None else f"code:{code}"
            bucket = grouped.setdefault(
                key,
                {
                    "stock_id": stock_id,
                    "stock_code": code or None,
                    "stock_name": str(row.get("stock_name") or code or "-"),
                    "change_rates": [],
                    "trading_values": [],
                },
            )
            if row.get("change_rate") is not None:
                bucket["change_rates"].append(float(row["change_rate"]))
            if row.get("trading_value") is not None:
                bucket["trading_values"].append(int(row["trading_value"]))

        stock_ids = sorted({int(row["stock_id"]) for row in grouped.values() if row["stock_id"] is not None})
        context: dict[int, dict[str, Any]] = {}
        if stock_ids:
            placeholders = ",".join(f":stock_{index}" for index in range(len(stock_ids)))
            params: dict[str, Any] = {"event_date": event_date, "theme_id": theme_id}
            params.update({f"stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)})
            rows = self.db.execute(
                text(
                    f"""
                    SELECT s.id AS stock_id, s.stock_code, s.stock_name, mts.stock_memo,
                           p.close_price, p.change_rate AS price_change_rate, p.trading_value AS price_trading_value,
                           f.individual_net_amount, f.foreign_net_amount,
                           f.institution_net_amount, f.program_net_amount
                    FROM stocks s
                    LEFT JOIN stock_daily_prices p ON p.stock_id=s.id AND p.trade_date=:event_date
                    LEFT JOIN stock_investor_flows f ON f.stock_id=s.id AND f.flow_date=:event_date
                    LEFT JOIN market_theme_stocks mts ON mts.theme_id=:theme_id AND mts.stock_id=s.id
                    WHERE s.id IN ({placeholders})
                    """
                ),
                params,
            ).mappings().all()
            context = {int(row["stock_id"]): dict(row) for row in rows}

        items: list[MarketThemeReturnStockItem] = []
        for bucket in grouped.values():
            stock_id = bucket["stock_id"]
            saved = context.get(stock_id, {}) if stock_id is not None else {}
            rates = list(bucket["change_rates"])
            trading_values = list(bucket["trading_values"])
            change_rate = self._mean(rates)
            if change_rate is None and saved.get("price_change_rate") is not None:
                change_rate = float(saved["price_change_rate"])
            trading_value = max(trading_values) if trading_values else saved.get("price_trading_value")
            amounts = {
                actor: int(saved[f"{actor}_net_amount"])
                if saved.get(f"{actor}_net_amount") is not None else None
                for actor in MarketThemeFlowAnalysisService.ACTORS
            }
            strengths = {
                actor: MarketThemeFlowAnalysisService._strength(amounts[actor], trading_value)
                for actor in MarketThemeFlowAnalysisService.ACTORS
            }
            has_investor = all(amounts[actor] is not None for actor in ("individual", "foreign", "institution"))
            has_program = amounts["program"] is not None
            flow_summary = None
            if has_investor or has_program:
                flow_summary = {
                    **{f"{actor}_net_amount": amounts[actor] for actor in MarketThemeFlowAnalysisService.ACTORS},
                    **{f"{actor}_flow_strength": strengths[actor] for actor in MarketThemeFlowAnalysisService.ACTORS},
                    "summary_code": MarketThemeFlowAnalysisService._summary_code(
                        strengths["individual"], strengths["foreign"], strengths["institution"]
                    ),
                    "has_investor_data": has_investor,
                    "has_program_data": has_program,
                }
            items.append(
                MarketThemeReturnStockItem(
                    stock_id=int(stock_id or 0),
                    stock_code=str(saved.get("stock_code") or bucket["stock_code"] or "") or None,
                    stock_name=str(saved.get("stock_name") or bucket["stock_name"]),
                    stock_memo=str(saved["stock_memo"]).strip() if saved.get("stock_memo") else None,
                    trading_value_100m=self._to_100m(trading_value),
                    change_rate=change_rate,
                    current_price=int(saved["close_price"]) if saved.get("close_price") is not None else None,
                    data_status="success" if change_rate is not None or trading_value is not None else "missing",
                    flow_summary=flow_summary,
                )
            )
        items.sort(
            key=lambda item: (
                not bool((item.stock_memo or "").strip()),
                (item.stock_memo or "").strip(),
                -(item.trading_value_100m or 0),
                item.stock_name,
                item.stock_id,
            )
        )
        return items
