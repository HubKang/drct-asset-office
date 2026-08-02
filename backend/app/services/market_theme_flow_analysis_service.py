from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.schemas.market_theme_stock_schema import MarketThemeFlowChartResponse


class MarketThemeFlowAnalysisService:
    """Read-only, transient aggregation for theme and stock flow UX."""

    PERIOD_DAYS = {"1M": 20, "3M": 63, "6M": 126}
    ACTORS = ("individual", "foreign", "institution", "program")

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _int(value: Any) -> int | None:
        return None if value is None else int(value)

    @staticmethod
    def _float(value: Any, digits: int = 4) -> float | None:
        if value is None:
            return None
        number = float(value)
        return round(number, digits) if math.isfinite(number) else None

    @staticmethod
    def _strength(net_amount: Any, trading_value: Any) -> float | None:
        if net_amount is None or trading_value in (None, 0):
            return None
        return round(float(net_amount) / float(trading_value) * 100, 4)

    @staticmethod
    def _direction(strength: float | None) -> int | None:
        if strength is None:
            return None
        if abs(strength) < 0.1:
            return 0
        return 1 if strength > 0 else -1

    @classmethod
    def _summary_code(cls, individual: float | None, foreign: float | None, institution: float | None) -> str:
        directions = {
            "individual": cls._direction(individual),
            "foreign": cls._direction(foreign),
            "institution": cls._direction(institution),
        }
        if all(value is None for value in directions.values()):
            return "NO_DATA"
        if directions["foreign"] == 1 and directions["institution"] == 1:
            return "FOREIGN_INSTITUTION_BUY"
        if directions["foreign"] == -1 and directions["institution"] == -1:
            return "FOREIGN_INSTITUTION_SELL"
        if directions["individual"] == 1 and directions["foreign"] != 1 and directions["institution"] != 1:
            return "INDIVIDUAL_LEAD"
        if directions["foreign"] == 1 and (directions["institution"] != 1 or abs(foreign or 0) > abs(institution or 0)):
            return "FOREIGN_LEAD"
        if directions["institution"] == 1 and (directions["foreign"] != 1 or abs(institution or 0) > abs(foreign or 0)):
            return "INSTITUTION_LEAD"
        return "MIXED"

    @staticmethod
    def _quality(connected: int, complete: int) -> tuple[str, float]:
        ratio = round(complete / connected, 4) if connected else 0.0
        if complete == 0:
            return "EMPTY", ratio
        if ratio >= 0.9:
            return "ENOUGH", ratio
        if ratio >= 0.6:
            return "PARTIAL", ratio
        return "INSUFFICIENT", ratio

    def get_daily_context(self, theme_id: int, base_date: str) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
        rows = self.db.execute(
            text(
                """
                SELECT s.id AS stock_id,
                       COALESCE(sdr.trading_value, p.trading_value) AS trading_value,
                       f.individual_net_amount, f.foreign_net_amount,
                       f.institution_net_amount, f.program_net_amount
                FROM market_theme_stocks mts
                JOIN stocks s ON s.id=mts.stock_id AND COALESCE(s.is_active, 1)=1
                LEFT JOIN market_theme_stock_daily_returns sdr
                  ON sdr.theme_id=mts.theme_id AND sdr.stock_id=mts.stock_id AND sdr.return_date=:base_date
                LEFT JOIN stock_daily_prices p
                  ON p.stock_id=mts.stock_id AND p.trade_date=:base_date
                LEFT JOIN stock_investor_flows f
                  ON f.stock_id=mts.stock_id AND f.flow_date=:base_date
                WHERE mts.theme_id=:theme_id AND COALESCE(mts.is_active, 1)=1
                ORDER BY s.id
                """
            ),
            {"theme_id": theme_id, "base_date": base_date},
        ).mappings().all()

        stock_summaries: dict[int, dict[str, Any]] = {}
        totals = {actor: 0 for actor in self.ACTORS}
        data_counts = {actor: 0 for actor in self.ACTORS}
        positive_counts = {actor: 0 for actor in self.ACTORS}
        investor_data_count = program_data_count = complete_count = 0
        theme_trading_value = 0
        theme_trading_value_seen = False
        for row in rows:
            amounts = {actor: self._int(row[f"{actor}_net_amount"]) for actor in self.ACTORS}
            trading_value = self._int(row["trading_value"])
            has_investor = all(amounts[actor] is not None for actor in self.ACTORS[:3])
            has_program = amounts["program"] is not None
            investor_data_count += int(has_investor)
            program_data_count += int(has_program)
            complete_count += int(has_investor and has_program and trading_value not in (None, 0))
            if (has_investor or has_program) and trading_value is not None:
                theme_trading_value += trading_value
                theme_trading_value_seen = True
            strengths = {actor: self._strength(amounts[actor], trading_value) for actor in self.ACTORS}
            for actor in self.ACTORS:
                if amounts[actor] is not None:
                    totals[actor] += int(amounts[actor])
                    data_counts[actor] += 1
                    positive_counts[actor] += int(amounts[actor] > 0)
            stock_summaries[int(row["stock_id"])] = {
                **{f"{actor}_net_amount": amounts[actor] for actor in self.ACTORS},
                **{f"{actor}_flow_strength": strengths[actor] for actor in self.ACTORS},
                "summary_code": self._summary_code(strengths["individual"], strengths["foreign"], strengths["institution"]),
                "has_investor_data": has_investor,
                "has_program_data": has_program,
            }

        connected = len(rows)
        quality, ratio = self._quality(connected, complete_count)
        actor_summaries: dict[str, dict[str, Any]] = {}
        total_strengths: dict[str, float | None] = {}
        for actor in self.ACTORS:
            total_amount = totals[actor] if data_counts[actor] else None
            strength = self._strength(total_amount, theme_trading_value if theme_trading_value_seen else None)
            total_strengths[actor] = strength
            actor_summaries[actor] = {
                "net_amount": total_amount,
                "flow_strength": strength,
                "positive_stock_count": positive_counts[actor],
                "data_stock_count": data_counts[actor],
            }
        theme_summary = {
            "base_date": base_date,
            "aggregation_basis": "CURRENT_ACTIVE_LINKS",
            "attribution_mode": "FULL",
            "connected_stock_count": connected,
            "investor_data_stock_count": investor_data_count,
            "program_data_stock_count": program_data_count,
            "complete_stock_count": complete_count,
            "completeness_ratio": ratio,
            "quality_status": quality,
            "theme_trading_value": theme_trading_value if theme_trading_value_seen else None,
            "summary_code": self._summary_code(total_strengths["individual"], total_strengths["foreign"], total_strengths["institution"]),
            **actor_summaries,
        }
        return theme_summary, stock_summaries

    def get_chart(self, theme_id: int, *, period: str, focus_date: str | None = None) -> MarketThemeFlowChartResponse:
        period_code = period.upper()
        if period_code not in self.PERIOD_DAYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="period must be 1M, 3M, or 6M")
        theme = self.db.execute(
            text("SELECT id, theme_name FROM market_themes WHERE id=:theme_id"), {"theme_id": theme_id}
        ).mappings().first()
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="theme not found")

        dates = self.db.execute(
            text(
                """
                SELECT
                  (SELECT MAX(return_date) FROM market_theme_daily_returns WHERE theme_id=:theme_id) AS return_latest,
                  (SELECT MAX(f.flow_date)
                     FROM market_theme_stocks mts
                     JOIN stock_investor_flows f ON f.stock_id=mts.stock_id
                    WHERE mts.theme_id=:theme_id AND COALESCE(mts.is_active, 1)=1
                      AND (f.individual_net_amount IS NOT NULL OR f.foreign_net_amount IS NOT NULL
                           OR f.institution_net_amount IS NOT NULL OR f.program_net_amount IS NOT NULL)) AS flow_latest
                """
            ),
            {"theme_id": theme_id},
        ).mappings().one()
        return_latest = str(dates["return_latest"]) if dates["return_latest"] else None
        flow_latest = str(dates["flow_latest"]) if dates["flow_latest"] else None
        common_latest = min(return_latest, flow_latest) if return_latest and flow_latest else None
        requested_days = self.PERIOD_DAYS[period_code]
        return_rows: list[dict[str, Any]] = []
        if common_latest:
            desc = self.db.execute(
                text(
                    """SELECT return_date, avg_change_rate, total_trading_value
                       FROM market_theme_daily_returns
                      WHERE theme_id=:theme_id AND return_date<=:end_date
                      ORDER BY return_date DESC LIMIT :limit"""
                ),
                {"theme_id": theme_id, "end_date": common_latest, "limit": requested_days},
            ).mappings().all()
            return_rows = [dict(row) for row in reversed(desc)]
        start_date = str(return_rows[0]["return_date"]) if return_rows else None
        end_date = str(return_rows[-1]["return_date"]) if return_rows else common_latest

        flow_map: dict[str, dict[str, Any]] = {}
        connected = 0
        if start_date and end_date:
            connected = int(self.db.execute(
                text("SELECT COUNT(*) FROM market_theme_stocks WHERE theme_id=:theme_id AND COALESCE(is_active,1)=1"),
                {"theme_id": theme_id},
            ).scalar() or 0)
            flow_rows = self.db.execute(
                text(
                    """
                    SELECT f.flow_date,
                           SUM(f.individual_net_amount) individual_daily_amount,
                           SUM(f.foreign_net_amount) foreign_daily_amount,
                           SUM(f.institution_net_amount) institution_daily_amount,
                           SUM(f.program_net_amount) program_daily_amount,
                           SUM(CASE WHEN f.individual_net_amount>0 THEN 1 ELSE 0 END) individual_positive_stock_count,
                           SUM(CASE WHEN f.foreign_net_amount>0 THEN 1 ELSE 0 END) foreign_positive_stock_count,
                           SUM(CASE WHEN f.institution_net_amount>0 THEN 1 ELSE 0 END) institution_positive_stock_count,
                           SUM(CASE WHEN f.program_net_amount>0 THEN 1 ELSE 0 END) program_positive_stock_count,
                           SUM(CASE WHEN f.individual_net_amount IS NOT NULL THEN 1 ELSE 0 END) individual_data_stock_count,
                           SUM(CASE WHEN f.foreign_net_amount IS NOT NULL THEN 1 ELSE 0 END) foreign_data_stock_count,
                           SUM(CASE WHEN f.institution_net_amount IS NOT NULL THEN 1 ELSE 0 END) institution_data_stock_count,
                           SUM(CASE WHEN f.individual_net_amount IS NOT NULL AND f.foreign_net_amount IS NOT NULL
                                         AND f.institution_net_amount IS NOT NULL THEN 1 ELSE 0 END) investor_data_stock_count,
                           SUM(CASE WHEN f.program_net_amount IS NOT NULL THEN 1 ELSE 0 END) program_data_stock_count,
                           SUM(CASE WHEN f.individual_net_amount IS NOT NULL AND f.foreign_net_amount IS NOT NULL
                                         AND f.institution_net_amount IS NOT NULL AND f.program_net_amount IS NOT NULL
                                         AND COALESCE(p.trading_value,0)>0 THEN 1 ELSE 0 END) complete_stock_count,
                           SUM(CASE WHEN (f.individual_net_amount IS NOT NULL OR f.foreign_net_amount IS NOT NULL
                                              OR f.institution_net_amount IS NOT NULL OR f.program_net_amount IS NOT NULL)
                                         THEN p.trading_value END) theme_trading_value
                      FROM market_theme_stocks mts
                      JOIN stock_investor_flows f ON f.stock_id=mts.stock_id
                      LEFT JOIN stock_daily_prices p ON p.stock_id=f.stock_id AND p.trade_date=f.flow_date
                     WHERE mts.theme_id=:theme_id AND COALESCE(mts.is_active,1)=1
                       AND f.flow_date BETWEEN :start_date AND :end_date
                     GROUP BY f.flow_date ORDER BY f.flow_date
                    """
                ),
                {"theme_id": theme_id, "start_date": start_date, "end_date": end_date},
            ).mappings().all()
            flow_map = {str(row["flow_date"]): dict(row) for row in flow_rows}

        cumulative = {actor: 0 for actor in self.ACTORS}
        has_value = {actor: False for actor in self.ACTORS}
        positive_days = {actor: 0 for actor in self.ACTORS}
        series: list[dict[str, Any]] = []
        compound = 1.0
        for row in return_rows:
            trade_date = str(row["return_date"])
            flow = flow_map.get(trade_date, {})
            daily_return = self._float(row["avg_change_rate"])
            if daily_return is not None:
                compound *= 1 + daily_return / 100
                cumulative_return = round((compound - 1) * 100, 4)
            else:
                cumulative_return = None
            item: dict[str, Any] = {
                "trade_date": trade_date,
                "theme_daily_return_pct": daily_return,
                "theme_cumulative_return_pct": cumulative_return,
                "theme_trading_value": self._int(flow.get("theme_trading_value") or row.get("total_trading_value")),
                "connected_stock_count": connected,
            }
            for actor in self.ACTORS:
                daily = self._int(flow.get(f"{actor}_daily_amount"))
                if daily is None:
                    actor_cumulative = None
                else:
                    cumulative[actor] += daily
                    has_value[actor] = True
                    positive_days[actor] += int(daily > 0)
                    actor_cumulative = cumulative[actor]
                item[f"{actor}_daily_amount"] = daily
                item[f"{actor}_cumulative_amount"] = actor_cumulative
                item[f"{actor}_positive_stock_count"] = int(flow.get(f"{actor}_positive_stock_count") or 0)
                item[f"{actor}_data_stock_count"] = int(
                    flow.get("program_data_stock_count" if actor == "program" else f"{actor}_data_stock_count") or 0
                )
            investor_count = int(flow.get("investor_data_stock_count") or 0)
            program_count = int(flow.get("program_data_stock_count") or 0)
            complete_count = int(flow.get("complete_stock_count") or 0)
            item.update({
                "investor_data_stock_count": investor_count,
                "program_data_stock_count": program_count,
                "complete_stock_count": complete_count,
                "completeness_ratio": round(complete_count / connected, 4) if connected else 0.0,
            })
            series.append(item)

        latest_complete = series[-1]["complete_stock_count"] if series else 0
        quality, _ = self._quality(connected, int(latest_complete))
        summary_actors = {
            actor: {
                "cumulative_amount": cumulative[actor] if has_value[actor] else None,
                "positive_days": positive_days[actor],
                "positive_stock_count": series[-1][f"{actor}_positive_stock_count"] if series else 0,
                "data_stock_count": series[-1][f"{actor}_data_stock_count"] if series else 0,
            }
            for actor in self.ACTORS
        }
        selected = next((item for item in series if item["trade_date"] == focus_date), None) if focus_date else None
        return MarketThemeFlowChartResponse(
            theme_id=theme_id,
            theme_name=str(theme["theme_name"]),
            period={
                "code": period_code, "requested_trading_days": requested_days,
                "actual_trading_days": len(series), "start_date": start_date, "end_date": end_date,
            },
            latest_theme_return_date=return_latest,
            latest_flow_date=flow_latest,
            common_latest_date=common_latest,
            data_quality=quality,
            summary={
                "theme_return_pct": series[-1]["theme_cumulative_return_pct"] if series else None,
                **summary_actors,
            },
            series=series,
            focus_date=focus_date,
            selected=selected,
        )
