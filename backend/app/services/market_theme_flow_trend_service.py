from __future__ import annotations

from collections import OrderedDict, defaultdict
from copy import deepcopy
import json
import math
from threading import Lock
from time import monotonic, perf_counter
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.schemas.market_theme_stock_schema import MarketThemeFlowTrendResponse


ACTORS = {"FOREIGN", "INSTITUTION", "FOREIGN_INSTITUTION", "INDIVIDUAL", "PROGRAM"}
METRICS = {"FLOW_STRENGTH", "NET_AMOUNT", "BREADTH"}
ATTRIBUTIONS = {"FRACTIONAL", "FULL"}


class _TrendCache:
    def __init__(self, ttl_seconds: int = 60, max_entries: int = 64) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.pop(key, None)
            if item is None or item[0] <= monotonic():
                return None
            self._items[key] = item
            return deepcopy(item[1])

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._items.pop(key, None)
            self._items[key] = (monotonic() + self.ttl_seconds, deepcopy(value))
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


MARKET_THEME_FLOW_TREND_CACHE = _TrendCache()


def invalidate_market_theme_flow_trend_cache() -> None:
    MARKET_THEME_FLOW_TREND_CACHE.clear()


class MarketThemeFlowTrendService:
    """Read-only, current-link attribution for the daily theme flow heatmap."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _quality(connected: int, data_count: int) -> tuple[str, float]:
        ratio = round(data_count / connected, 4) if connected else 0.0
        if data_count == 0:
            return "EMPTY", ratio
        if ratio >= 0.9:
            return "ENOUGH", ratio
        if ratio >= 0.6:
            return "PARTIAL", ratio
        return "INSUFFICIENT", ratio

    @staticmethod
    def _safe_float(value: Any, digits: int = 4) -> float | None:
        if value is None:
            return None
        number = float(value)
        return round(number, digits) if math.isfinite(number) else None

    @staticmethod
    def _actor_amount(row: dict[str, Any], actor: str) -> int | None:
        if actor == "FOREIGN_INSTITUTION":
            foreign = row.get("foreign_net_amount")
            institution = row.get("institution_net_amount")
            return None if foreign is None or institution is None else int(foreign) + int(institution)
        field = {
            "FOREIGN": "foreign_net_amount",
            "INSTITUTION": "institution_net_amount",
            "INDIVIDUAL": "individual_net_amount",
            "PROGRAM": "program_net_amount",
        }[actor]
        return None if row.get(field) is None else int(row[field])

    @staticmethod
    def _in_clause(prefix: str, values: list[int]) -> tuple[str, dict[str, int]]:
        params = {f"{prefix}_{index}": value for index, value in enumerate(values)}
        return ",".join(f":{key}" for key in params), params

    def get_trend(
        self,
        *,
        end_date: str,
        recent_days: int = 30,
        actor: str = "FOREIGN",
        metric: str = "FLOW_STRENGTH",
        attribution: str = "FRACTIONAL",
        theme_group_id: int | None = None,
        search: str | None = None,
        limit: int | None = 20,
        refresh: bool = False,
    ) -> MarketThemeFlowTrendResponse:
        actor, metric, attribution = actor.upper(), metric.upper(), attribution.upper()
        if actor not in ACTORS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid actor")
        if metric not in METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid metric")
        if attribution not in ATTRIBUTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid attribution")
        if not 1 <= recent_days <= 60:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="recent_days must be 1..60")
        normalized_search = (search or "").strip().lower()
        cache_key = "|".join(map(str, (end_date, recent_days, actor, metric, attribution, theme_group_id, normalized_search, limit)))
        if refresh:
            MARKET_THEME_FLOW_TREND_CACHE.clear()
        else:
            cache_started = perf_counter()
            cached = MARKET_THEME_FLOW_TREND_CACHE.get(cache_key)
            if cached is not None:
                cached["performance"] = {
                    **cached.get("performance", {}),
                    "cache_hit": True,
                    "query_count": 0,
                    "query_ms": 0.0,
                    "calculation_ms": 0.0,
                    "serialization_ms": 0.0,
                    "total_ms": round((perf_counter() - cache_started) * 1000, 3),
                }
                return MarketThemeFlowTrendResponse(**cached)

        started = perf_counter()
        query_count = 0
        query_started = perf_counter()
        link_rows = self.db.execute(text("""
            WITH active_links AS (
                SELECT DISTINCT mts.theme_id, mts.stock_id
                  FROM market_theme_stocks mts
                  JOIN market_themes t0 ON t0.id=mts.theme_id AND COALESCE(t0.is_active,1)=1
                  JOIN stocks s0 ON s0.id=mts.stock_id AND COALESCE(s0.is_active,1)=1
                 WHERE COALESCE(mts.is_active,1)=1 AND COALESCE(t0.theme_level,'THEME')='THEME'
            )
            SELECT links.theme_id, links.stock_id, t.theme_name, t.parent_theme_id AS theme_group_id,
                   p.theme_name AS theme_group_name, COALESCE(t.sort_order, 0) AS sort_order,
                   s.stock_code, s.stock_name,
                   COUNT(*) OVER (PARTITION BY links.stock_id) AS active_theme_count
              FROM active_links links
              JOIN market_themes t ON t.id=links.theme_id
              LEFT JOIN market_themes p ON p.id=t.parent_theme_id
              JOIN stocks s ON s.id=links.stock_id
             ORDER BY t.sort_order, t.theme_name, s.id
        """)).mappings().all()
        query_count += 1
        all_links = [dict(row) for row in link_rows]
        target_links = [row for row in all_links if (theme_group_id is None or int(row.get("theme_group_id") or 0) == theme_group_id)
                        and (not normalized_search or normalized_search in str(row["theme_name"]).lower())]
        target_theme_ids = sorted({int(row["theme_id"]) for row in target_links})
        target_stock_ids = sorted({int(row["stock_id"]) for row in target_links})

        dates: list[str] = []
        if target_stock_ids and target_theme_ids:
            stock_clause, stock_params = self._in_clause("date_stock", target_stock_ids)
            date_theme_clause, date_theme_params = self._in_clause("date_theme", target_theme_ids)
            date_rows = self.db.execute(text(f"""
                SELECT DISTINCT flow_date FROM stock_investor_flows
                 WHERE stock_id IN ({stock_clause}) AND flow_date<=:end_date
                   AND EXISTS (
                       SELECT 1 FROM market_theme_daily_returns r
                        WHERE r.theme_id IN ({date_theme_clause}) AND r.return_date=stock_investor_flows.flow_date
                   )
                 ORDER BY flow_date DESC LIMIT :recent_days
            """), {**stock_params, **date_theme_params, "end_date": end_date, "recent_days": recent_days}).all()
            query_count += 1
            dates = sorted(str(row[0]) for row in date_rows)

        raw_by_stock: dict[int, list[dict[str, Any]]] = defaultdict(list)
        if dates and target_stock_ids:
            stock_clause, stock_params = self._in_clause("flow_stock", target_stock_ids)
            flow_rows = self.db.execute(text(f"""
                SELECT f.stock_id, f.flow_date, f.individual_net_amount, f.foreign_net_amount,
                       f.institution_net_amount, f.program_net_amount,
                       COALESCE(saved_return.trading_value, p.trading_value * 1000000) AS trading_value
                  FROM stock_investor_flows f
                  LEFT JOIN stock_daily_prices p ON p.stock_id=f.stock_id AND p.trade_date=f.flow_date
                  LEFT JOIN (
                        SELECT stock_id, return_date, MAX(trading_value) AS trading_value
                          FROM market_theme_stock_daily_returns
                         GROUP BY stock_id, return_date
                  ) saved_return ON saved_return.stock_id=f.stock_id AND saved_return.return_date=f.flow_date
                 WHERE f.stock_id IN ({stock_clause}) AND f.flow_date BETWEEN :start_date AND :end_date
                 ORDER BY f.stock_id, f.flow_date
            """), {**stock_params, "start_date": dates[0], "end_date": dates[-1]}).mappings().all()
            query_count += 1
            for row in flow_rows:
                raw_by_stock[int(row["stock_id"])].append(dict(row))

        return_map: dict[tuple[int, str], float | None] = {}
        if dates and target_theme_ids:
            theme_clause, theme_params = self._in_clause("return_theme", target_theme_ids)
            return_rows = self.db.execute(text(f"""
                SELECT theme_id, return_date, avg_change_rate FROM market_theme_daily_returns
                 WHERE theme_id IN ({theme_clause}) AND return_date BETWEEN :start_date AND :end_date
            """), {**theme_params, "start_date": dates[0], "end_date": dates[-1]}).mappings().all()
            query_count += 1
            return_map = {(int(row["theme_id"]), str(row["return_date"])): self._safe_float(row["avg_change_rate"])
                          for row in return_rows}
        query_ms = (perf_counter() - query_started) * 1000

        calculation_started = perf_counter()
        links_by_theme: dict[int, list[dict[str, Any]]] = defaultdict(list)
        theme_meta: dict[int, dict[str, Any]] = {}
        for link in target_links:
            theme_id = int(link["theme_id"])
            links_by_theme[theme_id].append(link)
            theme_meta.setdefault(theme_id, link)

        theme_payloads: list[dict[str, Any]] = []
        five_day_amounts: dict[int, int | None] = {}
        for theme_id in target_theme_ids:
            links = links_by_theme[theme_id]
            connected = len(links)
            stock_meta = {int(link["stock_id"]): link for link in links}
            accumulators: dict[str, dict[str, Any]] = {
                day: {"net": 0.0, "trading": 0.0, "data": 0, "positive": 0, "negative": 0, "zero": 0, "contributors": []}
                for day in dates
            }
            for stock_id, link in stock_meta.items():
                factor = 1.0 / max(1, int(link["active_theme_count"])) if attribution == "FRACTIONAL" else 1.0
                for raw in raw_by_stock.get(stock_id, []):
                    day = str(raw["flow_date"])
                    if day not in accumulators:
                        continue
                    amount = self._actor_amount(raw, actor)
                    if amount is None:
                        continue
                    bucket = accumulators[day]
                    attributed_amount = amount * factor
                    bucket["net"] += attributed_amount
                    bucket["data"] += 1
                    bucket["positive"] += int(amount > 0)
                    bucket["negative"] += int(amount < 0)
                    bucket["zero"] += int(amount == 0)
                    if raw.get("trading_value") is not None:
                        bucket["trading"] += int(raw["trading_value"]) * factor
                    bucket["contributors"].append({
                        "stock_id": stock_id, "stock_code": link.get("stock_code"),
                        "stock_name": str(link.get("stock_name") or link.get("stock_code") or stock_id),
                        "net_buy_amount": int(round(attributed_amount)),
                    })

            cells: list[dict[str, Any]] = []
            for day in dates:
                bucket = accumulators[day]
                data_count = int(bucket["data"])
                quality, completeness = self._quality(connected, data_count)
                net = int(round(bucket["net"])) if data_count else None
                trading = int(round(bucket["trading"])) if data_count and bucket["trading"] > 0 else None
                strength = round(net / trading * 100, 4) if net is not None and trading else None
                breadth = round(bucket["positive"] / data_count * 100, 4) if data_count else None
                contributors = sorted(bucket["contributors"], key=lambda item: item["net_buy_amount"], reverse=True)[:3]
                cells.append({
                    "trade_date": day, "net_buy_amount": net, "trading_value": trading,
                    "flow_strength": strength, "breadth_ratio": breadth,
                    "positive_stock_count": bucket["positive"], "negative_stock_count": bucket["negative"],
                    "zero_stock_count": bucket["zero"], "actor_data_stock_count": data_count,
                    "connected_stock_count": connected, "missing_stock_count": max(0, connected - data_count),
                    "completeness_ratio": completeness, "data_quality": quality,
                    "theme_return_pct": return_map.get((theme_id, day)), "top_contributors": contributors,
                })

            last_twenty = cells[-20:]
            valid_twenty = [cell for cell in last_twenty if cell["net_buy_amount"] is not None]
            cumulative_net = sum(int(cell["net_buy_amount"]) for cell in valid_twenty) if valid_twenty else None
            trading_values = [int(cell["trading_value"]) for cell in valid_twenty if cell["trading_value"] is not None]
            cumulative_trading = sum(trading_values) if trading_values else None
            period_strength = round(cumulative_net / cumulative_trading * 100, 4) if cumulative_net is not None and cumulative_trading else None
            latest = cells[-1] if cells else None
            streak = 0
            for cell in reversed(cells):
                value = cell["net_buy_amount"]
                if value is None or value == 0 or (streak > 0 and value < 0) or (streak < 0 and value > 0):
                    break
                streak += 1 if value > 0 else -1
            five_valid = [cell for cell in cells[-5:] if cell["net_buy_amount"] is not None]
            five_day_amounts[theme_id] = sum(int(cell["net_buy_amount"]) for cell in five_valid) if five_valid else None
            meta = theme_meta[theme_id]
            summary = {
                "cumulative_net_buy_amount": cumulative_net, "cumulative_trading_value": cumulative_trading,
                "flow_strength": period_strength, "latest_breadth_ratio": latest["breadth_ratio"] if latest else None,
                "positive_stock_count": latest["positive_stock_count"] if latest else 0,
                "actor_data_stock_count": latest["actor_data_stock_count"] if latest else 0,
                "current_streak": streak, "connected_stock_count": connected,
                "completeness_ratio": latest["completeness_ratio"] if latest else 0.0,
                "data_quality": latest["data_quality"] if latest else "EMPTY",
            }
            theme_payloads.append({
                "theme_id": theme_id, "theme_name": str(meta["theme_name"]),
                "theme_group_id": meta.get("theme_group_id"), "theme_group_name": meta.get("theme_group_name"),
                "sort_order": int(meta.get("sort_order") or 0), "connected_stock_count": connected,
                "twenty_day_summary": summary, "cells": cells,
            })

        quality_rank = {"ENOUGH": 3, "PARTIAL": 2, "INSUFFICIENT": 1, "EMPTY": 0}
        def latest_of(theme: dict[str, Any]) -> dict[str, Any] | None:
            return theme["cells"][-1] if theme["cells"] else None

        def top_item(theme: dict[str, Any], *, five_day: bool = False) -> dict[str, Any]:
            latest = latest_of(theme) or {}
            summary = theme["twenty_day_summary"]
            return {
                "theme_id": theme["theme_id"], "theme_name": theme["theme_name"],
                "flow_strength": latest.get("flow_strength"),
                "net_buy_amount": five_day_amounts.get(theme["theme_id"]) if five_day else latest.get("net_buy_amount"),
                "breadth_ratio": latest.get("breadth_ratio"), "positive_stock_count": latest.get("positive_stock_count", 0),
                "actor_data_stock_count": latest.get("actor_data_stock_count", 0), "current_streak": summary["current_streak"],
                "completeness_ratio": latest.get("completeness_ratio", 0.0), "data_quality": latest.get("data_quality", "EMPTY"),
            }

        def choose(value_getter, *, positive_only: bool = False) -> dict[str, Any] | None:
            candidates = [theme for theme in theme_payloads if value_getter(theme) is not None and (not positive_only or value_getter(theme) > 0)]
            if not candidates:
                return None
            return max(candidates, key=lambda theme: (
                value_getter(theme), quality_rank.get((latest_of(theme) or {}).get("data_quality", "EMPTY"), 0),
                (latest_of(theme) or {}).get("flow_strength") or -math.inf, -theme["sort_order"],
            ))

        today_theme = choose(lambda theme: (latest_of(theme) or {}).get("flow_strength"))
        five_theme = choose(lambda theme: five_day_amounts.get(theme["theme_id"]))
        breadth_theme = choose(lambda theme: (latest_of(theme) or {}).get("breadth_ratio"))
        streak_theme = choose(lambda theme: max(0, theme["twenty_day_summary"]["current_streak"]), positive_only=True)
        summary_payload = {
            "top_today": top_item(today_theme) if today_theme else None,
            "top_five_day": top_item(five_theme, five_day=True) if five_theme else None,
            "top_breadth": top_item(breadth_theme) if breadth_theme else None,
            "top_streak": top_item(streak_theme) if streak_theme else None,
        }

        metric_key = {"FLOW_STRENGTH": "flow_strength", "NET_AMOUNT": "net_buy_amount", "BREADTH": "breadth_ratio"}[metric]
        theme_payloads.sort(key=lambda theme: (
            (latest_of(theme) or {}).get(metric_key) is None,
            -float((latest_of(theme) or {}).get(metric_key) or 0),
            -quality_rank.get((latest_of(theme) or {}).get("data_quality", "EMPTY"), 0),
            theme["sort_order"], theme["theme_name"],
        ))
        if limit is not None:
            theme_payloads = theme_payloads[:limit]
        calculation_ms = (perf_counter() - calculation_started) * 1000
        payload: dict[str, Any] = {
            "request": {
                "end_date": end_date, "actual_end_date": dates[-1] if dates else None, "recent_days": recent_days,
                "actor": actor, "metric": metric, "attribution_mode": attribution,
                "aggregation_basis": "CURRENT_ACTIVE_LINKS", "theme_group_id": theme_group_id,
                "search": search.strip() if search and search.strip() else None, "limit": limit,
            },
            "dates": dates, "summary": summary_payload, "themes": theme_payloads,
            "performance": {
                "cache_hit": False, "query_count": query_count, "query_ms": round(query_ms, 3),
                "calculation_ms": round(calculation_ms, 3),
            },
        }
        payload["performance"]["total_ms"] = round((perf_counter() - started) * 1000, 3)
        serialization_started = perf_counter()
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        payload["performance"]["serialization_ms"] = round((perf_counter() - serialization_started) * 1000, 3)
        payload["performance"]["payload_bytes"] = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        MARKET_THEME_FLOW_TREND_CACHE.put(cache_key, payload)
        return MarketThemeFlowTrendResponse(**payload)
