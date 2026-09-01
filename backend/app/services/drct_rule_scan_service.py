from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.entities.drct_stock_signal import DrctSignalSearchRule, DrctSignalSearchVersion
from backend.app.services.drct_rule_engine import DrctRuleEvaluator, DrctRuleValidator


class DrctRuleUniverseService:
    def __init__(self, db: Session):
        self.db = db

    def load(self) -> list[dict[str, Any]]:
        rows = self.db.execute(text("""
            SELECT s.id AS stock_id, s.stock_code, s.stock_name,
                   t.id AS theme_id, t.theme_name
            FROM market_theme_stocks mts
            JOIN market_themes t ON t.id=mts.theme_id
            JOIN stocks s ON s.id=mts.stock_id
            WHERE mts.is_active=1 AND t.is_active=1
              AND COALESCE(t.theme_level, 'THEME')='THEME'
              AND COALESCE(s.is_active, 1)=1
            ORDER BY s.id, t.sort_order, t.theme_name
        """)).mappings().all()
        by_stock: dict[int, dict[str, Any]] = {}
        for row in rows:
            stock_id = int(row["stock_id"])
            item = by_stock.setdefault(stock_id, {
                "stock_id": stock_id,
                "stock_code": str(row["stock_code"]),
                "stock_name": str(row["stock_name"]),
                "theme_names": [],
            })
            if row["theme_name"] not in item["theme_names"]:
                item["theme_names"].append(str(row["theme_name"]))
        return list(by_stock.values())


class DrctRuleScanService:
    def __init__(self, db: Session):
        self.db = db

    def _current_rule(self, search_id: int) -> tuple[DrctSignalSearchVersion, DrctSignalSearchRule, dict[str, Any]]:
        version = self.db.execute(text("""
            SELECT version.* FROM drct_signal_search_versions version
            JOIN drct_signal_searches search ON search.id=version.search_id
            WHERE search.id=:search_id AND version.is_current=1
        """), {"search_id": search_id}).mappings().first()
        if version is None:
            raise HTTPException(404, "검색식 또는 현재 Version을 찾을 수 없습니다.")
        rule_row = self.db.scalar(text("SELECT id FROM drct_signal_search_rules WHERE search_version_id=:version_id"), {"version_id": version["id"]})
        if rule_row is None:
            raise HTTPException(409, "현재 Version에 DrCT 실행 Rule이 구성되지 않았습니다.")
        rule = self.db.get(DrctSignalSearchRule, int(rule_row))
        if rule is None:
            raise HTTPException(409, "현재 Version에 DrCT 실행 Rule이 구성되지 않았습니다.")
        payload = json.loads(rule.rule_json)
        validation = DrctRuleValidator.validate(payload)
        if validation.status != "VALID" or rule.validation_status != "VALID":
            message = validation.errors[0]["message"] if validation.errors else "Rule 검증이 완료되지 않았습니다."
            raise HTTPException(409, message)
        version_entity = self.db.get(DrctSignalSearchVersion, int(version["id"]))
        assert version_entity is not None
        return version_entity, rule, payload

    def _analysis_date(self, universe_ids: list[int], requested: date | None) -> str:
        if requested is not None:
            return requested.isoformat()
        if not universe_ids:
            raise HTTPException(409, "분석할 활성 테마 연결 종목이 없습니다.")
        row = self.db.execute(text("""
            SELECT MIN(latest_trade_date) AS analysis_date
            FROM (
                SELECT prices.stock_id, MAX(prices.trade_date) AS latest_trade_date
                FROM stock_daily_prices prices
                WHERE prices.stock_id IN (SELECT mts.stock_id FROM market_theme_stocks mts
                    JOIN market_themes t ON t.id=mts.theme_id
                    JOIN stocks s ON s.id=mts.stock_id
                    WHERE mts.is_active=1 AND t.is_active=1
                      AND COALESCE(t.theme_level, 'THEME')='THEME'
                      AND COALESCE(s.is_active,1)=1)
                GROUP BY prices.stock_id
            ) completed
        """)).mappings().one()
        if not row["analysis_date"]:
            raise HTTPException(409, "Universe에 분석 가능한 가격 데이터가 없습니다.")
        return str(row["analysis_date"])[:10]

    def _bulk_prices(self, stock_ids: list[int], analysis_date: str, row_count: int) -> dict[int, list[dict[str, Any]]]:
        if not stock_ids:
            return {}
        params: dict[str, Any] = {"analysis_date": analysis_date, "row_count": row_count}
        placeholders = []
        for index, stock_id in enumerate(stock_ids):
            key = f"stock_{index}"
            params[key] = stock_id
            placeholders.append(f":{key}")
        rows = self.db.execute(text(f"""
            WITH ranked AS (
                SELECT stock_id, trade_date, open_price, high_price, low_price, close_price,
                       volume, trading_value, ma5, ma10, ma20, ma60, ma120, ma240,
                       ROW_NUMBER() OVER (PARTITION BY stock_id ORDER BY trade_date DESC) AS rn
                FROM stock_daily_prices
                WHERE stock_id IN ({', '.join(placeholders)}) AND trade_date<=:analysis_date
            )
            SELECT * FROM ranked WHERE rn<=:row_count ORDER BY stock_id, rn
        """), params).mappings().all()
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[int(row["stock_id"])].append(dict(row))
        return grouped

    def _bulk_market_caps(self, stock_ids: list[int], analysis_date: str) -> dict[int, int]:
        if not stock_ids:
            return {}
        params: dict[str, Any] = {"analysis_date": analysis_date}
        placeholders = []
        for index, stock_id in enumerate(stock_ids):
            key = f"metric_stock_{index}"
            params[key] = stock_id
            placeholders.append(f":{key}")
        rows = self.db.execute(text(f"""
            WITH ranked AS (
                SELECT stock_id, market_cap,
                       ROW_NUMBER() OVER (PARTITION BY stock_id ORDER BY updated_at DESC, id DESC) AS rn
                FROM stock_daily_market_metrics
                WHERE stock_id IN ({', '.join(placeholders)})
                  AND trade_date=:analysis_date AND market_cap IS NOT NULL
            )
            SELECT stock_id, market_cap FROM ranked WHERE rn=1
        """), params).mappings().all()
        return {int(row["stock_id"]): int(row["market_cap"]) for row in rows if row["market_cap"] is not None}

    def _evaluate_all(self, rule: dict[str, Any], requested_date: date | None) -> tuple[str, list[dict[str, Any]], int]:
        started = time.perf_counter()
        universe = DrctRuleUniverseService(self.db).load()
        stock_ids = [item["stock_id"] for item in universe]
        analysis_date = self._analysis_date(stock_ids, requested_date)
        validation = DrctRuleValidator.validate(rule)
        price_by_stock = self._bulk_prices(stock_ids, analysis_date, validation.required_lookback + 1)
        caps = self._bulk_market_caps(stock_ids, analysis_date)
        results: list[dict[str, Any]] = []
        for stock in universe:
            rows = price_by_stock.get(stock["stock_id"], [])
            if not rows or str(rows[0]["trade_date"])[:10] != analysis_date:
                evaluated = {"status": "DATA_INCOMPLETE", "conditions": [{
                    "code": "DATA", "type": "PRICE_DATA", "label": "분석 기준일 가격",
                    "status": "DATA_INCOMPLETE", "criteria": f"trade_date={analysis_date}",
                    "actual_value": "분석 기준일 가격 데이터가 없습니다.",
                }]}
            else:
                evaluated = DrctRuleEvaluator.evaluate(rule, rows, caps.get(stock["stock_id"]))
            results.append({
                **stock,
                "analysis_date": analysis_date,
                "close": float(rows[0]["close_price"]) if rows and rows[0].get("close_price") is not None else None,
                **evaluated,
            })
        return analysis_date, results, int((time.perf_counter() - started) * 1000)

    def preview(self, search_id: int, analysis_date: date | None, include_all: bool = False) -> dict[str, Any]:
        version, _rule_row, rule = self._current_rule(search_id)
        resolved_date, results, elapsed_ms = self._evaluate_all(rule, analysis_date)
        counts = {status: sum(1 for item in results if item["status"] == status) for status in ("MATCH", "NO_MATCH", "DATA_INCOMPLETE")}
        visible = results if include_all else [item for item in results if item["status"] == "MATCH"]
        return {
            "search_id": search_id,
            "search_version_id": version.id,
            "version_no": version.version_no,
            "analysis_date": resolved_date,
            "universe_count": len(results),
            "evaluable_count": counts["MATCH"] + counts["NO_MATCH"],
            "data_incomplete_count": counts["DATA_INCOMPLETE"],
            "matched_count": counts["MATCH"],
            "elapsed_ms": elapsed_ms,
            "items": [{key: value for key, value in item.items() if key != "conditions"} for item in visible],
        }

    def diagnose(self, search_id: int, stock_id: int, analysis_date: date | None) -> dict[str, Any]:
        version, _rule_row, rule = self._current_rule(search_id)
        resolved_date, results, elapsed_ms = self._evaluate_all(rule, analysis_date)
        item = next((row for row in results if row["stock_id"] == stock_id), None)
        if item is None:
            raise HTTPException(404, "해당 종목은 현재 활성 테마 Universe에 포함되지 않습니다.")
        return {"search_id": search_id, "search_version_id": version.id, "version_no": version.version_no, "elapsed_ms": elapsed_ms, **item, "analysis_date": resolved_date}
