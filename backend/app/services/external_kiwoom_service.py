from __future__ import annotations

import math
import time
from collections import defaultdict
from calendar import monthrange
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.clients.kiwoom import KiwoomApiError
from backend.app.clients.kiwoom.kiwoom_auth_client import KiwoomAuthClient
from backend.app.clients.kiwoom.kiwoom_rest_client import KiwoomRestClient
from backend.app.core.config import now_kst
from backend.app.providers.market_data.kiwoom_rest_condition_provider import KiwoomRestConditionProvider
from backend.app.providers.market_data.kiwoom_rest_market_indicator_provider import KiwoomRestMarketIndicatorProvider
from backend.app.schemas.external_kiwoom_schema import (
    DailyThemeFlowStockItem,
    DailyThemeRanksUpdateRequest,
    DailyThemeRanksUpdateResponse,
    DailyThemeFlowStocksResponse,
    DailyThemeFlowSummaryItem,
    DailyThemeFlowSummaryResponse,
    MarketThemeLatestReturnResponse,
    MarketThemeMonthlyReturnDailyItem,
    MarketThemeMonthlyReturnResponse,
    MarketThemeMonthlyReturnSummary,
    MarketThemeMonthlyReturnSummaryTopItem,
    MarketThemeMonthlyReturnThemeItem,
    MarketThemeReturnRefreshItem,
    MarketThemeReturnRefreshRequest,
    MarketThemeReturnRefreshResponse,
    MarketThemeReturnStockItem,
    MonthlyThemeFlowCalendarDayItem,
    MonthlyThemeFlowMemoItem,
    MonthlyThemeFlowCalendarResponse,
    MonthlyThemeFlowStockItem,
    MonthlyThemeFlowCalendarThemeItem,
    MonthlyThemeFlowTrendPoint,
    MonthlyThemeFlowTrendResponse,
    MonthlyThemeFlowTrendTheme,
    KiwoomConditionListResponse,
    KiwoomConditionResultListResponse,
    KiwoomConditionResultItemOut,
    KiwoomConditionPreviewRequest,
    KiwoomConditionPreviewResponse,
    KiwoomConditionResultSaveRequest,
    KiwoomConditionResultSaveResponse,
    KiwoomConditionSyncRequest,
    KiwoomConditionSyncResponse,
    KiwoomConditionRefreshResponse,
    KiwoomMarketEventDeleteResponse,
    KiwoomMarketEventItemOut,
    KiwoomMarketEventListResponse,
    KiwoomMarketEventPatchRequest,
    KiwoomMarketEventPatchResponse,
    KiwoomMarketEventThemeLinkAddRequest,
    KiwoomMarketEventThemeLinkAddResponse,
    KiwoomMarketEventThemeLinkDeleteResponse,
    KiwoomMarketEventThemeLinkItemOut,
    KiwoomMarketEventThemeLinkListResponse,
    ThemeStockSyncResult,
    ThemeStockSyncSummary,
    KiwoomMarketEventSaveRequest,
    KiwoomMarketEventSaveResponse,
)
from backend.app.utils.stock_code import normalize_stock_code


class ExternalKiwoomService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._condition_provider = KiwoomRestConditionProvider()

    def refresh_conditions_from_kiwoom(self, source: str = "kiwoom_rest") -> KiwoomConditionRefreshResponse:
        try:
            fetched = self._condition_provider.fetch_condition_list()
        except KiwoomApiError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Kiwoom 조건검색 목록을 가져오지 못했습니다. api_id=ka10171 return_code={exc.code} message={exc.message}",
            ) from exc
        conditions = fetched.get("conditions", [])
        condition_count = len(conditions) if isinstance(conditions, list) else 0
        return_code = fetched.get("return_code")
        return_msg = fetched.get("return_msg")
        top_level_keys = fetched.get("top_level_keys") if isinstance(fetched.get("top_level_keys"), list) else []
        if condition_count <= 0:
            return KiwoomConditionRefreshResponse(
                success=False,
                source=source,
                api_id="ka10171",
                return_code=str(return_code) if return_code is not None else None,
                return_msg=str(return_msg) if return_msg is not None else None,
                condition_count=0,
                inserted=0,
                updated=0,
                total=int(
                    self.db.execute(
                        text("SELECT COUNT(*) FROM kiwoom_condition_searches WHERE source=:source AND is_active=1"),
                        {"source": source},
                    ).scalar_one()
                    or 0
                ),
                top_level_keys=top_level_keys[:20],
                sample_conditions=[],
                message="조건검색 목록 응답은 받았지만 조건식 목록을 파싱하지 못했습니다.",
            )
        payload = KiwoomConditionSyncRequest(
            source=source,
            items=conditions,
        )
        sync = self.sync_conditions(payload)
        return KiwoomConditionRefreshResponse(
            success=True,
            source=source,
            api_id="ka10171",
            return_code=str(return_code) if return_code is not None else None,
            return_msg=str(return_msg) if return_msg is not None else None,
            condition_count=condition_count,
            inserted=sync.inserted_count,
            updated=sync.updated_count,
            total=sync.total_count,
            top_level_keys=top_level_keys[:20],
            sample_conditions=[
                {
                    "condition_no": str(x.get("condition_seq") or ""),
                    "condition_name": str(x.get("condition_name") or ""),
                }
                for x in conditions[:3]
                if isinstance(x, dict)
            ],
            message="조건검색 목록을 갱신했습니다.",
        )

    def sync_conditions(self, payload: KiwoomConditionSyncRequest) -> KiwoomConditionSyncResponse:
        now = now_kst()
        inserted_count = 0
        updated_count = 0

        for item in payload.items:
            seq = (item.condition_seq or "").strip()
            name = (item.condition_name or "").strip()
            if not seq or not name:
                continue
            existing = self.db.execute(
                text("SELECT id FROM kiwoom_condition_searches WHERE source=:source AND condition_seq=:seq"),
                {"source": payload.source, "seq": seq},
            ).mappings().first()
            if existing:
                self.db.execute(
                    text(
                        """
                        UPDATE kiwoom_condition_searches
                        SET condition_name=:condition_name, is_active=1, last_synced_at=:last_synced_at, updated_at=:updated_at
                        WHERE id=:id
                        """
                    ),
                    {
                        "id": int(existing["id"]),
                        "condition_name": name,
                        "last_synced_at": now,
                        "updated_at": now,
                    },
                )
                updated_count += 1
            else:
                self.db.execute(
                    text(
                        """
                        INSERT INTO kiwoom_condition_searches
                        (condition_seq, condition_name, source, is_active, last_synced_at, created_at, updated_at)
                        VALUES (:condition_seq, :condition_name, :source, 1, :last_synced_at, :created_at, :updated_at)
                        """
                    ),
                    {
                        "condition_seq": seq,
                        "condition_name": name,
                        "source": payload.source,
                        "last_synced_at": now,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                inserted_count += 1

        self.db.commit()
        total_count = int(
            self.db.execute(
                text("SELECT COUNT(*) FROM kiwoom_condition_searches WHERE source=:source AND is_active=1"),
                {"source": payload.source},
            ).scalar_one()
            or 0
        )
        return KiwoomConditionSyncResponse(
            success=True,
            inserted_count=inserted_count,
            updated_count=updated_count,
            total_count=total_count,
        )

    def list_conditions(self, source: str = "kiwoom_rest") -> KiwoomConditionListResponse:
        rows = self.db.execute(
            text(
                """
                SELECT id, condition_seq, condition_name, source, is_active, last_synced_at
                FROM kiwoom_condition_searches
                WHERE source=:source
                ORDER BY is_active DESC,
                         CASE WHEN condition_seq GLOB '[0-9]*' THEN CAST(condition_seq AS INTEGER) ELSE 2147483647 END ASC,
                         condition_seq ASC
                """
            ),
            {"source": source},
        ).mappings().all()
        return KiwoomConditionListResponse(items=[dict(r) for r in rows])

    def save_condition_results(self, condition_seq: str, payload: KiwoomConditionResultSaveRequest) -> KiwoomConditionResultSaveResponse:
        now = now_kst()
        cond = self.db.execute(
            text("SELECT id, condition_name FROM kiwoom_condition_searches WHERE source=:source AND condition_seq=:seq"),
            {"source": payload.source, "seq": condition_seq},
        ).mappings().first()
        condition_id = int(cond["id"]) if cond else None
        condition_name = payload.condition_name or (str(cond["condition_name"]) if cond else None)

        saved_count = 0
        skipped_count = 0
        for item in payload.items:
            code = normalize_stock_code(item.stock_code or item.stock_code_raw)
            if len(code) != 6:
                skipped_count += 1
                continue
            detected_at = item.detected_at or now
            detected_date = str(detected_at)[:10]
            existing = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM kiwoom_condition_result_items
                    WHERE condition_seq=:condition_seq
                      AND stock_code=:stock_code
                      AND substr(detected_at,1,10)=:detected_date
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"condition_seq": condition_seq, "stock_code": code, "detected_date": detected_date},
            ).mappings().first()
            if existing:
                self.db.execute(
                    text(
                        """
                        UPDATE kiwoom_condition_result_items
                        SET condition_id=:condition_id,
                            condition_name=:condition_name,
                            stock_code_raw=:stock_code_raw,
                            stock_name=:stock_name,
                            current_price=:current_price,
                            change_rate=:change_rate,
                            intraday_change_rate=:intraday_change_rate,
                            trading_value=:trading_value,
                            volume=:volume,
                            detected_at=:detected_at,
                            source=:source,
                            source_api=:source_api,
                            raw_json=NULL
                        WHERE id=:id
                        """
                    ),
                    {
                        "id": int(existing["id"]),
                        "condition_id": condition_id,
                        "condition_name": condition_name,
                        "stock_code_raw": item.stock_code_raw or item.stock_code,
                        "stock_name": item.stock_name,
                        "current_price": self._to_abs_int(item.current_price),
                        "change_rate": self._normalize_change_rate(item.change_rate),
                        "intraday_change_rate": item.intraday_change_rate,
                        "trading_value": self._to_int_or_none(item.trading_value),
                        "volume": self._to_nonneg_int(item.volume),
                        "detected_at": detected_at,
                        "source": payload.source,
                        "source_api": item.source_api,
                    },
                )
                saved_count += 1
                continue
            self.db.execute(
                text(
                    """
                    INSERT INTO kiwoom_condition_result_items
                    (condition_id, condition_seq, condition_name, stock_code, stock_code_raw, stock_name,
                     current_price, change_rate, intraday_change_rate, trading_value, volume,
                     detected_at, source, source_api, raw_json, created_at)
                    VALUES
                    (:condition_id, :condition_seq, :condition_name, :stock_code, :stock_code_raw, :stock_name,
                     :current_price, :change_rate, :intraday_change_rate, :trading_value, :volume,
                     :detected_at, :source, :source_api, NULL, :created_at)
                    """
                ),
                {
                    "condition_id": condition_id,
                    "condition_seq": condition_seq,
                    "condition_name": condition_name,
                    "stock_code": code,
                    "stock_code_raw": item.stock_code_raw or item.stock_code,
                    "stock_name": item.stock_name,
                    "current_price": self._to_abs_int(item.current_price),
                    "change_rate": self._normalize_change_rate(item.change_rate),
                    "intraday_change_rate": item.intraday_change_rate,
                    "trading_value": self._to_int_or_none(item.trading_value),
                    "volume": self._to_nonneg_int(item.volume),
                    "detected_at": detected_at,
                    "source": payload.source,
                    "source_api": item.source_api,
                    "created_at": now,
                },
            )
            saved_count += 1

        self.db.commit()
        return KiwoomConditionResultSaveResponse(success=True, saved_count=saved_count, skipped_count=skipped_count)

    @staticmethod
    def _to_int_or_none(value: object | None) -> int | None:
        if value is None:
            return None
        try:
            return int(float(str(value).replace(",", "").strip()))
        except Exception:
            return None

    @classmethod
    def _to_abs_int(cls, value: object | None) -> int | None:
        n = cls._to_int_or_none(value)
        return abs(n) if n is not None else None

    @classmethod
    def _to_nonneg_int(cls, value: object | None) -> int | None:
        n = cls._to_int_or_none(value)
        if n is None:
            return None
        return max(0, n)

    @staticmethod
    def _normalize_change_rate(value: object | None) -> float | None:
        if value is None:
            return None
        try:
            rate = float(str(value).replace(",", "").strip())
        except Exception:
            return None
        if abs(rate) > 100:
            rate = rate / 100.0
        return rate

    def list_condition_results(self, condition_seq: str, limit: int = 200) -> KiwoomConditionResultListResponse:
        rows = self.db.execute(
            text(
                """
                SELECT id, condition_seq, condition_name, stock_code, stock_code_raw, stock_name,
                       current_price, change_rate, intraday_change_rate, trading_value, volume, detected_at, source_api
                FROM kiwoom_condition_result_items
                WHERE condition_seq=:condition_seq
                ORDER BY detected_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"condition_seq": condition_seq, "limit": limit},
        ).mappings().all()
        items = []
        for row in rows:
            item = dict(row)
            item["estimated_trading_value"] = self._estimate_trading_value(item.get("current_price"), item.get("volume"))
            items.append(item)
        return KiwoomConditionResultListResponse(items=items)

    @staticmethod
    def _estimate_trading_value(current_price: object | None, volume: object | None) -> int | None:
        p = ExternalKiwoomService._to_abs_int(current_price)
        v = ExternalKiwoomService._to_nonneg_int(volume)
        if p is None or v is None:
            return None
        return p * v

    def preview_condition_results(self, condition_seq: str, payload: KiwoomConditionPreviewRequest) -> KiwoomConditionPreviewResponse:
        try:
            fetched = self._condition_provider.fetch_condition_results(
                condition_seq=str(condition_seq),
                condition_name=payload.condition_name,
                search_type=payload.search_type,
                stex_tp=payload.stex_tp,
            )
        except KiwoomApiError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Kiwoom 조건검색 결과를 가져오지 못했습니다. api_id=ka10172 return_code={exc.code} message={exc.message}",
            ) from exc

        items_raw = fetched.get("items") if isinstance(fetched.get("items"), list) else []
        items: list[KiwoomConditionResultItemOut] = []
        for row in items_raw:
            if not isinstance(row, dict):
                continue
            normalized = {
                "id": 0,
                "condition_seq": str(row.get("condition_seq") or condition_seq),
                "condition_name": row.get("condition_name") or payload.condition_name,
                "stock_code": str(row.get("stock_code") or ""),
                "stock_code_raw": row.get("stock_code_raw"),
                "stock_name": row.get("stock_name"),
                "current_price": self._to_abs_int(row.get("current_price")),
                "change_rate": self._normalize_change_rate(row.get("change_rate")),
                "intraday_change_rate": self._normalize_change_rate(row.get("intraday_change_rate")),
                "trading_value": self._to_int_or_none(row.get("trading_value")),
                "volume": self._to_nonneg_int(row.get("volume")),
                "detected_at": str(row.get("detected_at") or now_kst()),
                "source_api": row.get("source_api"),
                "estimated_trading_value": self._estimate_trading_value(row.get("current_price"), row.get("volume")),
            }
            if len(normalized["stock_code"]) != 6:
                continue
            items.append(KiwoomConditionResultItemOut(**normalized))

        return_code = str(fetched.get("return_code") or "")
        return_msg = str(fetched.get("return_msg") or "") or None
        parsing_error = bool(fetched.get("parsing_error"))
        success = return_code in {"", "0", "000000"}
        error_message = None
        if parsing_error:
            error_message = "조건검색 응답은 수신했지만 결과 종목을 해석하지 못했습니다."
        return KiwoomConditionPreviewResponse(
            success=success,
            source=str(fetched.get("source") or "kiwoom_ws"),
            api_id=str(fetched.get("api_id") or "CNSRREQ"),
            condition_seq=str(fetched.get("condition_seq") or condition_seq),
            condition_name=(fetched.get("condition_name") if fetched.get("condition_name") is not None else payload.condition_name),
            requested_condition_seq=str(fetched.get("requested_condition_seq") or condition_seq),
            requested_condition_name=(fetched.get("requested_condition_name") if fetched.get("requested_condition_name") is not None else payload.condition_name),
            resolved_condition_seq=(str(fetched.get("resolved_condition_seq")) if fetched.get("resolved_condition_seq") is not None else None),
            resolved_condition_name=(fetched.get("resolved_condition_name") if fetched.get("resolved_condition_name") is not None else None),
            return_code=return_code or None,
            return_msg=return_msg,
            item_count=len(items),
            items=items,
            parsing_error=parsing_error,
            debug=fetched.get("debug") if isinstance(fetched.get("debug"), dict) else {},
            error_message=error_message,
        )

    def save_market_events(self, payload: KiwoomMarketEventSaveRequest) -> KiwoomMarketEventSaveResponse:
        now = now_kst()
        default_trade_date = datetime.strptime(now, "%Y-%m-%d %H:%M:%S").date().isoformat()
        payload_trade_date = (payload.detected_date or "").strip() if payload.detected_date else ""
        saved_count = 0
        updated_count = 0
        unmatched_items: list[str] = []

        for item in payload.items:
            event_trade_date = payload_trade_date or (str(item.detected_at or "")[:10] if item.detected_at else "") or default_trade_date
            code = normalize_stock_code(item.stock_code or item.stock_code_raw)
            if len(code) != 6:
                unmatched_items.append(item.stock_code or item.stock_code_raw or "")
                continue

            stock = self.db.execute(
                text(
                    """
                    SELECT id, stock_name, market
                    FROM stocks
                    WHERE is_active=1
                      AND (stock_code=:stock_code OR stock_code=:stock_code_prefixed)
                    LIMIT 1
                    """
                ),
                {"stock_code": code, "stock_code_prefixed": f"A{code}"},
            ).mappings().first()
            if not stock:
                unmatched_items.append(code)
                continue

            stock_id = int(stock["id"])
            existing = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM market_trend_events
                    WHERE trade_date=:trade_date
                      AND stock_id=:stock_id
                      AND event_type='kiwoom_condition'
                      AND COALESCE(condition_seq, '') = :condition_seq
                    LIMIT 1
                    """
                ),
                {"trade_date": event_trade_date, "stock_id": stock_id, "condition_seq": payload.condition_seq},
            ).mappings().first()

            estimated_trading_value = self._estimate_trading_value(item.current_price, item.volume)
            persisted_trading_value = item.trading_value if item.trading_value is not None else estimated_trading_value

            if existing:
                self.db.execute(
                    text(
                        """
                        UPDATE market_trend_events
                        SET stock_code=:stock_code,
                            stock_name=:stock_name,
                            market_type=:market_type,
                            trading_value=:trading_value,
                            change_rate=:change_rate,
                            condition_seq=:condition_seq,
                            condition_name=:condition_name,
                            detection_source='kiwoom_condition',
                            is_active=1,
                            deleted_at=NULL,
                            detected_at=:detected_at,
                            updated_at=:updated_at
                        WHERE id=:id
                        """
                    ),
                    {
                        "id": int(existing["id"]),
                        "stock_code": code,
                        "stock_name": item.stock_name or stock["stock_name"],
                        "market_type": stock["market"],
                        "trading_value": persisted_trading_value,
                        "change_rate": item.intraday_change_rate if item.intraday_change_rate is not None else item.change_rate,
                        "condition_seq": payload.condition_seq,
                        "condition_name": payload.condition_name,
                        "detected_at": item.detected_at or now,
                        "updated_at": now,
                    },
                )
                updated_count += 1
            else:
                self.db.execute(
                    text(
                        """
                        INSERT INTO market_trend_events (
                            trade_date, stock_id, stock_code, stock_name, market_type,
                            market_cap, trading_value, change_rate, intraday_range_rate,
                            event_type, detection_setting_id,
                            applied_min_market_cap, applied_min_trading_value, applied_min_change_rate,
                            applied_min_intraday_range_rate, applied_use_market_cap, applied_use_trading_value,
                            applied_use_change_rate, applied_use_intraday_range,
                            theme_id, theme_status, primary_theme_id, reason_summary, user_memo,
                            is_active, created_at, updated_at, detection_source, condition_seq, condition_name, detected_at
                        ) VALUES (
                            :trade_date, :stock_id, :stock_code, :stock_name, :market_type,
                            NULL, :trading_value, :change_rate, NULL,
                            'kiwoom_condition', NULL,
                            NULL, NULL, NULL,
                            NULL, NULL, NULL,
                            NULL, NULL,
                            NULL, 'unassigned', NULL, NULL, NULL,
                            1, :created_at, :updated_at, 'kiwoom_condition', :condition_seq, :condition_name, :detected_at
                        )
                        """
                    ),
                    {
                        "trade_date": event_trade_date,
                        "stock_id": stock_id,
                        "stock_code": code,
                        "stock_name": item.stock_name or stock["stock_name"],
                        "market_type": stock["market"],
                        "trading_value": persisted_trading_value,
                        "change_rate": item.intraday_change_rate if item.intraday_change_rate is not None else item.change_rate,
                        "created_at": now,
                        "updated_at": now,
                        "condition_seq": payload.condition_seq,
                        "condition_name": payload.condition_name,
                        "detected_at": item.detected_at or now,
                    },
                )
                saved_count += 1

        self.db.commit()
        return KiwoomMarketEventSaveResponse(
            success=True,
            saved_count=saved_count,
            updated_count=updated_count,
            unmatched_count=len(unmatched_items),
            unmatched_items=unmatched_items[:50],
        )

    def get_daily_theme_flow(self, trade_date: str) -> DailyThemeFlowSummaryResponse:
        rows = self.db.execute(
            text(
                """
                WITH event_theme_pairs AS (
                    SELECT l.event_id, l.market_theme_id
                    FROM market_trend_event_theme_links l
                    WHERE COALESCE(l.is_active, 1) = 1
                    UNION
                    SELECT id AS event_id, theme_id AS market_theme_id
                    FROM market_trend_events
                    WHERE theme_id IS NOT NULL
                )
                SELECT
                    mt.id AS market_theme_id,
                    mt.theme_name AS theme_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT mte.stock_code) AS stock_count,
                    AVG(mte.change_rate) AS avg_change_rate,
                    MAX(mte.change_rate) AS max_change_rate,
                    SUM(COALESCE(mte.trading_value, 0)) AS estimated_trading_value_sum
                FROM market_trend_events mte
                JOIN event_theme_pairs etp ON etp.event_id = mte.id
                JOIN market_themes mt ON mt.id = etp.market_theme_id
                WHERE mte.trade_date = :trade_date
                  AND mte.detection_source IN ('kiwoom_condition', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                GROUP BY mt.id, mt.theme_name
                ORDER BY stock_count DESC, avg_change_rate DESC, mt.theme_name ASC
                """
            ),
            {"trade_date": trade_date},
        ).mappings().all()

        rep_rows = self.db.execute(
            text(
                """
                WITH event_theme_pairs AS (
                    SELECT l.event_id, l.market_theme_id
                    FROM market_trend_event_theme_links l
                    WHERE COALESCE(l.is_active, 1) = 1
                    UNION
                    SELECT id AS event_id, theme_id AS market_theme_id
                    FROM market_trend_events
                    WHERE theme_id IS NOT NULL
                )
                SELECT
                    mt.id AS market_theme_id,
                    mte.stock_name,
                    mte.change_rate,
                    ROW_NUMBER() OVER (
                        PARTITION BY mt.id
                        ORDER BY mte.change_rate DESC, mte.stock_name ASC
                    ) AS rn
                FROM market_trend_events mte
                JOIN event_theme_pairs etp ON etp.event_id = mte.id
                JOIN market_themes mt ON mt.id = etp.market_theme_id
                WHERE mte.trade_date = :trade_date
                  AND mte.detection_source IN ('kiwoom_condition', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND mte.stock_name IS NOT NULL
                """
            ),
            {"trade_date": trade_date},
        ).mappings().all()

        rep_map: dict[int, list[str]] = {}
        for row in rep_rows:
            theme_id = int(row["market_theme_id"])
            rn = int(row["rn"])
            if rn > 3:
                continue
            rep_map.setdefault(theme_id, []).append(str(row["stock_name"]))

        items: list[DailyThemeFlowSummaryItem] = []
        for row in rows:
            theme_id = int(row["market_theme_id"])
            items.append(
                DailyThemeFlowSummaryItem(
                    market_theme_id=theme_id,
                    theme_name=str(row["theme_name"]),
                    event_count=int(row["event_count"] or 0),
                    stock_count=int(row["stock_count"] or 0),
                    avg_change_rate=float(row["avg_change_rate"]) if row["avg_change_rate"] is not None else None,
                    max_change_rate=float(row["max_change_rate"]) if row["max_change_rate"] is not None else None,
                    estimated_trading_value_sum=int(row["estimated_trading_value_sum"] or 0),
                    representative_stocks=rep_map.get(theme_id, []),
                )
            )
        ranked_items = self._apply_rank_overrides(trade_date=trade_date, items=items)
        return DailyThemeFlowSummaryResponse(success=True, trade_date=trade_date, items=ranked_items)

    @staticmethod
    def _rank_score(rank: int | None) -> int:
        if rank is None or rank <= 0:
            return 0
        if rank == 1:
            return 10
        if rank == 2:
            return 8
        if rank == 3:
            return 6
        if rank == 4:
            return 4
        if rank == 5:
            return 2
        return 1

    def _apply_rank_overrides(self, trade_date: str, items: list[DailyThemeFlowSummaryItem]) -> list[DailyThemeFlowSummaryItem]:
        if not items:
            return []
        scored_items = self._with_theme_strength_scores(items)
        sorted_auto = sorted(scored_items, key=self._auto_theme_rank_sort_key)
        auto_rank_map = {item.market_theme_id: idx + 1 for idx, item in enumerate(sorted_auto)}
        rank_rows = self.db.execute(
            text(
                """
                SELECT market_theme_id, manual_rank
                FROM daily_theme_flow_ranks
                WHERE trade_date=:trade_date
                """
            ),
            {"trade_date": trade_date},
        ).mappings().all()
        manual_map: dict[int, int] = {}
        for row in rank_rows:
            mr = row.get("manual_rank")
            if mr is None:
                continue
            value = int(mr)
            if value > 0:
                manual_map[int(row["market_theme_id"])] = value

        ranked = []
        for item in scored_items:
            auto_rank = auto_rank_map.get(item.market_theme_id)
            manual_rank = manual_map.get(item.market_theme_id)
            final_rank = manual_rank if manual_rank is not None else auto_rank
            rank_basis = "manual" if manual_rank is not None else "auto"
            ranked.append(
                DailyThemeFlowSummaryItem(
                    market_theme_id=item.market_theme_id,
                    theme_name=item.theme_name,
                    event_count=item.event_count,
                    stock_count=item.stock_count,
                    avg_change_rate=item.avg_change_rate,
                    max_change_rate=item.max_change_rate,
                    estimated_trading_value_sum=item.estimated_trading_value_sum,
                    representative_stocks=item.representative_stocks,
                    auto_rank=auto_rank,
                    manual_rank=manual_rank,
                    final_rank=final_rank,
                    theme_strength_score=item.theme_strength_score,
                    return_score=item.return_score,
                    trading_value_score=item.trading_value_score,
                    breadth_score=item.breadth_score,
                    rank_score=item.theme_strength_score,
                    rank_basis=rank_basis,
                )
            )
        ranked.sort(
            key=lambda x: (
                0 if x.manual_rank is not None else 1,
                999999 if x.manual_rank is None else int(x.manual_rank),
                -float(x.theme_strength_score or 0),
                -999999 if x.avg_change_rate is None else -float(x.avg_change_rate),
                -int(x.estimated_trading_value_sum),
                -int(x.stock_count),
                str(x.theme_name),
            )
        )
        return ranked

    @staticmethod
    def _clamp_score(value: float) -> float:
        return max(0.0, min(100.0, value))

    @classmethod
    def _return_score(cls, avg_change_rate: float | None) -> float:
        if avg_change_rate is None or avg_change_rate <= 0:
            return 0.0
        return cls._clamp_score((float(avg_change_rate) / 10.0) * 100.0)

    @classmethod
    def _breadth_score(cls, stock_count: int) -> float:
        return cls._clamp_score((max(0, int(stock_count)) / 8.0) * 100.0)

    @classmethod
    def _with_theme_strength_scores(cls, items: list[DailyThemeFlowSummaryItem]) -> list[DailyThemeFlowSummaryItem]:
        positive_logs = [
            math.log10(float(item.estimated_trading_value_sum) + 1.0)
            for item in items
            if float(item.estimated_trading_value_sum or 0) > 0
        ]
        min_log = min(positive_logs) if positive_logs else 0.0
        max_log = max(positive_logs) if positive_logs else 0.0
        scored: list[DailyThemeFlowSummaryItem] = []
        for item in items:
            trading_value = float(item.estimated_trading_value_sum or 0)
            if trading_value <= 0:
                trading_value_score = 0.0
            elif max_log == min_log:
                trading_value_score = 50.0
            else:
                log_value = math.log10(trading_value + 1.0)
                trading_value_score = cls._clamp_score(((log_value - min_log) / (max_log - min_log)) * 100.0)
            return_score = cls._return_score(item.avg_change_rate)
            breadth_score = cls._breadth_score(item.stock_count)
            strength = (0.50 * return_score) + (0.35 * trading_value_score) + (0.15 * breadth_score)
            scored.append(
                DailyThemeFlowSummaryItem(
                    market_theme_id=item.market_theme_id,
                    theme_name=item.theme_name,
                    event_count=item.event_count,
                    stock_count=item.stock_count,
                    avg_change_rate=item.avg_change_rate,
                    max_change_rate=item.max_change_rate,
                    estimated_trading_value_sum=item.estimated_trading_value_sum,
                    representative_stocks=item.representative_stocks,
                    auto_rank=item.auto_rank,
                    manual_rank=item.manual_rank,
                    final_rank=item.final_rank,
                    theme_strength_score=round(strength, 1),
                    return_score=round(return_score, 1),
                    trading_value_score=round(trading_value_score, 1),
                    breadth_score=round(breadth_score, 1),
                    rank_score=round(strength, 1),
                    rank_basis=item.rank_basis,
                )
            )
        return scored

    @staticmethod
    def _auto_theme_rank_sort_key(item: DailyThemeFlowSummaryItem) -> tuple[float, float, int, int, str]:
        return (
            -float(item.theme_strength_score or 0),
            -999999 if item.avg_change_rate is None else -float(item.avg_change_rate),
            -int(item.estimated_trading_value_sum or 0),
            -int(item.stock_count or 0),
            str(item.theme_name),
        )

    def update_daily_theme_flow_ranks(self, payload: DailyThemeRanksUpdateRequest) -> DailyThemeRanksUpdateResponse:
        daily = self.get_daily_theme_flow(payload.trade_date)
        valid_theme_ids = {item.market_theme_id for item in daily.items}
        now = now_kst()
        requested_ranks = [int(x.manual_rank) for x in payload.items if x.manual_rank is not None]
        if len(requested_ranks) != len(set(requested_ranks)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="manual_rank 값이 중복되었습니다.")

        updated_count = 0
        for row in payload.items:
            if row.market_theme_id not in valid_theme_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"유효하지 않은 market_theme_id: {row.market_theme_id}")
            existing = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM daily_theme_flow_ranks
                    WHERE trade_date=:trade_date AND market_theme_id=:market_theme_id
                    LIMIT 1
                    """
                ),
                {"trade_date": payload.trade_date, "market_theme_id": row.market_theme_id},
            ).mappings().first()
            auto_rank = next((x.auto_rank for x in daily.items if x.market_theme_id == row.market_theme_id), None)
            manual_rank = int(row.manual_rank) if row.manual_rank is not None else None
            final_rank = manual_rank if manual_rank is not None else auto_rank
            rank_basis = "manual" if manual_rank is not None else "auto"
            source_item = next((x for x in daily.items if x.market_theme_id == row.market_theme_id), None)
            rank_score = float(source_item.theme_strength_score if source_item is not None else 0)

            if existing:
                self.db.execute(
                    text(
                        """
                        UPDATE daily_theme_flow_ranks
                        SET auto_rank=:auto_rank,
                            manual_rank=:manual_rank,
                            final_rank=:final_rank,
                            rank_score=:rank_score,
                            rank_basis=:rank_basis,
                            user_memo=:user_memo,
                            updated_at=:updated_at
                        WHERE id=:id
                        """
                    ),
                    {
                        "id": int(existing["id"]),
                        "auto_rank": auto_rank,
                        "manual_rank": manual_rank,
                        "final_rank": final_rank,
                        "rank_score": rank_score,
                        "rank_basis": rank_basis,
                        "user_memo": row.user_memo,
                        "updated_at": now,
                    },
                )
            else:
                self.db.execute(
                    text(
                        """
                        INSERT INTO daily_theme_flow_ranks
                        (trade_date, market_theme_id, auto_rank, manual_rank, final_rank, rank_score, rank_basis, user_memo, created_at, updated_at)
                        VALUES
                        (:trade_date, :market_theme_id, :auto_rank, :manual_rank, :final_rank, :rank_score, :rank_basis, :user_memo, :created_at, :updated_at)
                        """
                    ),
                    {
                        "trade_date": payload.trade_date,
                        "market_theme_id": row.market_theme_id,
                        "auto_rank": auto_rank,
                        "manual_rank": manual_rank,
                        "final_rank": final_rank,
                        "rank_score": rank_score,
                        "rank_basis": rank_basis,
                        "user_memo": row.user_memo,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
            updated_count += 1
        self.db.commit()
        latest = self.get_daily_theme_flow(payload.trade_date)
        return DailyThemeRanksUpdateResponse(
            success=True,
            trade_date=payload.trade_date,
            updated_count=updated_count,
            items=latest.items,
        )

    def get_daily_theme_flow_stocks(self, trade_date: str, market_theme_id: int) -> DailyThemeFlowStocksResponse:
        rows = self.db.execute(
            text(
                """
                WITH event_theme_pairs AS (
                    SELECT l.event_id, l.market_theme_id
                    FROM market_trend_event_theme_links l
                    WHERE COALESCE(l.is_active, 1) = 1
                    UNION
                    SELECT id AS event_id, theme_id AS market_theme_id
                    FROM market_trend_events
                    WHERE theme_id IS NOT NULL
                )
                SELECT
                    mte.id AS event_id,
                    mt.id AS market_theme_id,
                    mt.theme_name AS theme_name,
                    mte.stock_code AS stock_code,
                    COALESCE(mte.stock_name, s.stock_name) AS stock_name,
                    mte.change_rate AS change_rate,
                    mte.condition_seq AS condition_seq,
                    mte.condition_name AS condition_name,
                    mte.user_memo AS user_memo,
                    mte.trading_value AS trading_value
                FROM market_trend_events mte
                JOIN event_theme_pairs etp ON etp.event_id = mte.id
                JOIN market_themes mt ON mt.id = etp.market_theme_id
                LEFT JOIN stocks s ON s.id = mte.stock_id
                WHERE mte.trade_date = :trade_date
                  AND mt.id = :market_theme_id
                  AND mte.detection_source IN ('kiwoom_condition', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                ORDER BY mte.change_rate DESC, mte.stock_code ASC, mte.id DESC
                """
            ),
            {"trade_date": trade_date, "market_theme_id": market_theme_id},
        ).mappings().all()

        dedup: dict[str, DailyThemeFlowStockItem] = {}
        theme_name: str | None = None
        for row in rows:
            code = normalize_stock_code(row["stock_code"])
            if len(code) != 6:
                continue
            theme_name = str(row["theme_name"])
            if code in dedup:
                continue
            dedup[code] = DailyThemeFlowStockItem(
                event_id=int(row["event_id"]),
                market_theme_id=int(row["market_theme_id"]),
                theme_name=str(row["theme_name"]),
                stock_code=code,
                stock_name=str(row["stock_name"] or code),
                change_rate=float(row["change_rate"]) if row["change_rate"] is not None else None,
                current_price=None,
                volume=None,
                estimated_trading_value=int(row["trading_value"]) if row["trading_value"] is not None else None,
                condition_seq=row["condition_seq"],
                condition_name=row["condition_name"],
                user_memo=row["user_memo"],
            )
        items = list(dedup.values())
        return DailyThemeFlowStocksResponse(
            success=True,
            trade_date=trade_date,
            market_theme_id=market_theme_id,
            theme_name=theme_name,
            items=items,
        )

    def get_monthly_theme_flow_calendar(self, month: str) -> MonthlyThemeFlowCalendarResponse:
        month_start, month_end = self._resolve_month_window(month)
        rows = self.db.execute(
            text(
                """
                SELECT
                    mte.trade_date AS trade_date,
                    CASE WHEN mt.theme_level = 'THEME_GROUP' THEN mt.id ELSE parent_mt.id END AS theme_group_id,
                    COALESCE(
                      CASE WHEN mt.theme_level = 'THEME_GROUP' THEN mt.theme_name ELSE parent_mt.theme_name END,
                      '미지정 테마그룹'
                    ) AS theme_group_name,
                    mt.id AS market_theme_id,
                    mt.theme_name AS theme_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT mte.stock_code) AS stock_count,
                    AVG(mte.change_rate) AS avg_change_rate,
                    MAX(mte.change_rate) AS max_change_rate,
                    SUM(
                      COALESCE(
                        mte.trading_value,
                        0
                      )
                    ) AS estimated_trading_value_sum
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                LEFT JOIN market_themes parent_mt ON parent_mt.id = mt.parent_theme_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                GROUP BY mte.trade_date, theme_group_id, theme_group_name, mt.id, mt.theme_name
                ORDER BY mte.trade_date ASC, stock_count DESC, event_count DESC, estimated_trading_value_sum DESC, avg_change_rate DESC, mt.theme_name ASC
                """
            ),
            {"start_date": month_start.isoformat(), "end_date": month_end.isoformat()},
        ).mappings().all()

        stock_rows = self.db.execute(
            text(
                """
                SELECT DISTINCT
                    mte.trade_date AS trade_date,
                    mt.id AS market_theme_id,
                    mte.stock_id AS stock_id,
                    mte.stock_code AS stock_code,
                    COALESCE(mte.stock_name, s.stock_name, mte.stock_code, '-') AS stock_name,
                    mte.change_rate AS change_rate
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                LEFT JOIN stocks s ON s.id = mte.stock_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                ORDER BY mte.trade_date ASC, mt.id ASC, stock_name ASC, stock_code ASC
                """
            ),
            {"start_date": month_start.isoformat(), "end_date": month_end.isoformat()},
        ).mappings().all()
        stocks_by_date_theme: dict[tuple[str, int], list[MonthlyThemeFlowStockItem]] = {}
        seen_stocks: set[tuple[str, int, str]] = set()
        for row in stock_rows:
            trade_date = str(row["trade_date"])
            theme_id = int(row["market_theme_id"])
            stock_code = str(row["stock_code"] or "")
            stock_key = stock_code or str(row["stock_id"] or row["stock_name"] or "")
            seen_key = (trade_date, theme_id, stock_key)
            if seen_key in seen_stocks:
                continue
            seen_stocks.add(seen_key)
            stocks_by_date_theme.setdefault((trade_date, theme_id), []).append(
                MonthlyThemeFlowStockItem(
                    stock_id=int(row["stock_id"]) if row["stock_id"] is not None else None,
                    stock_code=stock_code or None,
                    stock_name=str(row["stock_name"] or stock_code or "-"),
                    change_rate=float(row["change_rate"]) if row["change_rate"] is not None else None,
                )
            )

        memo_rows = self.db.execute(
            text(
                """
                SELECT
                    mte.trade_date AS trade_date,
                    mt.id AS market_theme_id,
                    mt.theme_name AS theme_name,
                    mte.stock_code AS stock_code,
                    COALESCE(mte.stock_name, s.stock_name, mte.stock_code, '-') AS stock_name,
                    mte.user_memo AS user_memo
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                LEFT JOIN stocks s ON s.id = mte.stock_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                  AND TRIM(COALESCE(mte.user_memo, '')) <> ''
                ORDER BY mte.trade_date ASC, mt.theme_name ASC, stock_name ASC, mte.stock_code ASC
                """
            ),
            {"start_date": month_start.isoformat(), "end_date": month_end.isoformat()},
        ).mappings().all()
        memo_items_by_date: dict[str, list[MonthlyThemeFlowMemoItem]] = {}
        seen_memos: set[tuple[str, int, str, str]] = set()
        for row in memo_rows:
            trade_date = str(row["trade_date"])
            theme_id = int(row["market_theme_id"]) if row["market_theme_id"] is not None else 0
            stock_code = str(row["stock_code"] or "")
            memo = str(row["user_memo"] or "").strip()
            seen_key = (trade_date, theme_id, stock_code or str(row["stock_name"] or ""), memo)
            if seen_key in seen_memos:
                continue
            seen_memos.add(seen_key)
            memo_items_by_date.setdefault(trade_date, []).append(
                MonthlyThemeFlowMemoItem(
                    theme_id=theme_id or None,
                    theme_name=str(row["theme_name"] or "미지정 테마"),
                    stock_code=stock_code or None,
                    stock_name=str(row["stock_name"] or stock_code or "-"),
                    memo=memo,
                )
            )

        grouped: dict[str, list[DailyThemeFlowSummaryItem]] = {}
        theme_group_meta: dict[tuple[str, int], dict[str, object]] = {}
        for row in rows:
            trade_date = str(row["trade_date"])
            theme_id = int(row["market_theme_id"])
            theme_group_meta[(trade_date, theme_id)] = {
                "theme_group_id": int(row["theme_group_id"]) if row["theme_group_id"] is not None else None,
                "theme_group_name": str(row["theme_group_name"] or "미지정 테마그룹"),
            }
            grouped.setdefault(trade_date, []).append(
                DailyThemeFlowSummaryItem(
                    market_theme_id=theme_id,
                    theme_name=str(row["theme_name"]),
                    stock_count=int(row["stock_count"] or 0),
                    event_count=int(row["event_count"] or 0),
                    avg_change_rate=float(row["avg_change_rate"]) if row["avg_change_rate"] is not None else None,
                    max_change_rate=float(row["max_change_rate"]) if row["max_change_rate"] is not None else None,
                    estimated_trading_value_sum=int(row["estimated_trading_value_sum"] or 0),
                    representative_stocks=[],
                )
            )

        day_total_rows = self.db.execute(
            text(
                """
                SELECT
                    mte.trade_date AS trade_date,
                    COUNT(DISTINCT mte.id) AS event_count,
                    COUNT(DISTINCT mte.stock_code) AS related_stock_count
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                GROUP BY mte.trade_date
                """
            ),
            {"start_date": month_start.isoformat(), "end_date": month_end.isoformat()},
        ).mappings().all()
        day_totals = {
            str(row["trade_date"]): {
                "event_count": int(row["event_count"] or 0),
                "related_stock_count": int(row["related_stock_count"] or 0),
            }
            for row in day_total_rows
        }

        days: list[MonthlyThemeFlowCalendarDayItem] = []
        cursor = month_start
        while cursor <= month_end:
            key = cursor.isoformat()
            day_themes = grouped.get(key, [])
            ranked_day = self._apply_rank_overrides(trade_date=key, items=day_themes)
            ranked = [
                MonthlyThemeFlowCalendarThemeItem(
                    rank=int(item.final_rank or (idx + 1)),
                    market_theme_id=item.market_theme_id,
                    theme_name=item.theme_name,
                    stock_count=item.stock_count,
                    event_count=item.event_count,
                    avg_change_rate=item.avg_change_rate,
                    max_change_rate=item.max_change_rate,
                    estimated_trading_value_sum=item.estimated_trading_value_sum,
                    auto_rank=item.auto_rank,
                    manual_rank=item.manual_rank,
                    final_rank=item.final_rank,
                    theme_strength_score=item.theme_strength_score,
                    return_score=item.return_score,
                    trading_value_score=item.trading_value_score,
                    breadth_score=item.breadth_score,
                    rank_score=float(item.rank_score),
                    rank_basis=item.rank_basis,
                    theme_group_id=theme_group_meta.get((key, item.market_theme_id), {}).get("theme_group_id"),
                    theme_group_name=str(theme_group_meta.get((key, item.market_theme_id), {}).get("theme_group_name") or "미지정 테마그룹"),
                    stocks=stocks_by_date_theme.get((key, item.market_theme_id), []),
                )
                for idx, item in enumerate(ranked_day)
            ]
            totals = day_totals.get(key, {"event_count": 0, "related_stock_count": 0})
            days.append(
                MonthlyThemeFlowCalendarDayItem(
                    trade_date=key,
                    event_count=totals["event_count"],
                    related_stock_count=totals["related_stock_count"],
                    themes=ranked,
                    memo_items=memo_items_by_date.get(key, []),
                )
            )
            cursor += timedelta(days=1)

        return MonthlyThemeFlowCalendarResponse(
            success=True,
            month=month,
            start_date=month_start.isoformat(),
            end_date=month_end.isoformat(),
            days=days,
        )

    def get_monthly_theme_flow_trend(
        self,
        month: str,
        view_mode: str = "THEME",
        theme_group_id: int | None = None,
        limit: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> MonthlyThemeFlowTrendResponse:
        month_start, month_end = self._resolve_theme_flow_trend_window(month, start_date, end_date)
        normalized_view_mode = (view_mode or "THEME").strip().upper()
        if normalized_view_mode not in {"THEME_GROUP", "THEME"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="view_mode는 THEME_GROUP 또는 THEME이어야 합니다.")
        normalized_limit = max(1, min(int(limit), 500)) if limit is not None else None
        theme_filter_sql = ""
        params: dict[str, object] = {"start_date": month_start.isoformat(), "end_date": month_end.isoformat()}
        if theme_group_id is not None:
            params["theme_group_id"] = theme_group_id
            if normalized_view_mode == "THEME":
                theme_filter_sql = "AND mt.parent_theme_id = :theme_group_id"
            else:
                theme_filter_sql = "AND COALESCE(parent_mt.id, mt.id) = :theme_group_id"

        id_sql = "COALESCE(parent_mt.id, mt.id)" if normalized_view_mode == "THEME_GROUP" else "mt.id"
        name_sql = "COALESCE(parent_mt.theme_name, mt.theme_name)" if normalized_view_mode == "THEME_GROUP" else "mt.theme_name"
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    mte.trade_date AS trade_date,
                    {id_sql} AS market_theme_id,
                    {name_sql} AS theme_name,
                    CASE WHEN mt.theme_level = 'THEME_GROUP' THEN mt.id ELSE parent_mt.id END AS theme_group_id,
                    COALESCE(
                      CASE WHEN mt.theme_level = 'THEME_GROUP' THEN mt.theme_name ELSE parent_mt.theme_name END,
                      '미지정 테마그룹'
                    ) AS theme_group_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT mte.stock_code) AS stock_count,
                    AVG(mte.change_rate) AS avg_change_rate,
                    MAX(mte.change_rate) AS max_change_rate,
                    SUM(
                      COALESCE(
                        mte.trading_value,
                        0
                      )
                    ) AS estimated_trading_value_sum
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                LEFT JOIN market_themes parent_mt ON parent_mt.id = mt.parent_theme_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                  {theme_filter_sql}
                GROUP BY mte.trade_date, {id_sql}, {name_sql}, theme_group_id, theme_group_name
                """
            ),
            params,
        ).mappings().all()

        child_rows = self.db.execute(
            text(
                f"""
                SELECT
                    CASE WHEN mt.theme_level = 'THEME_GROUP' THEN mt.id ELSE parent_mt.id END AS theme_group_id,
                    COALESCE(
                      CASE WHEN mt.theme_level = 'THEME_GROUP' THEN mt.theme_name ELSE parent_mt.theme_name END,
                      '미지정 테마그룹'
                    ) AS theme_group_name,
                    mt.id AS market_theme_id,
                    mt.theme_name AS theme_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT mte.stock_code) AS stock_count
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                LEFT JOIN market_themes parent_mt ON parent_mt.id = mt.parent_theme_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                  {theme_filter_sql}
                GROUP BY theme_group_id, theme_group_name, mt.id, mt.theme_name
                """
            ),
            params,
        ).mappings().all()
        child_theme_map: dict[int, list[dict[str, object]]] = {}
        for row in child_rows:
            group_id = int(row["theme_group_id"]) if row["theme_group_id"] is not None else int(row["market_theme_id"])
            child_theme_map.setdefault(group_id, []).append(
                {
                    "theme_name": str(row["theme_name"]),
                    "event_count": int(row["event_count"] or 0),
                    "stock_count": int(row["stock_count"] or 0),
                }
            )

        stock_rows = self.db.execute(
            text(
                f"""
                SELECT
                    {id_sql} AS market_theme_id,
                    COALESCE(mte.stock_name, s.stock_name, mte.stock_code, '-') AS stock_display_name,
                    MAX(mte.trade_date) AS latest_date
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                LEFT JOIN market_themes parent_mt ON parent_mt.id = mt.parent_theme_id
                LEFT JOIN stocks s ON s.id = mte.stock_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                  {theme_filter_sql}
                GROUP BY {id_sql}, COALESCE(mte.stock_name, s.stock_name, mte.stock_code, '-')
                ORDER BY latest_date DESC, stock_display_name ASC
                """
            ),
            params,
        ).mappings().all()
        related_stock_map: dict[int, list[str]] = {}
        for row in stock_rows:
            entity_id = int(row["market_theme_id"])
            stock_name = str(row["stock_display_name"] or "").strip()
            if not stock_name or stock_name == "-":
                continue
            current = related_stock_map.setdefault(entity_id, [])
            if stock_name not in current and len(current) < 8:
                current.append(stock_name)

        date_keys: list[str] = []
        cursor = month_start
        while cursor <= month_end:
            date_keys.append(cursor.isoformat())
            cursor += timedelta(days=1)

        by_date: dict[str, list[DailyThemeFlowSummaryItem]] = {}
        for row in rows:
            key = str(row["trade_date"])
            by_date.setdefault(key, []).append(
                DailyThemeFlowSummaryItem(
                    market_theme_id=int(row["market_theme_id"]),
                    theme_name=str(row["theme_name"]),
                    event_count=int(row["event_count"] or 0),
                    stock_count=int(row["stock_count"] or 0),
                    avg_change_rate=float(row["avg_change_rate"]) if row["avg_change_rate"] is not None else None,
                    max_change_rate=float(row["max_change_rate"]) if row["max_change_rate"] is not None else None,
                    estimated_trading_value_sum=int(row["estimated_trading_value_sum"] or 0),
                    representative_stocks=[],
                )
            )
        day_ranked: dict[str, list[DailyThemeFlowSummaryItem]] = {}
        total_score_map: dict[int, int] = {}
        theme_name_map: dict[int, str] = {}
        theme_group_meta_map: dict[int, dict[str, object]] = {}
        for key in date_keys:
            ranked = self._apply_rank_overrides(trade_date=key, items=by_date.get(key, []))
            day_ranked[key] = ranked
            for item in ranked:
                score = int(item.rank_score or 0)
                total_score_map[item.market_theme_id] = total_score_map.get(item.market_theme_id, 0) + score
                theme_name_map[item.market_theme_id] = item.theme_name
        for row in rows:
            entity_id = int(row["market_theme_id"])
            if normalized_view_mode == "THEME_GROUP":
                group_id = entity_id
                group_name = str(row["theme_name"])
            else:
                group_id = int(row["theme_group_id"]) if row["theme_group_id"] is not None else None
                group_name = str(row["theme_group_name"] or "미지정 테마그룹")
            theme_group_meta_map[entity_id] = {
                "theme_group_id": group_id,
                "theme_group_name": group_name,
            }

        sorted_theme_ids = sorted(total_score_map.keys(), key=lambda tid: (total_score_map.get(tid, 0), theme_name_map.get(tid, "")), reverse=True)

        themes: list[MonthlyThemeFlowTrendTheme] = []
        target_theme_ids = sorted_theme_ids[:normalized_limit] if normalized_limit is not None else sorted_theme_ids
        for theme_id in target_theme_ids:
            cumulative = 0
            series: list[MonthlyThemeFlowTrendPoint] = []
            for key in date_keys:
                ranked_day = day_ranked.get(key, [])
                day_item = next((x for x in ranked_day if x.market_theme_id == theme_id), None)
                if day_item is not None:
                    daily_score = int(day_item.rank_score or 0)
                    cumulative += daily_score
                    series.append(
                        MonthlyThemeFlowTrendPoint(
                            trade_date=key,
                            value=cumulative,
                            daily_score=daily_score,
                            final_rank=day_item.final_rank,
                            rank_basis=day_item.rank_basis,
                            stock_count=day_item.stock_count,
                            event_count=day_item.event_count,
                            avg_change_rate=day_item.avg_change_rate,
                            max_change_rate=day_item.max_change_rate,
                            estimated_trading_value_sum=day_item.estimated_trading_value_sum,
                        )
                    )
                else:
                    series.append(
                        MonthlyThemeFlowTrendPoint(
                            trade_date=key,
                            value=cumulative,
                            daily_score=0,
                            final_rank=None,
                            rank_basis="auto",
                            stock_count=0,
                            event_count=0,
                            avg_change_rate=None,
                            max_change_rate=None,
                            estimated_trading_value_sum=0,
                        )
                    )
            group_meta = theme_group_meta_map.get(theme_id, {})
            group_id = group_meta.get("theme_group_id")
            child_themes = child_theme_map.get(int(group_id), []) if group_id is not None else []
            child_theme_names = [
                str(row["theme_name"])
                for row in sorted(child_themes, key=lambda x: (int(x["event_count"]), int(x["stock_count"]), str(x["theme_name"])), reverse=True)
            ]
            themes.append(
                MonthlyThemeFlowTrendTheme(
                    market_theme_id=theme_id,
                    theme_name=theme_name_map.get(theme_id, str(theme_id)),
                    view_mode=normalized_view_mode,
                    theme_group_id=int(group_id) if group_id is not None else None,
                    theme_group_name=str(group_meta.get("theme_group_name") or ""),
                    child_theme_count=len(child_theme_names) if normalized_view_mode == "THEME_GROUP" else 0,
                    top_child_themes=child_theme_names[:3] if normalized_view_mode == "THEME_GROUP" else [],
                    related_stocks=related_stock_map.get(theme_id, []),
                    series=series,
                )
            )

        return MonthlyThemeFlowTrendResponse(
            success=True,
            month=month,
            start_date=month_start.isoformat(),
            end_date=month_end.isoformat(),
            themes=themes,
        )

    def _resolve_theme_flow_trend_window(
        self,
        month: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[date, date]:
        if start_date or end_date:
            if not start_date or not end_date:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date and end_date are required together.")
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date/end_date must be YYYY-MM-DD.")
            if start > end:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be before or equal to end_date.")
            return start, end

        return self._resolve_month_window(month)

    def _resolve_month_window(self, month: str) -> tuple[date, date]:
        try:
            parsed = datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month는 YYYY-MM 형식이어야 합니다.")
        month_start = date(parsed.year, parsed.month, 1)
        last_day = monthrange(parsed.year, parsed.month)[1]
        month_last = date(parsed.year, parsed.month, last_day)
        today = datetime.strptime(now_kst(), "%Y-%m-%d %H:%M:%S").date()
        if parsed.year == today.year and parsed.month == today.month:
            month_end = min(today, month_last)
        else:
            month_end = month_last
        return month_start, month_end

    def list_market_events(self, trade_date: str, limit: int = 200) -> KiwoomMarketEventListResponse:
        rows = self.db.execute(
            text(
                """
                SELECT id AS event_id, trade_date, stock_id, stock_code, stock_name, market_type, change_rate,
                       theme_status, condition_seq, condition_name, detection_source, user_memo, detected_at, updated_at
                FROM market_trend_events
                WHERE detection_source IN ('kiwoom_condition', 'manual')
                  AND trade_date=:trade_date
                  AND is_active=1
                ORDER BY detected_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"trade_date": trade_date, "limit": limit},
        ).mappings().all()
        stock_ids = sorted({int(row["stock_id"]) for row in rows if row.get("stock_id") is not None})
        themes_by_stock_id: dict[int, list[dict[str, object]]] = {stock_id: [] for stock_id in stock_ids}
        if stock_ids:
            placeholders = ", ".join(f":stock_id_{idx}" for idx, _ in enumerate(stock_ids))
            params = {f"stock_id_{idx}": stock_id for idx, stock_id in enumerate(stock_ids)}
            theme_rows = self.db.execute(
                text(
                    f"""
                    SELECT mts.stock_id,
                           mt.id AS theme_id,
                           mt.theme_name,
                           parent.id AS theme_group_id,
                           parent.theme_name AS theme_group_name,
                           COALESCE(mt.is_active, 1) AS is_active,
                           COALESCE(mts.is_primary, 0) AS is_primary,
                           mts.id AS mapping_id
                    FROM market_theme_stocks mts
                    JOIN market_themes mt ON mt.id = mts.theme_id
                    LEFT JOIN market_themes parent ON parent.id = mt.parent_theme_id
                    WHERE mts.stock_id IN ({placeholders})
                      AND COALESCE(mts.is_active, 1) = 1
                      AND COALESCE(mt.is_active, 1) = 1
                      AND COALESCE(mt.theme_level, 'THEME') = 'THEME'
                    ORDER BY COALESCE(mts.is_primary, 0) DESC, mt.theme_name ASC, mts.id ASC
                    """
                ),
                params,
            ).mappings().all()
            seen: set[tuple[int, int]] = set()
            for theme_row in theme_rows:
                stock_id = int(theme_row["stock_id"])
                theme_id = int(theme_row["theme_id"])
                key = (stock_id, theme_id)
                if key in seen:
                    continue
                seen.add(key)
                themes_by_stock_id.setdefault(stock_id, []).append(
                    {
                        "theme_id": theme_id,
                        "theme_name": theme_row["theme_name"],
                        "theme_group_id": theme_row["theme_group_id"],
                        "theme_group_name": theme_row["theme_group_name"],
                        "is_active": int(theme_row["is_active"] or 0),
                    }
                )
        items = []
        for row in rows:
            item = dict(row)
            stock_id = item.pop("stock_id", None)
            item["existing_themes"] = themes_by_stock_id.get(int(stock_id), []) if stock_id is not None else []
            items.append(KiwoomMarketEventItemOut(**item))
        return KiwoomMarketEventListResponse(items=items)

    def patch_market_event(self, event_id: int, payload: KiwoomMarketEventPatchRequest) -> KiwoomMarketEventPatchResponse:
        existing = self.db.execute(
            text(
                """
                SELECT id AS event_id, trade_date, stock_code, stock_name, market_type, change_rate,
                       theme_status, condition_seq, condition_name, detection_source, user_memo, detected_at, updated_at
                FROM market_trend_events
                WHERE id=:event_id
                  AND detection_source IN ('kiwoom_condition', 'manual')
                LIMIT 1
                """
            ),
            {"event_id": event_id},
        ).mappings().first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수급 이벤트 후보를 찾을 수 없습니다.")

        updates: dict[str, object] = {"event_id": event_id, "updated_at": now_kst()}
        set_clauses = ["updated_at=:updated_at"]
        if payload.theme_status is not None:
            updates["theme_status"] = payload.theme_status
            set_clauses.append("theme_status=:theme_status")
        if payload.user_memo is not None:
            updates["user_memo"] = payload.user_memo
            set_clauses.append("user_memo=:user_memo")

        self.db.execute(
            text(f"UPDATE market_trend_events SET {', '.join(set_clauses)} WHERE id=:event_id"),
            updates,
        )
        self.db.commit()

        row = self.db.execute(
            text(
                """
                SELECT id AS event_id, trade_date, stock_code, stock_name, market_type, change_rate,
                       theme_status, condition_seq, condition_name, detection_source, user_memo, detected_at, updated_at
                FROM market_trend_events
                WHERE id=:event_id
                LIMIT 1
                """
            ),
            {"event_id": event_id},
        ).mappings().first()
        return KiwoomMarketEventPatchResponse(success=True, item=KiwoomMarketEventItemOut(**dict(row)))

    def _sync_theme_stock_link_from_event(self, *, event_id: int, theme_id: int, now: str) -> ThemeStockSyncResult:
        event_row = self.db.execute(
            text(
                """
                SELECT id, stock_id, stock_code, stock_name
                FROM market_trend_events
                WHERE id=:event_id AND is_active=1
                """
            ),
            {"event_id": event_id},
        ).mappings().first()
        if not event_row:
            return ThemeStockSyncResult(status="skipped", reason="event_not_found")

        stock_id = int(event_row["stock_id"])
        existing = self.db.execute(
            text(
                """
                SELECT id, mapping_source, is_active
                FROM market_theme_stocks
                WHERE theme_id=:theme_id AND stock_id=:stock_id
                LIMIT 1
                """
            ),
            {"theme_id": theme_id, "stock_id": stock_id},
        ).mappings().first()
        if existing and int(existing["is_active"] or 0) == 1:
            print(f"[theme-stock-sync] skipped existing theme_id={theme_id} stock_id={stock_id}")
            return ThemeStockSyncResult(status="skipped", reason="already_exists", mapping_id=int(existing["id"]))
        if existing:
            self.db.execute(
                text(
                    """
                    UPDATE market_theme_stocks
                    SET is_active=1, updated_at=:updated_at
                    WHERE id=:mapping_id
                    """
                ),
                {"mapping_id": int(existing["id"]), "updated_at": now},
            )
            print(f"[theme-stock-sync] reactivated theme_id={theme_id} stock_id={stock_id}")
            return ThemeStockSyncResult(status="reactivated", mapping_id=int(existing["id"]))

        self.db.execute(
            text(
                """
                INSERT INTO market_theme_stocks
                (theme_id, stock_id, mapping_source, confidence_score, is_primary, is_active, created_at, updated_at)
                VALUES (:theme_id, :stock_id, 'supply_event', 1.0, 0, 1, :created_at, :updated_at)
                """
            ),
            {"theme_id": theme_id, "stock_id": stock_id, "created_at": now, "updated_at": now},
        )
        mapping_id = int(
            self.db.execute(
                text("SELECT id FROM market_theme_stocks WHERE theme_id=:theme_id AND stock_id=:stock_id"),
                {"theme_id": theme_id, "stock_id": stock_id},
            ).mappings().first()["id"]
        )
        print(f"[theme-stock-sync] created theme_id={theme_id} stock_id={stock_id} source=supply_event")
        return ThemeStockSyncResult(status="created", mapping_id=mapping_id)

    def _sync_remove_theme_stock_link_from_event(self, *, event_id: int, theme_id: int, stock_id: int, now: str) -> ThemeStockSyncResult:
        existing = self.db.execute(
            text(
                """
                SELECT id, mapping_source, is_primary, is_active
                FROM market_theme_stocks
                WHERE theme_id=:theme_id AND stock_id=:stock_id
                LIMIT 1
                """
            ),
            {"theme_id": theme_id, "stock_id": stock_id},
        ).mappings().first()
        if not existing:
            return ThemeStockSyncResult(status="skipped", reason="link_not_found")
        mapping_id = int(existing["id"])
        if (existing["mapping_source"] or "") == "manual":
            print(f"[theme-stock-sync] skipped manual protected theme_id={theme_id} stock_id={stock_id}")
            return ThemeStockSyncResult(status="skipped", reason="manual_link_protected", mapping_id=mapping_id)
        if int(existing["is_primary"] or 0) == 1:
            return ThemeStockSyncResult(status="skipped", reason="primary_link_protected", mapping_id=mapping_id)
        if int(existing["is_active"] or 0) != 1:
            return ThemeStockSyncResult(status="skipped", reason="already_inactive", mapping_id=mapping_id)

        other_reference = self.db.execute(
            text(
                """
                SELECT l.id
                FROM market_trend_event_theme_links l
                JOIN market_trend_events e ON e.id=l.event_id
                WHERE l.market_theme_id=:theme_id
                  AND e.stock_id=:stock_id
                  AND l.is_active=1
                  AND e.is_active=1
                  AND l.event_id<>:event_id
                LIMIT 1
                """
            ),
            {"theme_id": theme_id, "stock_id": stock_id, "event_id": event_id},
        ).mappings().first()
        if other_reference:
            return ThemeStockSyncResult(status="skipped", reason="referenced_by_other_supply_event", mapping_id=mapping_id)

        self.db.execute(
            text("UPDATE market_theme_stocks SET is_active=0, updated_at=:updated_at WHERE id=:mapping_id"),
            {"mapping_id": mapping_id, "updated_at": now},
        )
        print(f"[theme-stock-sync] deactivated theme_id={theme_id} stock_id={stock_id}")
        return ThemeStockSyncResult(status="deactivated", mapping_id=mapping_id)

    def delete_market_event(self, event_id: int) -> KiwoomMarketEventDeleteResponse:
        now = now_kst()
        existing = self.db.execute(
            text("SELECT id, stock_id FROM market_trend_events WHERE id=:event_id AND detection_source IN ('kiwoom_condition', 'manual')"),
            {"event_id": event_id},
        ).mappings().first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="\uC218\uAE09 \uC774\uBCA4\uD2B8 \uD6C4\uBCF4\uB97C \uCC3E\uC744 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4.")

        linked_theme_rows = self.db.execute(
            text(
                """
                SELECT market_theme_id
                FROM market_trend_event_theme_links
                WHERE event_id=:event_id AND is_active=1
                """
            ),
            {"event_id": event_id},
        ).mappings().all()
        stock_id = int(existing["stock_id"])

        self.db.execute(
            text("UPDATE market_trend_events SET is_active=0, deleted_at=:deleted_at, updated_at=:updated_at WHERE id=:event_id"),
            {"event_id": event_id, "deleted_at": now, "updated_at": now},
        )
        self.db.execute(
            text(
                """
                UPDATE market_trend_event_theme_links
                SET is_active=0, deleted_at=:deleted_at, updated_at=:updated_at
                WHERE event_id=:event_id AND is_active=1
                """
            ),
            {"event_id": event_id, "deleted_at": now, "updated_at": now},
        )
        sync_summary = ThemeStockSyncSummary()
        for linked_theme in linked_theme_rows:
            try:
                sync_result = self._sync_remove_theme_stock_link_from_event(
                    event_id=event_id,
                    theme_id=int(linked_theme["market_theme_id"]),
                    stock_id=stock_id,
                    now=now,
                )
                if sync_result.status == "deactivated":
                    sync_summary.deactivated += 1
                elif sync_result.status == "skipped":
                    sync_summary.skipped += 1
            except Exception as exc:
                sync_summary.failed += 1
                print(f"[theme-stock-sync] failed delete event_id={event_id} reason={exc}")
        self.db.commit()
        return KiwoomMarketEventDeleteResponse(success=True, event_id=event_id, theme_stock_sync=sync_summary)

    def list_market_event_themes(self, event_id: int) -> KiwoomMarketEventThemeLinkListResponse:
        rows = self.db.execute(
            text(
                """
                SELECT l.id AS link_id, l.event_id, l.market_theme_id, t.theme_name, l.link_reason, l.user_memo,
                       l.is_primary, l.created_at, l.updated_at
                FROM market_trend_event_theme_links l
                JOIN market_themes t ON t.id=l.market_theme_id
                WHERE l.event_id=:event_id
                  AND l.is_active=1
                ORDER BY l.is_primary DESC, l.id DESC
                """
            ),
            {"event_id": event_id},
        ).mappings().all()
        return KiwoomMarketEventThemeLinkListResponse(items=[KiwoomMarketEventThemeLinkItemOut(**dict(r)) for r in rows])

    def add_market_event_theme(self, event_id: int, payload: KiwoomMarketEventThemeLinkAddRequest) -> KiwoomMarketEventThemeLinkAddResponse:
        now = now_kst()
        event_row = self.db.execute(
            text("SELECT id FROM market_trend_events WHERE id=:event_id AND is_active=1 AND detection_source IN ('kiwoom_condition', 'manual')"),
            {"event_id": event_id},
        ).mappings().first()
        if not event_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수급 이벤트 후보를 찾을 수 없습니다.")
        theme_row = self.db.execute(
            text(
                """
                SELECT id, theme_name
                FROM market_themes
                WHERE id=:theme_id
                  AND is_active=1
                  AND COALESCE(theme_level, 'THEME')='THEME'
                """
            ),
            {"theme_id": payload.market_theme_id},
        ).mappings().first()
        if not theme_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="테마를 찾을 수 없습니다.")

        existing = self.db.execute(
            text("SELECT id FROM market_trend_event_theme_links WHERE event_id=:event_id AND market_theme_id=:theme_id LIMIT 1"),
            {"event_id": event_id, "theme_id": payload.market_theme_id},
        ).mappings().first()
        if existing:
            link_id = int(existing["id"])
            self.db.execute(
                text(
                    """
                    UPDATE market_trend_event_theme_links
                    SET is_active=1, deleted_at=NULL, link_reason=:link_reason, user_memo=:user_memo,
                        is_primary=:is_primary, updated_at=:updated_at
                    WHERE id=:id
                    """
                ),
                {
                    "id": link_id,
                    "link_reason": payload.link_reason,
                    "user_memo": payload.user_memo,
                    "is_primary": int(payload.is_primary or 0),
                    "updated_at": now,
                },
            )
        else:
            self.db.execute(
                text(
                    """
                    INSERT INTO market_trend_event_theme_links
                    (event_id, market_theme_id, link_reason, user_memo, is_primary, is_active, created_at, updated_at, deleted_at)
                    VALUES (:event_id, :theme_id, :link_reason, :user_memo, :is_primary, 1, :created_at, :updated_at, NULL)
                    """
                ),
                {
                    "event_id": event_id,
                    "theme_id": payload.market_theme_id,
                    "link_reason": payload.link_reason,
                    "user_memo": payload.user_memo,
                    "is_primary": int(payload.is_primary or 0),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            link_id = int(
                self.db.execute(
                    text("SELECT id FROM market_trend_event_theme_links WHERE event_id=:event_id AND market_theme_id=:theme_id"),
                    {"event_id": event_id, "theme_id": payload.market_theme_id},
                ).mappings().first()["id"]
            )

        theme_stock_sync = None
        try:
            theme_stock_sync = self._sync_theme_stock_link_from_event(
                event_id=event_id,
                theme_id=int(payload.market_theme_id),
                now=now,
            )
        except Exception as exc:
            print(f"[theme-stock-sync] failed add event_id={event_id} theme_id={payload.market_theme_id} reason={exc}")
            theme_stock_sync = ThemeStockSyncResult(status="failed", reason=str(exc))
        self.db.commit()
        row = self.db.execute(
            text(
                """
                SELECT l.id AS link_id, l.event_id, l.market_theme_id, t.theme_name, l.link_reason, l.user_memo,
                       l.is_primary, l.created_at, l.updated_at
                FROM market_trend_event_theme_links l
                JOIN market_themes t ON t.id=l.market_theme_id
                WHERE l.id=:link_id
                """
            ),
            {"link_id": link_id},
        ).mappings().first()
        return KiwoomMarketEventThemeLinkAddResponse(success=True, item=KiwoomMarketEventThemeLinkItemOut(**dict(row)), theme_stock_sync=theme_stock_sync)

    def remove_market_event_theme(self, event_id: int, link_id: int) -> KiwoomMarketEventThemeLinkDeleteResponse:
        now = now_kst()
        row = self.db.execute(
            text(
                """
                SELECT l.id, l.market_theme_id, e.stock_id
                FROM market_trend_event_theme_links l
                JOIN market_trend_events e ON e.id=l.event_id
                WHERE l.id=:link_id AND l.event_id=:event_id AND l.is_active=1
                """
            ),
            {"link_id": link_id, "event_id": event_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="\uD14C\uB9C8 \uC5F0\uACB0\uC744 \uCC3E\uC744 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4.")
        self.db.execute(
            text("UPDATE market_trend_event_theme_links SET is_active=0, deleted_at=:deleted_at, updated_at=:updated_at WHERE id=:id"),
            {"id": link_id, "deleted_at": now, "updated_at": now},
        )
        theme_stock_sync = None
        try:
            theme_stock_sync = self._sync_remove_theme_stock_link_from_event(
                event_id=event_id,
                theme_id=int(row["market_theme_id"]),
                stock_id=int(row["stock_id"]),
                now=now,
            )
        except Exception as exc:
            print(f"[theme-stock-sync] failed remove event_id={event_id} link_id={link_id} reason={exc}")
            theme_stock_sync = ThemeStockSyncResult(status="failed", reason=str(exc))
        self.db.commit()
        return KiwoomMarketEventThemeLinkDeleteResponse(success=True, link_id=link_id, theme_stock_sync=theme_stock_sync)
    def refresh_market_theme_returns(self, payload: MarketThemeReturnRefreshRequest) -> MarketThemeReturnRefreshResponse:
        total_started_at = time.perf_counter()
        refreshed_at = now_kst()
        return_date = refreshed_at[:10]
        provider = KiwoomRestMarketIndicatorProvider()
        rest_diagnostics_before = KiwoomRestClient.diagnostics_snapshot()
        auth_diagnostics_before = KiwoomAuthClient.diagnostics_snapshot()
        themes = self._list_return_refresh_themes(payload)
        items: list[MarketThemeReturnRefreshItem] = []
        inserted_count = 0
        updated_count = 0
        total_stock_count = 0
        total_success_count = 0
        total_failed_count = 0

        theme_ids = [int(theme["theme_id"]) for theme in themes]
        link_rows = self._list_active_theme_return_stock_links(theme_ids)
        links_by_theme: dict[int, list[dict[str, object]]] = defaultdict(list)
        unique_stocks: dict[int, dict[str, object]] = {}
        for row in link_rows:
            theme_id = int(row["theme_id"])
            stock_id = int(row["stock_id"])
            links_by_theme[theme_id].append(row)
            unique_stocks.setdefault(stock_id, {
                "stock_id": stock_id,
                "stock_code": row.get("stock_code"),
                "stock_name": row.get("stock_name"),
            })

        price_started_at = time.perf_counter()
        stock_return_cache: dict[int, dict[str, object]] = {}
        for stock_id, stock in unique_stocks.items():
            stock_return_cache[stock_id] = self._fetch_theme_stock_return(provider, stock, return_date)
        price_fetch_ms = int((time.perf_counter() - price_started_at) * 1000)
        price_api_call_count = len(unique_stocks)

        calc_started_at = time.perf_counter()
        theme_results: list[dict[str, object]] = []
        for theme in themes:
            theme_id = int(theme["theme_id"])
            stocks = links_by_theme.get(theme_id, [])
            stock_results = [dict(stock_return_cache[int(stock["stock_id"])]) for stock in stocks if int(stock["stock_id"]) in stock_return_cache]

            stock_count = len(stocks)
            success_results = [row for row in stock_results if row.get("data_status") == "success" and row.get("change_rate") is not None]
            failed_count = stock_count - len(success_results)
            total_stock_count += stock_count
            total_success_count += len(success_results)
            total_failed_count += failed_count

            if not success_results:
                theme_results.append({
                    "theme_id": theme_id,
                    "theme_name": str(theme["theme_name"]),
                    "stock_count": stock_count,
                    "success_stock_count": 0,
                    "failed_stock_count": failed_count,
                    "stock_results": stock_results,
                    "avg_change_rate": None,
                    "total_trading_value": 0,
                    "total_trading_value_100m": None,
                    "rising_count": 0,
                    "falling_count": 0,
                    "flat_count": 0,
                })
                continue

            change_rates = [float(row["change_rate"]) for row in success_results if row.get("change_rate") is not None]
            avg_change_rate = round(sum(change_rates) / len(change_rates), 4) if change_rates else None
            total_trading_value = sum(int(row.get("trading_value") or 0) for row in success_results)
            total_trading_value_100m = round(total_trading_value / 100_000_000, 4) if total_trading_value else 0.0
            rising_count = sum(1 for rate in change_rates if rate > 0)
            falling_count = sum(1 for rate in change_rates if rate < 0)
            flat_count = sum(1 for rate in change_rates if rate == 0)

            theme_results.append({
                "theme_id": theme_id,
                "theme_name": str(theme["theme_name"]),
                "stock_count": stock_count,
                "success_stock_count": len(success_results),
                "failed_stock_count": failed_count,
                "stock_results": stock_results,
                "avg_change_rate": avg_change_rate,
                "total_trading_value": total_trading_value,
                "total_trading_value_100m": total_trading_value_100m,
                "rising_count": rising_count,
                "falling_count": falling_count,
                "flat_count": flat_count,
            })
        calc_ms = int((time.perf_counter() - calc_started_at) * 1000)

        db_started_at = time.perf_counter()
        for result in theme_results:
            theme_id = int(result["theme_id"])
            stock_count = int(result["stock_count"])
            success_stock_count = int(result["success_stock_count"])
            failed_count = int(result["failed_stock_count"])
            avg_change_rate = result["avg_change_rate"]
            total_trading_value_100m = result["total_trading_value_100m"]
            if success_stock_count <= 0:
                self._delete_market_theme_daily_return(theme_id=theme_id, return_date=return_date)
                items.append(MarketThemeReturnRefreshItem(
                    theme_id=theme_id,
                    theme_name=str(result["theme_name"]),
                    return_date=return_date,
                    avg_change_rate=None,
                    stock_count=stock_count,
                    success_stock_count=0,
                    failed_stock_count=failed_count,
                    total_trading_value_100m=None,
                    save_action="skipped",
                ))
                continue

            self._delete_market_theme_stock_daily_returns(theme_id=theme_id, return_date=return_date)
            daily_return_id, save_action = self._upsert_market_theme_daily_return(
                theme_id=theme_id,
                return_date=return_date,
                avg_change_rate=avg_change_rate if avg_change_rate is None else float(avg_change_rate),
                stock_count=stock_count,
                success_stock_count=success_stock_count,
                failed_stock_count=failed_count,
                rising_stock_count=int(result["rising_count"]),
                falling_stock_count=int(result["falling_count"]),
                flat_stock_count=int(result["flat_count"]),
                total_trading_value=int(result["total_trading_value"]),
                total_trading_value_100m=total_trading_value_100m if total_trading_value_100m is None else float(total_trading_value_100m),
                now=refreshed_at,
            )
            for stock_result in result["stock_results"]:
                self._upsert_market_theme_stock_daily_return(daily_return_id=daily_return_id, theme_id=theme_id, return_date=return_date, row=stock_result, now=refreshed_at)

            if save_action == "inserted":
                inserted_count += 1
            elif save_action == "updated":
                updated_count += 1
            items.append(MarketThemeReturnRefreshItem(
                theme_id=theme_id,
                theme_name=str(result["theme_name"]),
                return_date=return_date,
                avg_change_rate=avg_change_rate if avg_change_rate is None else float(avg_change_rate),
                stock_count=stock_count,
                success_stock_count=success_stock_count,
                failed_stock_count=failed_count,
                total_trading_value_100m=total_trading_value_100m if total_trading_value_100m is None else float(total_trading_value_100m),
                save_action=save_action,
            ))

        self.db.commit()
        db_upsert_ms = int((time.perf_counter() - db_started_at) * 1000)
        total_ms = int((time.perf_counter() - total_started_at) * 1000)
        rest_diagnostics_after = KiwoomRestClient.diagnostics_snapshot()
        auth_diagnostics_after = KiwoomAuthClient.diagnostics_snapshot()
        rest_post_calls = int(rest_diagnostics_after.get("rest_post_calls", 0)) - int(rest_diagnostics_before.get("rest_post_calls", 0))
        auth_token_issue_count = int(auth_diagnostics_after.get("auth_token_issue_count", 0)) - int(auth_diagnostics_before.get("auth_token_issue_count", 0))
        ka10001_calls = int(rest_diagnostics_after.get("ka10001_calls", 0)) - int(rest_diagnostics_before.get("ka10001_calls", 0))
        ka10015_calls = int(rest_diagnostics_after.get("ka10015_calls", 0)) - int(rest_diagnostics_before.get("ka10015_calls", 0))
        message = f"\ud14c\ub9c8\ub4f1\ub77d\ub960 \uac31\uc2e0 \uc644\ub8cc: {len(themes)}\uac1c \ud14c\ub9c8, \uace0\uc720 {len(unique_stocks)}\uac1c \uc885\ubaa9, {total_stock_count}\uac74 \ubc18\uc601"
        if total_failed_count:
            message = f"\ud14c\ub9c8\ub4f1\ub77d\ub960 \uac31\uc2e0 \uc644\ub8cc: {len(themes)}\uac1c \ud14c\ub9c8, \uace0\uc720 {len(unique_stocks)}\uac1c \uc885\ubaa9, {total_failed_count}\uac1c \uc885\ubaa9 \uc870\ud68c \uc2e4\ud328"
        print(
            "[theme-return-refresh] "
            f"themes={len(themes)} links={len(link_rows)} unique_stocks={len(unique_stocks)} "
            f"price_api_calls={price_api_call_count} rest_post_calls={rest_post_calls} "
            f"auth_token_issue_count={auth_token_issue_count} ka10001_calls={ka10001_calls} ka10015_calls={ka10015_calls} "
            f"price_fetch_ms={price_fetch_ms} "
            f"calc_ms={calc_ms} db_upsert_ms={db_upsert_ms} total_ms={total_ms}"
        )
        return MarketThemeReturnRefreshResponse(
            success=True,
            return_date=return_date,
            refreshed_at=refreshed_at,
            theme_count=len(themes),
            stock_count=total_stock_count,
            success_stock_count=total_success_count,
            failed_stock_count=total_failed_count,
            inserted_count=inserted_count,
            updated_count=updated_count,
            items=items,
            message=message,
            theme_stock_link_count=len(link_rows),
            unique_stock_count=len(unique_stocks),
            price_api_call_count=price_api_call_count,
            rest_post_calls=rest_post_calls,
            auth_token_issue_count=auth_token_issue_count,
            ka10001_calls=ka10001_calls,
            ka10015_calls=ka10015_calls,
            price_fetch_ms=price_fetch_ms,
            calc_ms=calc_ms,
            db_upsert_ms=db_upsert_ms,
            total_ms=total_ms,
        )

    def get_market_theme_latest_return(self, theme_id: int) -> MarketThemeLatestReturnResponse:
        theme = self.db.execute(
            text(
                """
                SELECT t.id, t.theme_name, p.theme_name AS theme_group_name
                FROM market_themes t
                LEFT JOIN market_themes p ON p.id=t.parent_theme_id
                WHERE t.id=:theme_id
                """
            ),
            {"theme_id": theme_id},
        ).mappings().first()
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="테마를 찾을 수 없습니다.")

        latest = self.db.execute(
            text(
                """
                SELECT id, return_date, avg_change_rate, stock_count, success_stock_count, failed_stock_count,
                       rising_stock_count, falling_stock_count, flat_stock_count, total_trading_value_100m, last_refreshed_at
                FROM market_theme_daily_returns
                WHERE theme_id=:theme_id
                ORDER BY return_date DESC, last_refreshed_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"theme_id": theme_id},
        ).mappings().first()
        if not latest:
            stock_count = len(self._list_active_theme_return_stocks(theme_id))
            return MarketThemeLatestReturnResponse(
                theme_id=theme_id,
                theme_name=str(theme["theme_name"]),
                theme_group_name=theme["theme_group_name"],
                stock_count=stock_count,
                stocks=[],
            )

        stock_rows = self.db.execute(
            text(
                """
                SELECT stock_id, stock_code, stock_name, trading_value_100m, change_rate, current_price, data_status, error_message
                FROM market_theme_stock_daily_returns
                WHERE theme_daily_return_id=:daily_return_id
                ORDER BY data_status='success' DESC, COALESCE(trading_value, 0) DESC, stock_name ASC
                """
            ),
            {"daily_return_id": int(latest["id"])},
        ).mappings().all()
        return MarketThemeLatestReturnResponse(
            theme_id=theme_id,
            theme_name=str(theme["theme_name"]),
            theme_group_name=theme["theme_group_name"],
            return_date=latest["return_date"],
            avg_change_rate=latest["avg_change_rate"],
            snapshot_at=latest["last_refreshed_at"],
            stock_count=int(latest["stock_count"] or 0),
            success_stock_count=int(latest["success_stock_count"] or 0),
            failed_stock_count=int(latest["failed_stock_count"] or 0),
            rising_stock_count=int(latest["rising_stock_count"] or 0),
            falling_stock_count=int(latest["falling_stock_count"] or 0),
            flat_stock_count=int(latest["flat_stock_count"] or 0),
            total_trading_value_100m=latest["total_trading_value_100m"],
            stocks=[MarketThemeReturnStockItem(**dict(row)) for row in stock_rows],
        )

    def get_market_theme_monthly_returns(
        self,
        *,
        month: str,
        active_only: bool = True,
        theme_group_id: int | None = None,
        keyword: str | None = None,
        limit: int | None = None,
        lookback_days: int = 0,
    ) -> MarketThemeMonthlyReturnResponse:
        try:
            year, month_num = [int(part) for part in month.split("-", 1)]
            start = date(year, month_num, 1)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month는 YYYY-MM 형식이어야 합니다.")
        end = date(start.year, start.month, monthrange(start.year, start.month)[1])
        if lookback_days and lookback_days > 0:
            start = max(start, date.today() - timedelta(days=lookback_days - 1))

        params: dict[str, object] = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        where = ["COALESCE(t.theme_level, 'THEME')='THEME'"]
        if active_only:
            where.append("t.is_active=1")
        if theme_group_id is not None:
            where.append("t.parent_theme_id=:theme_group_id")
            params["theme_group_id"] = int(theme_group_id)
        if keyword:
            where.append("(LOWER(t.theme_name) LIKE :keyword OR LOWER(COALESCE(p.theme_name, '')) LIKE :keyword OR LOWER(COALESCE(t.keywords, '')) LIKE :keyword)")
            params["keyword"] = f"%{keyword.lower()}%"
        sql_where = " AND ".join(where)
        rows = self.db.execute(
            text(
                f"""
                SELECT t.id AS theme_id, t.theme_name, t.parent_theme_id AS theme_group_id,
                       p.theme_name AS theme_group_name, d.return_date, d.avg_change_rate,
                       d.total_trading_value_100m, d.rising_stock_count, d.falling_stock_count, d.flat_stock_count
                FROM market_themes t
                LEFT JOIN market_themes p ON p.id=t.parent_theme_id
                LEFT JOIN market_theme_daily_returns d
                  ON d.theme_id=t.id AND d.return_date BETWEEN :start_date AND :end_date
                WHERE {sql_where}
                ORDER BY t.is_supply_theme DESC, COALESCE(p.theme_name, '미지정') ASC, t.sort_order ASC, t.theme_name ASC, d.return_date ASC
                """
            ),
            params,
        ).mappings().all()

        grouped: dict[int, dict[str, object]] = {}
        for row in rows:
            theme_id = int(row["theme_id"])
            item = grouped.setdefault(theme_id, {
                "theme_id": theme_id,
                "theme_name": str(row["theme_name"]),
                "theme_group_id": row["theme_group_id"],
                "theme_group_name": row["theme_group_name"],
                "daily_returns": [],
            })
            if row["return_date"]:
                item["daily_returns"].append(MarketThemeMonthlyReturnDailyItem(
                    return_date=str(row["return_date"]),
                    avg_change_rate=row["avg_change_rate"],
                    total_trading_value_100m=row["total_trading_value_100m"],
                    rising_stock_count=int(row["rising_stock_count"] or 0),
                    falling_stock_count=int(row["falling_stock_count"] or 0),
                    flat_stock_count=int(row["flat_stock_count"] or 0),
                ))

        themes: list[MarketThemeMonthlyReturnThemeItem] = []
        for item in grouped.values():
            daily_returns = item["daily_returns"]
            rates = [float(day.avg_change_rate) for day in daily_returns if day.avg_change_rate is not None]
            compound: float | None = None
            if rates:
                acc = 1.0
                for rate in rates:
                    acc *= 1 + (rate / 100)
                compound = round((acc - 1) * 100, 4)
            sum_return = round(sum(rates), 4) if rates else None
            trading_value = sum(float(day.total_trading_value_100m or 0) for day in daily_returns)
            themes.append(MarketThemeMonthlyReturnThemeItem(
                theme_id=int(item["theme_id"]),
                theme_name=str(item["theme_name"]),
                theme_group_id=item["theme_group_id"],
                theme_group_name=item["theme_group_name"],
                monthly_compound_return=compound,
                monthly_sum_return=sum_return,
                total_trading_value_100m=round(trading_value, 4),
                rising_days=sum(1 for rate in rates if rate > 0),
                falling_days=sum(1 for rate in rates if rate < 0),
                flat_days=sum(1 for rate in rates if rate == 0),
                data_days=len(rates),
                daily_returns=daily_returns,
            ))

        themes.sort(key=lambda row: (row.monthly_compound_return is None, -(row.monthly_compound_return or -999999), row.theme_name))
        if limit and limit > 0:
            themes = themes[:limit]

        def to_top(theme: MarketThemeMonthlyReturnThemeItem | None) -> MarketThemeMonthlyReturnSummaryTopItem | None:
            if theme is None:
                return None
            return MarketThemeMonthlyReturnSummaryTopItem(
                theme_id=theme.theme_id,
                theme_name=theme.theme_name,
                monthly_compound_return=theme.monthly_compound_return,
                total_trading_value_100m=theme.total_trading_value_100m,
            )

        with_return = [theme for theme in themes if theme.monthly_compound_return is not None]
        summary = MarketThemeMonthlyReturnSummary(
            top_rising_theme=to_top(max(with_return, key=lambda x: x.monthly_compound_return or 0) if with_return else None),
            top_falling_theme=to_top(min(with_return, key=lambda x: x.monthly_compound_return or 0) if with_return else None),
            top_trading_value_theme=to_top(max(themes, key=lambda x: x.total_trading_value_100m or 0) if themes else None),
            rising_day_theme=to_top(max(themes, key=lambda x: x.rising_days) if themes else None),
        )
        return MarketThemeMonthlyReturnResponse(
            month=month,
            active_only=active_only,
            display_start_date=start.isoformat(),
            display_end_date=end.isoformat(),
            themes=themes,
            summary=summary,
        )

    def get_market_theme_range_returns(
        self,
        *,
        end_date: str,
        days: int = 30,
        active_only: bool = True,
        theme_group_id: int | None = None,
        keyword: str | None = None,
        limit: int | None = None,
    ) -> MarketThemeMonthlyReturnResponse:
        try:
            end = date.fromisoformat(end_date)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date는 YYYY-MM-DD 형식이어야 합니다.")
        normalized_days = max(1, min(int(days or 30), 120))
        start = end - timedelta(days=normalized_days - 1)
        calc_start = start - timedelta(days=29)
        params: dict[str, object] = {
            "start_date": start.isoformat(),
            "calc_start_date": calc_start.isoformat(),
            "end_date": end.isoformat(),
        }
        where = ["COALESCE(t.theme_level, 'THEME')='THEME'"]
        if active_only:
            where.append("t.is_active=1")
        if theme_group_id is not None:
            where.append("t.parent_theme_id=:theme_group_id")
            params["theme_group_id"] = int(theme_group_id)
        if keyword:
            where.append("(LOWER(t.theme_name) LIKE :keyword OR LOWER(COALESCE(p.theme_name, '')) LIKE :keyword OR LOWER(COALESCE(t.keywords, '')) LIKE :keyword)")
            params["keyword"] = f"%{keyword.lower()}%"
        sql_where = " AND ".join(where)
        rows = self.db.execute(
            text(
                f"""
                SELECT t.id AS theme_id, t.theme_name, t.parent_theme_id AS theme_group_id,
                       p.theme_name AS theme_group_name, d.return_date, d.avg_change_rate,
                       d.total_trading_value_100m, d.rising_stock_count, d.falling_stock_count, d.flat_stock_count
                FROM market_themes t
                LEFT JOIN market_themes p ON p.id=t.parent_theme_id
                LEFT JOIN market_theme_daily_returns d
                  ON d.theme_id=t.id AND d.return_date BETWEEN :calc_start_date AND :end_date
                WHERE {sql_where}
                ORDER BY t.is_supply_theme DESC, COALESCE(p.theme_name, '미지정') ASC, t.sort_order ASC, t.theme_name ASC, d.return_date ASC
                """
            ),
            params,
        ).mappings().all()

        grouped: dict[int, dict[str, object]] = {}
        for row in rows:
            theme_id = int(row["theme_id"])
            item = grouped.setdefault(theme_id, {
                "theme_id": theme_id,
                "theme_name": str(row["theme_name"]),
                "theme_group_id": row["theme_group_id"],
                "theme_group_name": row["theme_group_name"],
                "daily_returns": [],
            })
            if row["return_date"]:
                item["daily_returns"].append(MarketThemeMonthlyReturnDailyItem(
                    return_date=str(row["return_date"]),
                    avg_change_rate=row["avg_change_rate"],
                    total_trading_value_100m=row["total_trading_value_100m"],
                    rising_stock_count=int(row["rising_stock_count"] or 0),
                    falling_stock_count=int(row["falling_stock_count"] or 0),
                    flat_stock_count=int(row["flat_stock_count"] or 0),
                ))

        themes: list[MarketThemeMonthlyReturnThemeItem] = []
        continuous_rising_by_theme: dict[int, int] = {}
        for item in grouped.values():
            all_daily_returns = item["daily_returns"]
            all_rate_by_date = {
                date.fromisoformat(day.return_date): float(day.avg_change_rate)
                for day in all_daily_returns
                if day.avg_change_rate is not None
            }
            daily_returns: list[MarketThemeMonthlyReturnDailyItem] = []
            for day in all_daily_returns:
                day_date = date.fromisoformat(day.return_date)
                if day_date < start or day_date > end:
                    continue
                window_start = day_date - timedelta(days=29)
                window_rates = [
                    rate
                    for rate_date, rate in all_rate_by_date.items()
                    if window_start <= rate_date <= day_date
                ]
                daily_returns.append(
                    day.model_copy(
                        update={
                            "rolling_30d_change_rate": round(sum(window_rates), 4) if window_rates else None,
                        }
                    )
                )
            rates = [float(day.avg_change_rate) for day in daily_returns if day.avg_change_rate is not None]
            compound: float | None = None
            if rates:
                acc = 1.0
                for rate in rates:
                    acc *= 1 + (rate / 100)
                compound = round((acc - 1) * 100, 4)
            sum_return = round(sum(rates), 4) if rates else None
            trading_value = sum(float(day.total_trading_value_100m or 0) for day in daily_returns)
            continuous_rising = 0
            for day in reversed(daily_returns):
                if day.avg_change_rate is not None and float(day.avg_change_rate) > 0:
                    continuous_rising += 1
                else:
                    break
            theme_id = int(item["theme_id"])
            continuous_rising_by_theme[theme_id] = continuous_rising
            themes.append(MarketThemeMonthlyReturnThemeItem(
                theme_id=theme_id,
                theme_name=str(item["theme_name"]),
                theme_group_id=item["theme_group_id"],
                theme_group_name=item["theme_group_name"],
                monthly_compound_return=compound,
                monthly_sum_return=sum_return,
                period_compound_return=compound,
                period_sum_return=sum_return,
                total_trading_value_100m=round(trading_value, 4),
                rising_days=sum(1 for rate in rates if rate > 0),
                falling_days=sum(1 for rate in rates if rate < 0),
                flat_days=sum(1 for rate in rates if rate == 0),
                data_days=len(rates),
                daily_returns=daily_returns,
            ))

        themes.sort(key=lambda row: (row.monthly_compound_return is None, -(row.monthly_compound_return or -999999), row.theme_name))
        if limit and limit > 0:
            themes = themes[:limit]

        def to_top(theme: MarketThemeMonthlyReturnThemeItem | None) -> MarketThemeMonthlyReturnSummaryTopItem | None:
            if theme is None:
                return None
            continuous_rising = continuous_rising_by_theme.get(theme.theme_id, 0)
            return MarketThemeMonthlyReturnSummaryTopItem(
                theme_id=theme.theme_id,
                theme_name=theme.theme_name,
                monthly_compound_return=theme.monthly_compound_return,
                period_compound_return=theme.period_compound_return,
                total_trading_value_100m=theme.total_trading_value_100m,
                continuous_rising_days=continuous_rising,
            )

        with_return = [theme for theme in themes if theme.monthly_compound_return is not None]
        continuous_candidates = [theme for theme in themes if continuous_rising_by_theme.get(theme.theme_id, 0) > 0]
        top_continuous = max(continuous_candidates, key=lambda x: continuous_rising_by_theme.get(x.theme_id, 0)) if continuous_candidates else None
        summary = MarketThemeMonthlyReturnSummary(
            top_rising_theme=to_top(max(with_return, key=lambda x: x.monthly_compound_return or 0) if with_return else None),
            top_falling_theme=to_top(min(with_return, key=lambda x: x.monthly_compound_return or 0) if with_return else None),
            top_trading_value_theme=to_top(max(themes, key=lambda x: x.total_trading_value_100m or 0) if themes else None),
            rising_day_theme=to_top(max(themes, key=lambda x: x.rising_days) if themes else None),
            top_continuous_rising_theme=to_top(top_continuous),
        )
        return MarketThemeMonthlyReturnResponse(
            month=end.isoformat()[:7],
            end_date=end.isoformat(),
            days=normalized_days,
            active_only=active_only,
            display_start_date=start.isoformat(),
            display_end_date=end.isoformat(),
            themes=themes,
            summary=summary,
        )
    def get_market_theme_daily_return(self, theme_id: int, return_date: str) -> MarketThemeLatestReturnResponse:
        theme = self.db.execute(
            text(
                """
                SELECT t.id, t.theme_name, p.theme_name AS theme_group_name
                FROM market_themes t
                LEFT JOIN market_themes p ON p.id=t.parent_theme_id
                WHERE t.id=:theme_id
                """
            ),
            {"theme_id": theme_id},
        ).mappings().first()
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="테마를 찾을 수 없습니다.")
        daily = self.db.execute(
            text(
                """
                SELECT id, return_date, avg_change_rate, stock_count, success_stock_count, failed_stock_count,
                       rising_stock_count, falling_stock_count, flat_stock_count, total_trading_value_100m, last_refreshed_at
                FROM market_theme_daily_returns
                WHERE theme_id=:theme_id AND return_date=:return_date
                LIMIT 1
                """
            ),
            {"theme_id": theme_id, "return_date": return_date},
        ).mappings().first()
        if not daily:
            return MarketThemeLatestReturnResponse(
                theme_id=theme_id,
                theme_name=str(theme["theme_name"]),
                theme_group_name=theme["theme_group_name"],
                return_date=return_date,
                stock_count=len(self._list_active_theme_return_stocks(theme_id)),
                stocks=[],
            )
        stock_rows = self.db.execute(
            text(
                """
                SELECT stock_id, stock_code, stock_name, trading_value_100m, change_rate, current_price, data_status, error_message
                FROM market_theme_stock_daily_returns
                WHERE theme_daily_return_id=:daily_return_id
                ORDER BY data_status='success' DESC, COALESCE(trading_value, 0) DESC, stock_name ASC
                """
            ),
            {"daily_return_id": int(daily["id"])},
        ).mappings().all()
        return MarketThemeLatestReturnResponse(
            theme_id=theme_id,
            theme_name=str(theme["theme_name"]),
            theme_group_name=theme["theme_group_name"],
            return_date=daily["return_date"],
            avg_change_rate=daily["avg_change_rate"],
            snapshot_at=daily["last_refreshed_at"],
            stock_count=int(daily["stock_count"] or 0),
            success_stock_count=int(daily["success_stock_count"] or 0),
            failed_stock_count=int(daily["failed_stock_count"] or 0),
            rising_stock_count=int(daily["rising_stock_count"] or 0),
            falling_stock_count=int(daily["falling_stock_count"] or 0),
            flat_stock_count=int(daily["flat_stock_count"] or 0),
            total_trading_value_100m=daily["total_trading_value_100m"],
            stocks=[MarketThemeReturnStockItem(**dict(row)) for row in stock_rows],
        )
    def _list_return_refresh_themes(self, payload: MarketThemeReturnRefreshRequest) -> list[dict[str, object]]:
        params: dict[str, object] = {}
        where = "WHERE t.is_active=1 AND COALESCE(t.theme_level, 'THEME')='THEME'"
        if payload.scope == "selected" and payload.theme_ids:
            placeholders = []
            for idx, theme_id in enumerate(payload.theme_ids):
                key = f"theme_id_{idx}"
                placeholders.append(f":{key}")
                params[key] = int(theme_id)
            where += f" AND t.id IN ({', '.join(placeholders)})"
        rows = self.db.execute(
            text(
                f"""
                SELECT t.id AS theme_id, t.theme_name
                FROM market_themes t
                {where}
                ORDER BY t.is_supply_theme DESC, t.sort_order ASC, t.theme_name ASC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def _list_active_theme_return_stock_links(self, theme_ids: list[int]) -> list[dict[str, object]]:
        if not theme_ids:
            return []
        params: dict[str, object] = {}
        placeholders = []
        for idx, theme_id in enumerate(theme_ids):
            key = f"theme_id_{idx}"
            placeholders.append(f":{key}")
            params[key] = int(theme_id)
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    mts.theme_id,
                    s.id AS stock_id,
                    s.stock_code,
                    s.stock_name,
                    COALESCE(mts.is_primary, 0) AS is_primary
                FROM market_theme_stocks mts
                JOIN stocks s ON s.id=mts.stock_id
                WHERE mts.theme_id IN ({', '.join(placeholders)})
                  AND mts.is_active=1
                  AND COALESCE(s.is_active, 1)=1
                ORDER BY mts.theme_id ASC, mts.is_primary DESC, s.stock_name ASC
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def _list_active_theme_return_stocks(self, theme_id: int) -> list[dict[str, object]]:
        rows = self.db.execute(
            text(
                """
                SELECT s.id AS stock_id, s.stock_code, s.stock_name
                FROM market_theme_stocks mts
                JOIN stocks s ON s.id=mts.stock_id
                WHERE mts.theme_id=:theme_id
                  AND mts.is_active=1
                  AND COALESCE(s.is_active, 1)=1
                ORDER BY mts.is_primary DESC, s.stock_name ASC
                """
            ),
            {"theme_id": theme_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def _fetch_theme_stock_return(self, provider: KiwoomRestMarketIndicatorProvider, stock: dict[str, object], return_date: str) -> dict[str, object]:
        stock_code = normalize_stock_code(str(stock.get("stock_code") or ""))
        base_row = {
            "stock_id": int(stock["stock_id"]),
            "stock_code": stock_code,
            "stock_name": str(stock.get("stock_name") or stock_code),
            "change_rate": None,
            "trading_value": None,
            "trading_value_100m": None,
            "current_price": None,
            "data_status": "missing",
            "error_message": None,
        }
        if len(stock_code) != 6:
            base_row["data_status"] = "failed"
            base_row["error_message"] = "invalid_stock_code"
            return base_row
        try:
            basic = provider.get_stock_basic_info(stock_code=stock_code)
            # Theme return refresh needs only current price, change rate, and accumulated trading value.
            # ka10001 provides all three, so avoid the per-stock ka10015 daily-detail call here.
            change_rate = self._normalize_change_rate(basic.get("change_rate"))
            current_price = self._to_abs_int(basic.get("close_price"))
            trading_value = self._to_int_or_none(basic.get("trading_value"))
            if trading_value is None:
                try:
                    daily = provider.get_stock_daily_trade_detail(stock_code=stock_code, base_dt=return_date)
                    trading_value = self._to_int_or_none(daily.get("trading_value"))
                    current_price = current_price if current_price is not None else self._to_abs_int(daily.get("close_price"))
                except Exception:
                    trading_value = None
            if change_rate is None:
                base_row["data_status"] = "failed"
                base_row["error_message"] = "change_rate_missing"
                base_row["current_price"] = current_price
                base_row["trading_value"] = trading_value
                base_row["trading_value_100m"] = round(trading_value / 100_000_000, 4) if trading_value is not None else None
                return base_row
            base_row.update({
                "change_rate": change_rate,
                "trading_value": trading_value,
                "trading_value_100m": round(trading_value / 100_000_000, 4) if trading_value is not None else None,
                "current_price": current_price,
                "data_status": "success",
            })
            return base_row
        except Exception as exc:
            base_row["data_status"] = "failed"
            base_row["error_message"] = str(exc)[:500]
            return base_row

    def _upsert_market_theme_daily_return(
        self,
        *,
        theme_id: int,
        return_date: str,
        avg_change_rate: float | None,
        stock_count: int,
        success_stock_count: int,
        failed_stock_count: int,
        rising_stock_count: int,
        falling_stock_count: int,
        flat_stock_count: int,
        total_trading_value: int,
        total_trading_value_100m: float | None,
        now: str,
    ) -> tuple[int, str]:
        existing = self.db.execute(
            text("SELECT id FROM market_theme_daily_returns WHERE theme_id=:theme_id AND return_date=:return_date"),
            {"theme_id": theme_id, "return_date": return_date},
        ).mappings().first()
        params = {
            "theme_id": theme_id,
            "return_date": return_date,
            "avg_change_rate": avg_change_rate,
            "stock_count": stock_count,
            "success_stock_count": success_stock_count,
            "failed_stock_count": failed_stock_count,
            "rising_stock_count": rising_stock_count,
            "falling_stock_count": falling_stock_count,
            "flat_stock_count": flat_stock_count,
            "total_trading_value": total_trading_value,
            "total_trading_value_100m": total_trading_value_100m,
            "now": now,
        }
        if existing:
            daily_return_id = int(existing["id"])
            self.db.execute(
                text(
                    """
                    UPDATE market_theme_daily_returns
                    SET avg_change_rate=:avg_change_rate, stock_count=:stock_count,
                        success_stock_count=:success_stock_count, failed_stock_count=:failed_stock_count,
                        rising_stock_count=:rising_stock_count, falling_stock_count=:falling_stock_count,
                        flat_stock_count=:flat_stock_count, total_trading_value=:total_trading_value,
                        total_trading_value_100m=:total_trading_value_100m,
                        last_refreshed_at=:now, refresh_count=refresh_count+1, updated_at=:now
                    WHERE id=:id
                    """
                ),
                {**params, "id": daily_return_id},
            )
            return daily_return_id, "updated"
        self.db.execute(
            text(
                """
                INSERT INTO market_theme_daily_returns
                (theme_id, return_date, avg_change_rate, stock_count, success_stock_count, failed_stock_count,
                 rising_stock_count, falling_stock_count, flat_stock_count, total_trading_value, total_trading_value_100m,
                 data_source, first_created_at, last_refreshed_at, refresh_count, created_at, updated_at)
                VALUES
                (:theme_id, :return_date, :avg_change_rate, :stock_count, :success_stock_count, :failed_stock_count,
                 :rising_stock_count, :falling_stock_count, :flat_stock_count, :total_trading_value, :total_trading_value_100m,
                 'kiwoom', :now, :now, 1, :now, :now)
                """
            ),
            params,
        )
        daily_return_id = int(self.db.execute(
            text("SELECT id FROM market_theme_daily_returns WHERE theme_id=:theme_id AND return_date=:return_date"),
            {"theme_id": theme_id, "return_date": return_date},
        ).mappings().first()["id"])
        return daily_return_id, "inserted"

    def _delete_market_theme_stock_daily_returns(self, *, theme_id: int, return_date: str) -> None:
        self.db.execute(
            text(
                """
                DELETE FROM market_theme_stock_daily_returns
                WHERE theme_id=:theme_id AND return_date=:return_date
                """
            ),
            {"theme_id": theme_id, "return_date": return_date},
        )

    def _delete_market_theme_daily_return(self, *, theme_id: int, return_date: str) -> None:
        self._delete_market_theme_stock_daily_returns(theme_id=theme_id, return_date=return_date)
        self.db.execute(
            text(
                """
                DELETE FROM market_theme_daily_returns
                WHERE theme_id=:theme_id AND return_date=:return_date
                """
            ),
            {"theme_id": theme_id, "return_date": return_date},
        )

    def _upsert_market_theme_stock_daily_return(self, *, daily_return_id: int, theme_id: int, return_date: str, row: dict[str, object], now: str) -> None:
        existing = self.db.execute(
            text(
                """
                SELECT id FROM market_theme_stock_daily_returns
                WHERE theme_id=:theme_id AND stock_id=:stock_id AND return_date=:return_date
                """
            ),
            {"theme_id": theme_id, "stock_id": int(row["stock_id"]), "return_date": return_date},
        ).mappings().first()
        params = {
            "theme_daily_return_id": daily_return_id,
            "theme_id": theme_id,
            "stock_id": int(row["stock_id"]),
            "stock_code": row.get("stock_code"),
            "stock_name": row.get("stock_name"),
            "return_date": return_date,
            "change_rate": row.get("change_rate"),
            "trading_value": row.get("trading_value"),
            "trading_value_100m": row.get("trading_value_100m"),
            "current_price": row.get("current_price"),
            "data_status": row.get("data_status") or "missing",
            "error_message": row.get("error_message"),
            "now": now,
        }
        if existing:
            self.db.execute(
                text(
                    """
                    UPDATE market_theme_stock_daily_returns
                    SET theme_daily_return_id=:theme_daily_return_id, stock_code=:stock_code, stock_name=:stock_name,
                        change_rate=:change_rate, trading_value=:trading_value, trading_value_100m=:trading_value_100m,
                        current_price=:current_price, data_status=:data_status, error_message=:error_message, updated_at=:now
                    WHERE id=:id
                    """
                ),
                {**params, "id": int(existing["id"])},
            )
            return
        self.db.execute(
            text(
                """
                INSERT INTO market_theme_stock_daily_returns
                (theme_daily_return_id, theme_id, stock_id, stock_code, stock_name, return_date, change_rate,
                 trading_value, trading_value_100m, current_price, data_status, error_message, created_at, updated_at)
                VALUES
                (:theme_daily_return_id, :theme_id, :stock_id, :stock_code, :stock_name, :return_date, :change_rate,
                 :trading_value, :trading_value_100m, :current_price, :data_status, :error_message, :now, :now)
                """
            ),
            params,
        )
