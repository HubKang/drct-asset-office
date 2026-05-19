from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.schemas.market_trend_schema import (
    AssignThemeToTrendEventRequest,
    CollectMarketTrendEventsResponse,
    DailyThemeFlowItem,
    DailyThemeFlowResponse,
    MarketTrendEventResponse,
    TrendDetectionSettingResponse,
    TrendDetectionSettingUpdateRequest,
)

KRW_100M = 100_000_000
ALLOWED_MARKET_SCOPE = {"ALL", "KOSPI", "KOSDAQ"}
ALLOWED_THEME_STATUS = {
    "unassigned",
    "manual_assigned",
    "ai_suggested",
    "auto_assigned_pending_review",
    "user_corrected",
}


class MarketTrendService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _validate_market_scope(value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ALLOWED_MARKET_SCOPE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid market_scope")
        return normalized

    @staticmethod
    def _to_krw_100m(value: int | None) -> float | None:
        if value is None:
            return None
        return round(value / KRW_100M, 4)

    def _get_active_setting_row(self) -> dict:
        row = self.db.execute(
            text(
                """
                SELECT *
                FROM trend_detection_settings
                WHERE is_active = 1
                ORDER BY is_default DESC, updated_at DESC, id DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="active trend detection setting not found")
        return dict(row)

    def get_detection_settings(self) -> TrendDetectionSettingResponse:
        row = self._get_active_setting_row()
        return TrendDetectionSettingResponse(
            id=int(row["id"]),
            setting_key=str(row["setting_key"]),
            setting_name=str(row["setting_name"]),
            min_market_cap=int(row["min_market_cap"]),
            min_market_cap_krw_100m=self._to_krw_100m(int(row["min_market_cap"])) or 0.0,
            min_trading_value=int(row["min_trading_value"]),
            min_trading_value_krw_100m=self._to_krw_100m(int(row["min_trading_value"])) or 0.0,
            min_change_rate=float(row["min_change_rate"]),
            min_intraday_range_rate=(
                float(row["min_intraday_range_rate"]) if row["min_intraday_range_rate"] is not None else None
            ),
            use_intraday_range=bool(row["use_intraday_range"]),
            market_scope=str(row["market_scope"]),
            is_active=bool(row["is_active"]),
        )

    def update_detection_settings(self, payload: TrendDetectionSettingUpdateRequest) -> TrendDetectionSettingResponse:
        market_scope = self._validate_market_scope(payload.market_scope)
        row = self._get_active_setting_row()
        now = now_kst()
        min_market_cap = int(round(payload.min_market_cap_krw_100m * KRW_100M))
        min_trading_value = int(round(payload.min_trading_value_krw_100m * KRW_100M))

        self.db.execute(
            text(
                """
                UPDATE trend_detection_settings
                SET min_market_cap = :min_market_cap,
                    min_trading_value = :min_trading_value,
                    min_change_rate = :min_change_rate,
                    min_intraday_range_rate = :min_intraday_range_rate,
                    use_intraday_range = :use_intraday_range,
                    market_scope = :market_scope,
                    is_active = :is_active,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "min_market_cap": min_market_cap,
                "min_trading_value": min_trading_value,
                "min_change_rate": float(payload.min_change_rate),
                "min_intraday_range_rate": payload.min_intraday_range_rate,
                "use_intraday_range": 1 if payload.use_intraday_range else 0,
                "market_scope": market_scope,
                "is_active": 1 if payload.is_active else 0,
                "updated_at": now,
                "id": int(row["id"]),
            },
        )
        self.db.commit()
        return self.get_detection_settings()

    def collect_events(self, trade_date: str | None) -> CollectMarketTrendEventsResponse:
        setting = self._get_active_setting_row()
        base_trade_date = trade_date
        if not base_trade_date:
            base_trade_date = self.db.execute(text("SELECT MAX(trade_date) AS trade_date FROM stock_daily_prices")).scalar_one()
        if not base_trade_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade_date not found")

        market_scope = str(setting["market_scope"]).upper()
        conditions = [
            "p.trade_date = :trade_date",
            "COALESCE(m.market_cap, 0) >= :min_market_cap",
            "COALESCE(m.trading_value, p.trading_value, 0) >= :min_trading_value",
            "COALESCE(p.change_rate, 0) >= :min_change_rate",
        ]
        if bool(setting["use_intraday_range"]):
            conditions.append("COALESCE(p.intraday_range_rate, 0) >= :min_intraday_range_rate")
        if market_scope != "ALL":
            conditions.append("UPPER(COALESCE(m.market, s.market, '')) = :market_scope")

        query = f"""
            WITH price_rows AS (
                SELECT
                    p.stock_id,
                    p.trade_date,
                    p.change_rate,
                    p.trading_value AS price_trading_value,
                    CASE
                        WHEN p.low_price IS NOT NULL AND p.high_price IS NOT NULL AND p.close_price IS NOT NULL AND p.close_price != 0
                        THEN ((p.high_price - p.low_price) / p.close_price) * 100.0
                        ELSE NULL
                    END AS intraday_range_rate
                FROM stock_daily_prices p
                WHERE p.trade_date = :trade_date
            ),
            metric_rows AS (
                SELECT
                    stock_id,
                    trade_date,
                    MAX(market_cap) AS market_cap,
                    MAX(trading_value) AS trading_value,
                    MAX(market) AS market
                FROM stock_daily_market_metrics
                WHERE trade_date = :trade_date
                GROUP BY stock_id, trade_date
            )
            SELECT
                p.trade_date,
                s.id AS stock_id,
                s.stock_code,
                s.stock_name,
                COALESCE(m.market, s.market) AS market_type,
                m.market_cap AS market_cap,
                COALESCE(m.trading_value, p.price_trading_value) AS trading_value,
                p.change_rate,
                p.intraday_range_rate
            FROM price_rows p
            JOIN stocks s ON s.id = p.stock_id
            LEFT JOIN metric_rows m ON m.stock_id = p.stock_id AND m.trade_date = p.trade_date
            WHERE {" AND ".join(conditions)}
            ORDER BY COALESCE(m.trading_value, p.price_trading_value, 0) DESC, p.change_rate DESC, s.stock_name ASC
        """

        params = {
            "trade_date": base_trade_date,
            "min_market_cap": int(setting["min_market_cap"]),
            "min_trading_value": int(setting["min_trading_value"]),
            "min_change_rate": float(setting["min_change_rate"]),
            "min_intraday_range_rate": (
                float(setting["min_intraday_range_rate"]) if setting["min_intraday_range_rate"] is not None else 0.0
            ),
            "market_scope": market_scope,
        }
        rows = [dict(row) for row in self.db.execute(text(query), params).mappings().all()]
        now = now_kst()
        inserted_count = 0

        for row in rows:
            result = self.db.execute(
                text(
                    """
                    INSERT INTO market_trend_events (
                        trade_date, stock_id, stock_code, stock_name, market_type,
                        market_cap, trading_value, change_rate, intraday_range_rate, event_type,
                        detection_setting_id, applied_min_market_cap, applied_min_trading_value, applied_min_change_rate,
                        applied_min_intraday_range_rate, applied_use_intraday_range,
                        theme_id, theme_status, primary_theme_id, reason_summary, user_memo, is_active, created_at, updated_at
                    )
                    VALUES (
                        :trade_date, :stock_id, :stock_code, :stock_name, :market_type,
                        :market_cap, :trading_value, :change_rate, :intraday_range_rate, 'supply_surge',
                        :detection_setting_id, :applied_min_market_cap, :applied_min_trading_value, :applied_min_change_rate,
                        :applied_min_intraday_range_rate, :applied_use_intraday_range,
                        NULL, 'unassigned', NULL, NULL, NULL, 1, :created_at, :updated_at
                    )
                    ON CONFLICT(trade_date, stock_id, event_type) DO NOTHING
                    """
                ),
                {
                    "trade_date": row["trade_date"],
                    "stock_id": row["stock_id"],
                    "stock_code": row["stock_code"],
                    "stock_name": row["stock_name"],
                    "market_type": row["market_type"],
                    "market_cap": row["market_cap"],
                    "trading_value": row["trading_value"],
                    "change_rate": row["change_rate"],
                    "intraday_range_rate": row["intraday_range_rate"],
                    "detection_setting_id": int(setting["id"]),
                    "applied_min_market_cap": int(setting["min_market_cap"]),
                    "applied_min_trading_value": int(setting["min_trading_value"]),
                    "applied_min_change_rate": float(setting["min_change_rate"]),
                    "applied_min_intraday_range_rate": setting["min_intraday_range_rate"],
                    "applied_use_intraday_range": int(setting["use_intraday_range"]),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            if result.rowcount and result.rowcount > 0:
                inserted_count += 1

        self.db.commit()
        collected_count = len(rows)
        duplicated_count = max(0, collected_count - inserted_count)
        return CollectMarketTrendEventsResponse(
            trade_date=str(base_trade_date),
            applied_condition={
                "min_market_cap_krw_100m": self._to_krw_100m(int(setting["min_market_cap"])) or 0.0,
                "min_trading_value_krw_100m": self._to_krw_100m(int(setting["min_trading_value"])) or 0.0,
                "min_change_rate": float(setting["min_change_rate"]),
                "use_intraday_range": bool(setting["use_intraday_range"]),
                "min_intraday_range_rate": (
                    float(setting["min_intraday_range_rate"]) if setting["min_intraday_range_rate"] is not None else None
                ),
                "market_scope": market_scope,
            },
            collected_count=collected_count,
            inserted_count=inserted_count,
            duplicated_count=duplicated_count,
            message="수급 이벤트 종목 수집이 완료되었습니다.",
        )

    def list_events(
        self,
        *,
        trade_date: str | None,
        theme_status: str | None,
        theme_id: int | None,
        market_scope: str | None,
        limit: int,
        offset: int,
    ) -> list[MarketTrendEventResponse]:
        conditions = ["e.is_active = 1"]
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if trade_date:
            conditions.append("e.trade_date = :trade_date")
            params["trade_date"] = trade_date
        if theme_status:
            if theme_status not in ALLOWED_THEME_STATUS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid theme_status")
            conditions.append("e.theme_status = :theme_status")
            params["theme_status"] = theme_status
        if theme_id is not None:
            conditions.append("e.theme_id = :theme_id")
            params["theme_id"] = theme_id
        if market_scope:
            scope = self._validate_market_scope(market_scope)
            if scope != "ALL":
                conditions.append("UPPER(COALESCE(e.market_type, '')) = :market_scope")
                params["market_scope"] = scope

        query = f"""
            SELECT
                e.id AS event_id,
                e.trade_date,
                e.stock_id,
                e.stock_code,
                e.stock_name,
                e.market_type,
                e.market_cap,
                e.trading_value,
                e.change_rate,
                e.intraday_range_rate,
                e.theme_id,
                t.theme_name,
                e.theme_status,
                e.reason_summary,
                e.user_memo,
                e.applied_min_market_cap,
                e.applied_min_trading_value,
                e.applied_min_change_rate,
                e.applied_min_intraday_range_rate,
                e.applied_use_intraday_range
            FROM market_trend_events e
            LEFT JOIN market_themes t ON t.id = e.theme_id
            WHERE {" AND ".join(conditions)}
            ORDER BY e.trade_date DESC, COALESCE(e.trading_value, 0) DESC, e.stock_name ASC
            LIMIT :limit OFFSET :offset
        """
        rows = self.db.execute(text(query), params).mappings().all()
        return [
            MarketTrendEventResponse(
                event_id=int(row["event_id"]),
                trade_date=str(row["trade_date"]),
                stock_id=int(row["stock_id"]),
                stock_code=row["stock_code"],
                stock_name=row["stock_name"],
                market_type=row["market_type"],
                market_cap=row["market_cap"],
                trading_value=row["trading_value"],
                change_rate=row["change_rate"],
                intraday_range_rate=row["intraday_range_rate"],
                theme_id=row["theme_id"],
                theme_name=row["theme_name"],
                theme_status=str(row["theme_status"]),
                reason_summary=row["reason_summary"],
                user_memo=row["user_memo"],
                applied_condition={
                    "min_market_cap_krw_100m": self._to_krw_100m(row["applied_min_market_cap"]),
                    "min_trading_value_krw_100m": self._to_krw_100m(row["applied_min_trading_value"]),
                    "min_change_rate": row["applied_min_change_rate"],
                    "min_intraday_range_rate": row["applied_min_intraday_range_rate"],
                    "use_intraday_range": bool(row["applied_use_intraday_range"]),
                },
            )
            for row in rows
        ]

    def assign_event_theme(self, event_id: int, payload: AssignThemeToTrendEventRequest) -> MarketTrendEventResponse:
        event = self.db.execute(
            text("SELECT id, stock_id FROM market_trend_events WHERE id = :id AND is_active = 1"),
            {"id": event_id},
        ).mappings().first()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market trend event not found")
        theme = self.db.execute(
            text("SELECT id FROM market_themes WHERE id = :id"),
            {"id": payload.theme_id},
        ).mappings().first()
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")

        now = now_kst()
        self.db.execute(
            text(
                """
                UPDATE market_trend_events
                SET theme_id = :theme_id,
                    primary_theme_id = :theme_id, -- TODO: 확장 시 이벤트-다중테마 매핑 테이블로 분리 고려
                    theme_status = 'manual_assigned',
                    reason_summary = :reason_summary,
                    user_memo = :user_memo,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "theme_id": payload.theme_id,
                "reason_summary": payload.reason_summary,
                "user_memo": payload.user_memo,
                "updated_at": now,
                "id": event_id,
            },
        )

        if payload.also_add_to_theme_stocks:
            self.db.execute(
                text(
                    """
                    INSERT INTO market_theme_stocks (
                        theme_id, stock_id, mapping_source, confidence_score, is_primary, is_active, created_at, updated_at
                    )
                    VALUES (:theme_id, :stock_id, 'manual', 1.0, :is_primary, 1, :now, :now)
                    ON CONFLICT(theme_id, stock_id)
                    DO UPDATE SET
                        is_active = 1,
                        is_primary = excluded.is_primary,
                        updated_at = excluded.updated_at
                    """
                ),
                {
                    "theme_id": payload.theme_id,
                    "stock_id": int(event["stock_id"]),
                    "is_primary": 1 if payload.is_primary_for_theme else 0,
                    "now": now,
                },
            )

        self.db.commit()
        updated = self.db.execute(
            text(
                """
                SELECT
                    e.id AS event_id,
                    e.trade_date,
                    e.stock_id,
                    e.stock_code,
                    e.stock_name,
                    e.market_type,
                    e.market_cap,
                    e.trading_value,
                    e.change_rate,
                    e.intraday_range_rate,
                    e.theme_id,
                    t.theme_name,
                    e.theme_status,
                    e.reason_summary,
                    e.user_memo,
                    e.applied_min_market_cap,
                    e.applied_min_trading_value,
                    e.applied_min_change_rate,
                    e.applied_min_intraday_range_rate,
                    e.applied_use_intraday_range
                FROM market_trend_events e
                LEFT JOIN market_themes t ON t.id = e.theme_id
                WHERE e.id = :event_id
                """
            ),
            {"event_id": event_id},
        ).mappings().first()
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market trend event not found")
        row = updated
        return MarketTrendEventResponse(
            event_id=int(row["event_id"]),
            trade_date=str(row["trade_date"]),
            stock_id=int(row["stock_id"]),
            stock_code=row["stock_code"],
            stock_name=row["stock_name"],
            market_type=row["market_type"],
            market_cap=row["market_cap"],
            trading_value=row["trading_value"],
            change_rate=row["change_rate"],
            intraday_range_rate=row["intraday_range_rate"],
            theme_id=row["theme_id"],
            theme_name=row["theme_name"],
            theme_status=str(row["theme_status"]),
            reason_summary=row["reason_summary"],
            user_memo=row["user_memo"],
            applied_condition={
                "min_market_cap_krw_100m": self._to_krw_100m(row["applied_min_market_cap"]),
                "min_trading_value_krw_100m": self._to_krw_100m(row["applied_min_trading_value"]),
                "min_change_rate": row["applied_min_change_rate"],
                "min_intraday_range_rate": row["applied_min_intraday_range_rate"],
                "use_intraday_range": bool(row["applied_use_intraday_range"]),
            },
        )

    def get_daily_theme_flow(
        self,
        *,
        trade_date: str | None,
        only_supply_theme: bool,
        market_scope: str | None,
    ) -> DailyThemeFlowResponse:
        base_trade_date = trade_date
        if not base_trade_date:
            base_trade_date = self.db.execute(text("SELECT MAX(trade_date) FROM market_trend_events")).scalar_one()
        if not base_trade_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade_date not found")

        filter_clause = ["e.trade_date = :trade_date", "e.is_active = 1"]
        params: dict[str, object] = {"trade_date": base_trade_date}
        if only_supply_theme:
            filter_clause.append("COALESCE(t.is_supply_theme, 0) = 1")
        if market_scope:
            scope = self._validate_market_scope(market_scope)
            if scope != "ALL":
                filter_clause.append("UPPER(COALESCE(e.market_type, '')) = :market_scope")
                params["market_scope"] = scope

        summary = self.db.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS event_count,
                    SUM(CASE WHEN e.theme_id IS NOT NULL THEN 1 ELSE 0 END) AS assigned_count,
                    SUM(CASE WHEN e.theme_id IS NULL THEN 1 ELSE 0 END) AS unassigned_count
                FROM market_trend_events e
                LEFT JOIN market_themes t ON t.id = e.theme_id
                WHERE {" AND ".join(filter_clause)}
                """
            ),
            params,
        ).mappings().first()
        if not summary:
            summary = {"event_count": 0, "assigned_count": 0, "unassigned_count": 0}

        grouped = self.db.execute(
            text(
                f"""
                SELECT
                    e.theme_id,
                    t.theme_name,
                    COALESCE(t.is_supply_theme, 0) AS is_supply_theme,
                    COUNT(*) AS detected_stock_count,
                    CAST(SUM(COALESCE(e.trading_value, 0)) AS INTEGER) AS total_trading_value,
                    AVG(e.change_rate) AS avg_change_rate,
                    MAX(e.change_rate) AS max_change_rate
                FROM market_trend_events e
                JOIN market_themes t ON t.id = e.theme_id
                WHERE {" AND ".join(filter_clause)} AND e.theme_id IS NOT NULL
                GROUP BY e.theme_id, t.theme_name, t.is_supply_theme
                ORDER BY total_trading_value DESC, detected_stock_count DESC, avg_change_rate DESC
                """
            ),
            params,
        ).mappings().all()

        items: list[DailyThemeFlowItem] = []
        for idx, row in enumerate(grouped, start=1):
            top_change_name = self.db.execute(
                text(
                    """
                    SELECT stock_name
                    FROM market_trend_events
                    WHERE trade_date = :trade_date AND is_active = 1 AND theme_id = :theme_id
                    ORDER BY change_rate DESC, stock_name ASC
                    LIMIT 1
                    """
                ),
                {"trade_date": base_trade_date, "theme_id": row["theme_id"]},
            ).scalar_one_or_none()
            top_value_name = self.db.execute(
                text(
                    """
                    SELECT stock_name
                    FROM market_trend_events
                    WHERE trade_date = :trade_date AND is_active = 1 AND theme_id = :theme_id
                    ORDER BY COALESCE(trading_value, 0) DESC, stock_name ASC
                    LIMIT 1
                    """
                ),
                {"trade_date": base_trade_date, "theme_id": row["theme_id"]},
            ).scalar_one_or_none()
            total_value = int(row["total_trading_value"] or 0)
            items.append(
                DailyThemeFlowItem(
                    theme_id=int(row["theme_id"]),
                    theme_name=str(row["theme_name"]),
                    is_supply_theme=bool(row["is_supply_theme"]),
                    detected_stock_count=int(row["detected_stock_count"]),
                    total_trading_value=total_value,
                    total_trading_value_krw_100m=round(total_value / KRW_100M, 4),
                    avg_change_rate=(round(float(row["avg_change_rate"]), 4) if row["avg_change_rate"] is not None else None),
                    max_change_rate=(round(float(row["max_change_rate"]), 4) if row["max_change_rate"] is not None else None),
                    top_change_stock_name=top_change_name,
                    top_trading_value_stock_name=top_value_name,
                    trend_rank=idx,
                )
            )

        return DailyThemeFlowResponse(
            trade_date=str(base_trade_date),
            description=(
                "본 집계는 사용자가 부여한 테마 기준의 내부 참고 지표입니다. "
                "공식 업종/테마 분류가 아니며, 최종 투자 판단은 사용자가 수행합니다."
            ),
            summary={
                "event_count": int(summary.get("event_count") or 0),
                "assigned_count": int(summary.get("assigned_count") or 0),
                "unassigned_count": int(summary.get("unassigned_count") or 0),
            },
            items=items,
        )
