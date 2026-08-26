from __future__ import annotations

import calendar
from datetime import date, datetime
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.schemas.market_calendar_schema import (
    MarketCalendarDailyResponse,
    MarketCalendarEventCreateRequest,
    MarketCalendarEventResponse,
    MarketCalendarEventUpdateRequest,
    MarketCalendarMonthlyResponse,
    MarketCalendarStockResponse,
)

ALLOWED_EVENT_TYPES = {"news", "policy", "issue", "earnings", "disclosure", "supply", "other"}
ALLOWED_IMPORTANCE = {"high", "medium", "low"}


class MarketCalendarService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _parse_date(value: str, field_name: str) -> date:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} 형식은 YYYY-MM-DD여야 합니다.") from exc

    @staticmethod
    def _normalize_text(value: str | None) -> str | None:
        text_value = (value or "").strip()
        return text_value or None

    def _normalize_payload(self, payload: MarketCalendarEventCreateRequest | MarketCalendarEventUpdateRequest) -> dict[str, object]:
        start_date = self._parse_date(payload.start_date, "start_date")
        end_date = self._parse_date(payload.end_date, "end_date")
        period_type = payload.period_type
        if period_type == "M":
            start_date = start_date.replace(day=1)
            end_date = end_date.replace(day=calendar.monthrange(end_date.year, end_date.month)[1])
        if end_date < start_date:
            unit = "종료월" if period_type == "M" else "종료일"
            start_unit = "시작월" if period_type == "M" else "시작일"
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{unit}은 {start_unit}보다 빠를 수 없습니다.")

        event_type = (payload.event_type or "news").strip()
        importance = (payload.importance or "medium").strip()
        if event_type not in ALLOWED_EVENT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 이벤트 유형입니다.")
        if importance not in ALLOWED_IMPORTANCE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 중요도입니다.")

        news_url = self._normalize_text(payload.news_url)
        if news_url:
            parsed = urlparse(news_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="뉴스 URL 형식이 올바르지 않습니다.")

        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="뉴스명을 입력해 주세요.")

        if payload.theme_id is not None:
            self._get_theme(payload.theme_id)
        return {
            "period_type": period_type,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "theme_id": int(payload.theme_id) if payload.theme_id is not None else None,
            "title": title,
            "summary": self._normalize_text(payload.summary),
            "news_url": news_url,
            "event_type": event_type,
            "importance": importance,
            "memo": self._normalize_text(payload.memo),
            "stock_ids": list(dict.fromkeys([int(stock_id) for stock_id in payload.stock_ids if int(stock_id) > 0])),
        }

    def _get_theme(self, theme_id: int) -> dict[str, object]:
        row = self.db.execute(
            text(
                """
                SELECT id, theme_name, theme_level, is_active
                FROM market_themes
                WHERE id = :theme_id
                """
            ),
            {"theme_id": theme_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="테마를 찾을 수 없습니다.")
        if int(row["is_active"] or 0) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비활성 테마는 선택할 수 없습니다.")
        if str(row["theme_level"] or "THEME") != "THEME":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="테마그룹이 아닌 테마를 선택해 주세요.")
        return dict(row)

    def _list_stock_rows(self, stock_ids: list[int]) -> list[dict[str, object]]:
        if not stock_ids:
            return []
        placeholders = ", ".join([f":stock_id_{index}" for index, _ in enumerate(stock_ids)])
        params = {f"stock_id_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        rows = self.db.execute(
            text(
                f"""
                SELECT id, stock_code, stock_name
                FROM stocks
                WHERE is_active = 1 AND id IN ({placeholders})
                ORDER BY stock_name
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def _replace_stocks(self, event_id: int, stock_ids: list[int]) -> None:
        self.db.execute(text("DELETE FROM market_calendar_event_stocks WHERE event_id = :event_id"), {"event_id": event_id})
        rows = self._list_stock_rows(stock_ids)
        now = now_kst()
        for row in rows:
            self.db.execute(
                text(
                    """
                    INSERT INTO market_calendar_event_stocks
                    (event_id, stock_id, stock_code, stock_name, created_at)
                    VALUES (:event_id, :stock_id, :stock_code, :stock_name, :created_at)
                    """
                ),
                {
                    "event_id": event_id,
                    "stock_id": int(row["id"]),
                    "stock_code": row["stock_code"],
                    "stock_name": row["stock_name"],
                    "created_at": now,
                },
            )

    def _stocks_by_event(self, event_ids: list[int]) -> dict[int, list[MarketCalendarStockResponse]]:
        if not event_ids:
            return {}
        placeholders = ", ".join([f":event_id_{index}" for index, _ in enumerate(event_ids)])
        params = {f"event_id_{index}": event_id for index, event_id in enumerate(event_ids)}
        rows = self.db.execute(
            text(
                f"""
                SELECT event_id, stock_id, stock_code, stock_name
                FROM market_calendar_event_stocks
                WHERE event_id IN ({placeholders})
                ORDER BY stock_name
                """
            ),
            params,
        ).mappings().all()
        grouped: dict[int, list[MarketCalendarStockResponse]] = {}
        for row in rows:
            event_id = int(row["event_id"])
            grouped.setdefault(event_id, []).append(
                MarketCalendarStockResponse(
                    stock_id=int(row["stock_id"]),
                    stock_code=row["stock_code"],
                    stock_name=row["stock_name"],
                )
            )
        return grouped

    @staticmethod
    def _to_response(row: dict[str, object], stocks: list[MarketCalendarStockResponse]) -> MarketCalendarEventResponse:
        return MarketCalendarEventResponse(
            id=int(row["id"]),
            period_type="M" if str(row.get("period_type") or "D").upper() == "M" else "D",
            start_date=str(row["start_date"]),
            end_date=str(row["end_date"]),
            theme_id=int(row["theme_id"]) if row.get("theme_id") is not None else None,
            theme_name=str(row["theme_name"]) if row.get("theme_name") is not None else None,
            theme_group_id=int(row["theme_group_id"]) if row.get("theme_group_id") is not None else None,
            theme_group_name=str(row["theme_group_name"]) if row.get("theme_group_name") is not None else None,
            title=str(row["title"]),
            summary=str(row["summary"]) if row.get("summary") is not None else None,
            news_url=str(row["news_url"]) if row.get("news_url") is not None else None,
            event_type=str(row["event_type"]),
            importance=str(row["importance"]),
            memo=str(row["memo"]) if row.get("memo") is not None else None,
            is_active=int(row["is_active"]),
            stocks=stocks,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _event_query_rows(
        self,
        *,
        start_date: str,
        end_date: str,
        theme_group_id: int | None = None,
        theme_id: int | None = None,
        keyword: str | None = None,
        event_type: str | None = None,
        event_id: int | None = None,
    ) -> list[dict[str, object]]:
        clauses = ["e.is_active = 1", "e.start_date <= :end_date", "e.end_date >= :start_date"]
        params: dict[str, object] = {"start_date": start_date, "end_date": end_date}
        if event_id is not None:
            clauses.append("e.id = :event_id")
            params["event_id"] = event_id
        if theme_group_id:
            clauses.append("t.parent_theme_id = :theme_group_id")
            params["theme_group_id"] = theme_group_id
        if theme_id:
            clauses.append("e.theme_id = :theme_id")
            params["theme_id"] = theme_id
        if event_type:
            clauses.append("e.event_type = :event_type")
            params["event_type"] = event_type
        if keyword:
            clauses.append("(e.title LIKE :keyword OR e.summary LIKE :keyword OR e.memo LIKE :keyword OR t.theme_name LIKE :keyword OR g.theme_name LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        where_sql = " AND ".join(clauses)
        rows = self.db.execute(
            text(
                f"""
                SELECT e.id, e.period_type, e.start_date, e.end_date, e.theme_id, e.title, e.summary, e.news_url,
                       e.event_type, e.importance, e.memo, e.is_active, e.created_at, e.updated_at,
                       t.theme_name, t.parent_theme_id AS theme_group_id, g.theme_name AS theme_group_name
                FROM market_calendar_events e
                LEFT JOIN market_themes t ON t.id = e.theme_id
                LEFT JOIN market_themes g ON g.id = t.parent_theme_id
                WHERE {where_sql}
                ORDER BY e.start_date ASC, e.importance ASC, e.id ASC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def _list_events(
        self,
        *,
        start_date: str,
        end_date: str,
        theme_group_id: int | None = None,
        theme_id: int | None = None,
        keyword: str | None = None,
        event_type: str | None = None,
    ) -> list[MarketCalendarEventResponse]:
        event_rows = self._event_query_rows(
            start_date=start_date,
            end_date=end_date,
            theme_group_id=theme_group_id,
            theme_id=theme_id,
            keyword=keyword,
            event_type=event_type,
        )
        stocks_by_event = self._stocks_by_event([int(row["id"]) for row in event_rows])
        return [self._to_response(row, stocks_by_event.get(int(row["id"]), [])) for row in event_rows]

    def list_monthly(
        self,
        *,
        month: str,
        theme_group_id: int | None = None,
        theme_id: int | None = None,
        keyword: str | None = None,
        event_type: str | None = None,
    ) -> MarketCalendarMonthlyResponse:
        try:
            year, month_number = [int(part) for part in month.split("-", 1)]
            last_day = calendar.monthrange(year, month_number)[1]
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month 형식은 YYYY-MM이어야 합니다.") from exc
        start_date = date(year, month_number, 1).isoformat()
        end_date = date(year, month_number, last_day).isoformat()
        return MarketCalendarMonthlyResponse(
            month=month,
            start_date=start_date,
            end_date=end_date,
            events=self._list_events(
                start_date=start_date,
                end_date=end_date,
                theme_group_id=theme_group_id,
                theme_id=theme_id,
                keyword=keyword,
                event_type=event_type,
            ),
        )

    def list_daily(self, selected_date: str) -> MarketCalendarDailyResponse:
        parsed = self._parse_date(selected_date, "date").isoformat()
        events = self._list_events(start_date=parsed, end_date=parsed)
        return MarketCalendarDailyResponse(date=parsed, events=[event for event in events if event.period_type == "D"])

    def create_event(self, payload: MarketCalendarEventCreateRequest) -> MarketCalendarEventResponse:
        data = self._normalize_payload(payload)
        stock_ids = data.pop("stock_ids")
        now = now_kst()
        result = self.db.execute(
            text(
                """
                INSERT INTO market_calendar_events
                (period_type, start_date, end_date, theme_id, title, summary, news_url, event_type, importance, memo, is_active, created_at, updated_at)
                VALUES (:period_type, :start_date, :end_date, :theme_id, :title, :summary, :news_url, :event_type, :importance, :memo, 1, :created_at, :updated_at)
                """
            ),
            {**data, "created_at": now, "updated_at": now},
        )
        event_id = int(result.lastrowid)
        self._replace_stocks(event_id, stock_ids)  # type: ignore[arg-type]
        self.db.commit()
        return self.get_event(event_id)

    def update_event(self, event_id: int, payload: MarketCalendarEventUpdateRequest) -> MarketCalendarEventResponse:
        self.get_event(event_id)
        data = self._normalize_payload(payload)
        stock_ids = data.pop("stock_ids")
        now = now_kst()
        self.db.execute(
            text(
                """
                UPDATE market_calendar_events
                SET period_type = :period_type,
                    start_date = :start_date,
                    end_date = :end_date,
                    theme_id = :theme_id,
                    title = :title,
                    summary = :summary,
                    news_url = :news_url,
                    event_type = :event_type,
                    importance = :importance,
                    memo = :memo,
                    updated_at = :updated_at
                WHERE id = :event_id AND is_active = 1
                """
            ),
            {**data, "event_id": event_id, "updated_at": now},
        )
        self._replace_stocks(event_id, stock_ids)  # type: ignore[arg-type]
        self.db.commit()
        return self.get_event(event_id)

    def delete_event(self, event_id: int) -> dict[str, object]:
        self.get_event(event_id)
        self.db.execute(
            text("UPDATE market_calendar_events SET is_active = 0, updated_at = :updated_at WHERE id = :event_id"),
            {"event_id": event_id, "updated_at": now_kst()},
        )
        self.db.commit()
        return {"success": True, "event_id": event_id}

    def get_event(self, event_id: int) -> MarketCalendarEventResponse:
        event_rows = self._event_query_rows(start_date="0000-01-01", end_date="9999-12-31", event_id=event_id)
        if not event_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="캘린더 이벤트를 찾을 수 없습니다.")
        stocks_by_event = self._stocks_by_event([event_id])
        return self._to_response(event_rows[0], stocks_by_event.get(event_id, []))
