from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session


class MarketIndicatorService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _as_bool(value: Any) -> bool:
        return bool(int(value or 0))

    def get_category_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            text("""
                SELECT category, COUNT(*) AS count
                FROM market_indicators
                WHERE is_active = 1
                GROUP BY category
            """)
        ).mappings().all()
        return {str(row["category"]): int(row["count"] or 0) for row in rows}

    def list_indicators(self, *, category: str | None = None, active_only: bool = True) -> dict[str, Any]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if active_only:
            clauses.append("is_active = 1")
        if category:
            clauses.append("category = :category")
            params["category"] = category
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT *
                FROM market_indicators
                {where_sql}
                ORDER BY display_order, indicator_name
                """
            ),
            params,
        ).mappings().all()
        return {"items": [self._indicator_item(row) for row in rows], "category_counts": self.get_category_counts()}

    def get_indicator(self, indicator_code: str) -> dict[str, Any]:
        row = self.db.execute(
            text("SELECT * FROM market_indicators WHERE indicator_code = :indicator_code"),
            {"indicator_code": indicator_code.strip().upper()},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market indicator not found")
        return self._indicator_item(row)

    def get_indicator_values(self, indicator_code: str, *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        indicator = self.get_indicator(indicator_code)
        clauses = ["indicator_code = :indicator_code"]
        params: dict[str, Any] = {"indicator_code": indicator["indicator_code"]}
        if start_date:
            clauses.append("value_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            clauses.append("value_date <= :end_date")
            params["end_date"] = end_date
        rows = self.db.execute(
            text(
                f"""
                SELECT *
                FROM market_indicator_values
                WHERE {' AND '.join(clauses)}
                ORDER BY value_date
                """
            ),
            params,
        ).mappings().all()
        return {"indicator_code": indicator["indicator_code"], "indicator_name": indicator["indicator_name"], "items": [self._value_item(row) for row in rows]}

    def list_provider_mappings(self) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                SELECT m.*, i.indicator_name
                FROM market_indicator_provider_mappings m
                LEFT JOIN market_indicators i ON i.indicator_code = m.indicator_code
                ORDER BY i.display_order, m.provider
                """
            )
        ).mappings().all()
        return {"items": [self._mapping_item(row) for row in rows]}

    def collect_indicator(self, indicator_codes: list[str] | None = None) -> dict[str, Any]:
        if indicator_codes:
            targets = [code.strip().upper() for code in indicator_codes if code.strip()]
        else:
            rows = self.db.execute(text("SELECT indicator_code FROM market_indicators WHERE is_active = 1 ORDER BY display_order")).mappings().all()
            targets = [str(row["indicator_code"]) for row in rows]
        results = [
            {
                "indicator_code": code,
                "status": "WAITING",
                "message": "provider mapping ?? ??",
            }
            for code in targets
        ]
        return {
            "requested_count": len(results),
            "success_count": 0,
            "waiting_count": len(results),
            "failed_count": 0,
            "message": "?? ???? ??? 59-B/59-C?? provider mapping ?? ? ??????.",
            "results": results,
        }

    def _indicator_item(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["is_active"] = self._as_bool(item.get("is_active"))
        return item

    def _value_item(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["is_preliminary"] = self._as_bool(item.get("is_preliminary"))
        item.pop("raw_payload_json", None)
        item.pop("created_at", None)
        item.pop("updated_at", None)
        return item

    def _mapping_item(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["is_enabled"] = self._as_bool(item.get("is_enabled"))
        item["is_verified"] = self._as_bool(item.get("is_verified"))
        return item
