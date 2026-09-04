from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from calendar import monthrange
from datetime import date, datetime, timedelta
from threading import Lock
from typing import Callable

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.clients.kiwoom import KiwoomApiError
from backend.app.clients.kiwoom.kiwoom_auth_client import KiwoomAuthClient
from backend.app.clients.kiwoom.kiwoom_rest_client import KiwoomRestClient
from backend.app.core.config import now_kst
from backend.app.providers.market_data.kiwoom_rest_condition_provider import KiwoomRestConditionProvider
from backend.app.providers.market_data.kiwoom_rest_market_indicator_provider import KiwoomRestMarketIndicatorProvider
from backend.app.services.market_theme_return_prediction_service import MarketThemeReturnPredictionService
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
    MarketThemeReturnRecalculationPreview,
    MarketThemeReturnRecalculationResponse,
    MarketThemeReturnRefreshRequest,
    MarketThemeReturnRefreshResponse,
    MarketThemeReturnStockItem,
    MonthlySupplyClassificationDiagnostics,
    MonthlySupplySummary30d,
    MonthlySupplySummaryStockItem,
    MonthlySupplySummaryThemeItem,
    SupplyTopStockReturnPoint,
    SupplyTopStockReturnTrendItem,
    SupplyTopStockReturnTrendResponse,
    SupplyTopStockPriceReadiness,
    SupplyTopStockPriceCollectRequest,
    SupplyTopStockPriceCollectItem,
    SupplyTopStockPriceCollectResponse,
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
from backend.app.services.stock_price_service import StockPriceService
from backend.app.services.market_theme_flow_analysis_service import MarketThemeFlowAnalysisService
from backend.app.utils.stock_code import normalize_stock_code

logger = logging.getLogger(__name__)


class ExternalKiwoomService:
    _supply_price_collection_lock = Lock()
    _theme_return_recalculation_state_lock = Lock()
    _theme_return_recalculating_ids: set[int] = set()
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

    def _load_manual_rank_maps(self, start_date: str, end_date: str) -> dict[str, dict[int, int]]:
        rank_rows = self.db.execute(
            text(
                """
                SELECT trade_date, market_theme_id, manual_rank
                FROM daily_theme_flow_ranks
                WHERE trade_date BETWEEN :start_date AND :end_date
                """
            ),
            {"start_date": start_date, "end_date": end_date},
        ).mappings().all()
        rank_maps: dict[str, dict[int, int]] = {}
        for row in rank_rows:
            manual_rank = row.get("manual_rank")
            if manual_rank is None:
                continue
            value = int(manual_rank)
            if value <= 0:
                continue
            trade_date = str(row["trade_date"])
            rank_maps.setdefault(trade_date, {})[int(row["market_theme_id"])] = value
        return rank_maps

    def _apply_rank_overrides(
        self,
        trade_date: str,
        items: list[DailyThemeFlowSummaryItem],
        manual_map: dict[int, int] | None = None,
    ) -> list[DailyThemeFlowSummaryItem]:
        if not items:
            return []
        scored_items = self._with_theme_strength_scores(items)
        sorted_auto = sorted(scored_items, key=self._auto_theme_rank_sort_key)
        auto_rank_map = {item.market_theme_id: idx + 1 for idx, item in enumerate(sorted_auto)}
        if manual_map is None:
            manual_map = self._load_manual_rank_maps(trade_date, trade_date).get(trade_date, {})
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

    def _build_supply_theme_aggregation(self, start_date: date, end_date: date) -> dict[str, object]:
        """Resolve saved supply events through the current active stock-theme classification."""
        started_at = time.perf_counter()
        params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
        base_rows = self.db.execute(
            text(
                """
                SELECT
                    mte.id AS event_id,
                    mte.trade_date AS trade_date,
                    COALESCE(mte.stock_id, stock_by_code.id) AS stock_id,
                    COALESCE(mte.stock_code, stock_by_code.stock_code) AS stock_code,
                    COALESCE(mte.stock_name, stock_by_code.stock_name, mte.stock_code, '-') AS stock_name,
                    mte.change_rate AS change_rate,
                    mte.trading_value AS trading_value,
                    mte.user_memo AS user_memo,
                    mte.theme_id AS legacy_theme_id
                FROM market_trend_events mte
                LEFT JOIN stocks stock_by_code ON stock_by_code.stock_code = mte.stock_code
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                ORDER BY mte.trade_date, mte.id
                """
            ),
            params,
        ).mappings().all()
        current_rows = self.db.execute(
            text(
                """
                SELECT
                    mte.id AS event_id,
                    mte.trade_date AS trade_date,
                    COALESCE(mte.stock_id, stock_by_code.id) AS stock_id,
                    COALESCE(mte.stock_code, stock_by_code.stock_code) AS stock_code,
                    COALESCE(mte.stock_name, stock_by_code.stock_name, mte.stock_code, '-') AS stock_name,
                    mte.change_rate AS change_rate,
                    mte.trading_value AS trading_value,
                    mte.user_memo AS user_memo,
                    mt.id AS market_theme_id,
                    mt.theme_name AS theme_name,
                    CASE WHEN mt.theme_level = 'THEME_GROUP' THEN mt.id ELSE parent_mt.id END AS theme_group_id,
                    COALESCE(
                        CASE WHEN mt.theme_level = 'THEME_GROUP' THEN mt.theme_name ELSE parent_mt.theme_name END,
                        '미지정 테마그룹'
                    ) AS theme_group_name
                FROM market_trend_events mte
                LEFT JOIN stocks stock_by_code ON stock_by_code.stock_code = mte.stock_code
                JOIN market_theme_stocks mts
                  ON mts.stock_id = COALESCE(mte.stock_id, stock_by_code.id)
                 AND COALESCE(mts.is_active, 1) = 1
                JOIN market_themes mt
                  ON mt.id = mts.theme_id
                 AND COALESCE(mt.is_active, 1) = 1
                LEFT JOIN market_themes parent_mt ON parent_mt.id = mt.parent_theme_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND (mt.parent_theme_id IS NULL OR COALESCE(parent_mt.is_active, 1) = 1)
                ORDER BY mte.trade_date, mt.id, mte.id
                """
            ),
            params,
        ).mappings().all()
        historical_rows = self.db.execute(
            text(
                """
                WITH event_theme_pairs AS (
                    SELECT l.event_id, l.market_theme_id
                    FROM market_trend_event_theme_links l
                    WHERE COALESCE(l.is_active, 1) = 1
                      AND COALESCE(l.deleted_at, '') = ''
                    UNION
                    SELECT id AS event_id, theme_id AS market_theme_id
                    FROM market_trend_events
                    WHERE theme_id IS NOT NULL
                )
                SELECT etp.event_id, etp.market_theme_id
                FROM event_theme_pairs etp
                JOIN market_trend_events mte ON mte.id = etp.event_id
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest', 'manual')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                """
            ),
            params,
        ).mappings().all()

        base_by_event: dict[int, dict[str, object]] = {int(row["event_id"]): dict(row) for row in base_rows}
        current_theme_ids: dict[int, set[int]] = defaultdict(set)
        historical_theme_ids: dict[int, set[int]] = defaultdict(set)
        mapped_stock_keys: set[str] = set()
        active_theme_ids: set[int] = set()
        buckets: dict[tuple[str, int, str], dict[str, object]] = {}

        for row in historical_rows:
            historical_theme_ids[int(row["event_id"])].add(int(row["market_theme_id"]))
        for row in current_rows:
            event_id = int(row["event_id"])
            trade_date = str(row["trade_date"])
            theme_id = int(row["market_theme_id"])
            stock_id = int(row["stock_id"]) if row["stock_id"] is not None else None
            stock_code = normalize_stock_code(row["stock_code"])
            stock_name = str(row["stock_name"] or stock_code or "-")
            stock_key = f"id:{stock_id}" if stock_id is not None else f"code:{stock_code}" if stock_code else f"name:{stock_name}"
            current_theme_ids[event_id].add(theme_id)
            active_theme_ids.add(theme_id)
            mapped_stock_keys.add(stock_key)
            key = (trade_date, theme_id, stock_key)
            bucket = buckets.setdefault(
                key,
                {
                    "trade_date": trade_date,
                    "market_theme_id": theme_id,
                    "theme_name": str(row["theme_name"]),
                    "theme_group_id": int(row["theme_group_id"]) if row["theme_group_id"] is not None else None,
                    "theme_group_name": str(row["theme_group_name"] or "미지정 테마그룹"),
                    "stock_id": stock_id,
                    "stock_code": stock_code or None,
                    "stock_name": stock_name,
                    "event_ids": set(),
                    "change_rates": [],
                    "trading_values": [],
                    "memos": set(),
                },
            )
            bucket["event_ids"].add(event_id)
            if row["change_rate"] is not None:
                bucket["change_rates"].append(float(row["change_rate"]))
            if row["trading_value"] is not None:
                bucket["trading_values"].append(int(row["trading_value"]))
            memo = str(row["user_memo"] or "").strip()
            if memo:
                bucket["memos"].add(memo)

        records: list[dict[str, object]] = []
        for bucket in buckets.values():
            rates = list(bucket.pop("change_rates"))
            trading_values = list(bucket.pop("trading_values"))
            event_ids = set(bucket["event_ids"])
            records.append(
                {
                    **bucket,
                    "event_ids": event_ids,
                    "event_count": 1,
                    "change_rate": sum(rates) / len(rates) if rates else None,
                    "trading_value": max(trading_values) if trading_values else 0,
                    "memos": sorted(bucket["memos"]),
                }
            )
        records.sort(key=lambda row: (str(row["trade_date"]), int(row["market_theme_id"]), str(row["stock_name"])))

        all_stock_keys: set[str] = set()
        reclassified_event_stock_keys: set[tuple[str, str]] = set()
        for event_id, row in base_by_event.items():
            stock_id = int(row["stock_id"]) if row["stock_id"] is not None else None
            stock_code = normalize_stock_code(row["stock_code"])
            stock_name = str(row["stock_name"] or stock_code or "-")
            stock_key = f"id:{stock_id}" if stock_id is not None else f"code:{stock_code}" if stock_code else f"name:{stock_name}"
            all_stock_keys.add(stock_key)
            current_ids = current_theme_ids.get(event_id, set())
            if current_ids and current_ids != historical_theme_ids.get(event_id, set()):
                reclassified_event_stock_keys.add((str(row["trade_date"]), stock_key))

        diagnostics = MonthlySupplyClassificationDiagnostics(
            classification_basis="CURRENT_ACTIVE_THEME_MAPPING",
            event_count=len(base_by_event),
            unique_stock_count=len(all_stock_keys),
            active_theme_count=len(active_theme_ids),
            reclassified_event_stock_count=len(reclassified_event_stock_keys),
            unclassified_stock_count=len(all_stock_keys - mapped_stock_keys),
            period_start_date=start_date.isoformat(),
            period_end_date=end_date.isoformat(),
        )
        logger.info(
            "[monthly-supply-current-classification] period=%s~%s events=%s stocks=%s themes=%s reclassified=%s unclassified=%s rows=%s total_ms=%s",
            start_date.isoformat(), end_date.isoformat(), diagnostics.event_count,
            diagnostics.unique_stock_count, diagnostics.active_theme_count,
            diagnostics.reclassified_event_stock_count, diagnostics.unclassified_stock_count,
            len(records), int((time.perf_counter() - started_at) * 1000),
        )
        return {"records": records, "diagnostics": diagnostics}

    def _build_monthly_supply_summary_30d(self) -> MonthlySupplySummary30d:
        period_end = date.fromisoformat(now_kst()[:10])
        period_start = period_end - timedelta(days=30)
        aggregation = self._build_supply_theme_aggregation(period_start, period_end)
        records = list(aggregation["records"])

        stock_stats: dict[str, dict[str, object]] = {}
        theme_stats: dict[int, dict[str, object]] = {}
        for row in records:
            stock_id = row["stock_id"]
            stock_code = str(row["stock_code"] or "")
            stock_name = str(row["stock_name"])
            stock_key = f"id:{stock_id}" if stock_id is not None else f"code:{stock_code}" if stock_code else f"name:{stock_name}"
            stock_stat = stock_stats.setdefault(stock_key, {
                "stock_id": stock_id, "stock_code": stock_code or None, "stock_name": stock_name, "dates": set(),
            })
            stock_stat["dates"].add(str(row["trade_date"]))
            theme_id = int(row["market_theme_id"])
            theme_stat = theme_stats.setdefault(theme_id, {
                "theme_id": theme_id, "theme_name": str(row["theme_name"]), "dates": set(), "stocks": set(),
            })
            theme_stat["dates"].add(str(row["trade_date"]))
            theme_stat["stocks"].add(stock_key)

        ranked_stocks = sorted(
            stock_stats.values(),
            key=lambda item: (-len(item["dates"]), -date.fromisoformat(max(item["dates"])).toordinal(), str(item["stock_name"])),
        )
        top_stocks = [
            MonthlySupplySummaryStockItem(
                rank=index, stock_id=item["stock_id"], stock_code=item["stock_code"], stock_name=str(item["stock_name"]),
                appearance_count=len(item["dates"]), latest_detected_date=max(item["dates"]),
            )
            for index, item in enumerate(ranked_stocks[:3], start=1)
        ]
        ranked_themes = sorted(
            theme_stats.values(),
            key=lambda item: (-len(item["dates"]), -date.fromisoformat(max(item["dates"])).toordinal(), -len(item["stocks"]), str(item["theme_name"])),
        )
        top_theme = None
        if ranked_themes:
            winner = ranked_themes[0]
            top_theme = MonthlySupplySummaryThemeItem(
                theme_id=int(winner["theme_id"]), theme_name=str(winner["theme_name"]),
                appearance_count=len(winner["dates"]), latest_appearance_date=max(winner["dates"]),
                unique_stock_count=len(winner["stocks"]),
            )
        return MonthlySupplySummary30d(
            period_start_date=period_start.isoformat(), period_end_date=period_end.isoformat(),
            appeared_theme_count=len(theme_stats), top_theme=top_theme, top_stocks=top_stocks,
        )
    def get_supply_top_stock_return_trend(
        self,
        *,
        period_start_date: str,
        period_end_date: str,
        limit: int = 20,
    ) -> SupplyTopStockReturnTrendResponse:
        started_at = time.perf_counter()
        try:
            period_start = date.fromisoformat(period_start_date)
            period_end = date.fromisoformat(period_end_date)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="기간은 YYYY-MM-DD 형식이어야 합니다.") from exc
        if period_start > period_end:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="기간 시작일은 종료일보다 늦을 수 없습니다.")
        normalized_limit = max(1, min(int(limit), 20))
        aggregation = self._build_supply_theme_aggregation(period_start, period_end)
        source_records = list(aggregation["records"])

        stock_stats: dict[int, dict[str, object]] = {}
        for row in source_records:
            if row["stock_id"] is None:
                continue
            stock_id = int(row["stock_id"])
            stat = stock_stats.setdefault(stock_id, {
                "stock_id": stock_id,
                "stock_code": str(row["stock_code"] or ""),
                "stock_name": str(row["stock_name"] or row["stock_code"] or stock_id),
                "dates": set(),
            })
            stat["dates"].add(str(row["trade_date"]))
        ranked = sorted(
            stock_stats.values(),
            key=lambda item: (-len(item["dates"]), -date.fromisoformat(max(item["dates"])).toordinal(), str(item["stock_name"])),
        )[:normalized_limit]
        selected_ids = [int(item["stock_id"]) for item in ranked]
        price_rows: list[dict[str, object]] = []
        if selected_ids:
            id_params = {f"stock_id_{index}": stock_id for index, stock_id in enumerate(selected_ids)}
            id_sql = ", ".join(f":stock_id_{index}" for index in range(len(selected_ids)))
            price_rows = [dict(row) for row in self.db.execute(
                text(f"""
                    SELECT price.stock_id, price.trade_date, price.close_price, price.change_rate, price.updated_at
                    FROM stock_daily_prices price
                    WHERE price.stock_id IN ({id_sql})
                      AND price.close_price IS NOT NULL AND price.close_price > 0
                      AND price.trade_date <= :period_end_date
                      AND (price.trade_date >= :period_start_date OR price.trade_date = (
                        SELECT MAX(base.trade_date) FROM stock_daily_prices base
                        WHERE base.stock_id = price.stock_id
                          AND base.trade_date < :period_start_date
                          AND base.close_price IS NOT NULL AND base.close_price > 0
                      ))
                    ORDER BY price.stock_id, price.trade_date
                """),
                {**id_params, "period_start_date": period_start_date, "period_end_date": period_end_date},
            ).mappings().all()]

        market_trade_dates = [str(value) for value in self.db.execute(
            text("""
                SELECT DISTINCT trade_date FROM stock_daily_prices
                WHERE trade_date BETWEEN :start_date AND :end_date
                  AND close_price IS NOT NULL AND close_price > 0
                ORDER BY trade_date
            """),
            {"start_date": period_start_date, "end_date": period_end_date},
        ).scalars().all()]
        prices_by_stock: dict[int, list[dict[str, object]]] = defaultdict(list)
        for row in price_rows:
            prices_by_stock[int(row["stock_id"])].append(row)
        selected_trade_dates = sorted({
            str(row["trade_date"]) for row in price_rows
            if period_start_date <= str(row["trade_date"]) <= period_end_date
        })
        trade_dates = market_trade_dates or selected_trade_dates
        expected_trade_date_count = len(trade_dates)
        price_data_end_date = max(selected_trade_dates) if selected_trade_dates else None
        latest_updates_by_stock: dict[int, str] = {}
        for row in price_rows:
            stock_id = int(row["stock_id"])
            updated_at = str(row.get("updated_at") or "")
            if updated_at and updated_at > latest_updates_by_stock.get(stock_id, ""):
                latest_updates_by_stock[stock_id] = updated_at
        last_price_collection_date = None
        if selected_ids and all(stock_id in latest_updates_by_stock for stock_id in selected_ids):
            last_price_collection_date = min(latest_updates_by_stock.values())[:10]
        items: list[SupplyTopStockReturnTrendItem] = []
        status_counts: dict[str, int] = defaultdict(int)
        missing_ids: list[int] = []
        missing_codes: list[str] = []

        for rank, stat in enumerate(ranked, start=1):
            stock_id = int(stat["stock_id"])
            rows = prices_by_stock.get(stock_id, [])
            base_row = next((row for row in rows if str(row["trade_date"]) < period_start_date), None)
            period_rows = [row for row in rows if period_start_date <= str(row["trade_date"]) <= period_end_date]
            fallback_row = period_rows[0] if period_rows else None
            effective_base_row = base_row or fallback_row
            base_close = float(effective_base_row["close_price"]) if effective_base_row else None
            observation_count = len(period_rows)
            coverage_rate = round((observation_count / expected_trade_date_count) * 100, 1) if expected_trade_date_count else 0.0
            if observation_count == 0:
                price_status, status_name = "NO_PRICE_DATA", "가격 없음"
                reason = "최근 30일 범위에 저장된 일봉 가격이 없습니다."
            elif observation_count == 1:
                price_status, status_name = "INSUFFICIENT_OBSERVATIONS", "관측 부족"
                reason = "기간 내 유효 종가가 1개뿐이라 누적등락률 선을 만들 수 없습니다."
            elif base_row is None:
                price_status, status_name = "READY_WITH_FALLBACK", "기간 첫 종가 기준"
                reason = "시작일 이전 종가가 없어 기간 내 첫 거래일 종가를 0% 기준으로 사용합니다."
            elif expected_trade_date_count and coverage_rate < 50:
                price_status, status_name = "PARTIAL", "일부 가격만 있음"
                reason = "기준 종가와 유효 가격은 있으나 전체 거래일의 50% 미만만 저장되어 있습니다."
            else:
                price_status, status_name = "READY", "준비 완료"
                reason = "기준 종가와 누적등락률 계산에 필요한 가격이 준비되었습니다."
            graphable = price_status in {"READY", "READY_WITH_FALLBACK", "PARTIAL"}
            status_counts[price_status] += 1
            if not graphable:
                missing_ids.append(stock_id)
                missing_codes.append(str(stat["stock_code"]))

            supply_dates = sorted(set(stat["dates"]), reverse=True)
            supply_date_set = set(supply_dates)
            points: list[SupplyTopStockReturnPoint] = []
            previous_close = float(base_row["close_price"]) if base_row else None
            for row in period_rows:
                close = float(row["close_price"])
                daily_return = float(row["change_rate"]) if row["change_rate"] is not None else (((close / previous_close) - 1) * 100 if previous_close else None)
                cumulative_return = ((close / base_close) - 1) * 100 if base_close else None
                points.append(SupplyTopStockReturnPoint(
                    trade_date=str(row["trade_date"]), close=close,
                    daily_return=round(daily_return, 4) if daily_return is not None else None,
                    cumulative_return=round(cumulative_return, 4) if cumulative_return is not None else None,
                    is_supply_date=str(row["trade_date"]) in supply_date_set,
                ))
                previous_close = close
            latest_point = points[-1] if points else None
            items.append(SupplyTopStockReturnTrendItem(
                rank=rank, stock_id=stock_id, stock_code=str(stat["stock_code"]), stock_name=str(stat["stock_name"]),
                appearance_count=len(supply_dates), appearance_dates=supply_dates,
                latest_detected_date=supply_dates[0] if supply_dates else None,
                price_data_status=price_status, price_data_status_name=status_name, price_data_reason=reason,
                price_observation_count=observation_count, expected_trade_date_count=expected_trade_date_count,
                price_coverage_rate=coverage_rate,
                base_price_date=str(effective_base_row["trade_date"]) if effective_base_row else None,
                base_close=base_close, latest_price_date=latest_point.trade_date if latest_point else None,
                latest_close=latest_point.close if latest_point else None,
                latest_daily_return=latest_point.daily_return if latest_point else None,
                latest_cumulative_return=latest_point.cumulative_return if latest_point else None,
                has_sufficient_price_data=graphable, points=points,
            ))

        ready_count = sum(status_counts[key] for key in ("READY", "READY_WITH_FALLBACK", "PARTIAL"))
        readiness = SupplyTopStockPriceReadiness(
            total_stock_count=len(items), ready_stock_count=ready_count,
            fallback_ready_stock_count=status_counts["READY_WITH_FALLBACK"], partial_stock_count=status_counts["PARTIAL"],
            missing_stock_count=len(missing_ids),
            readiness_rate=round((ready_count / len(items)) * 100, 1) if items else 0,
            missing_stock_ids=missing_ids, missing_stock_codes=missing_codes,
            no_price_data_count=status_counts["NO_PRICE_DATA"], no_base_price_count=status_counts["NO_BASE_PRICE"],
            insufficient_observation_count=status_counts["INSUFFICIENT_OBSERVATIONS"],
        )
        logger.info(
            "[SUPPLY TOP STOCK TREND] period=%s~%s selected=%s ready=%s missing=%s price_rows=%s expected_dates=%s total_ms=%s",
            period_start_date, period_end_date, len(items), ready_count, len(missing_ids), len(price_rows),
            expected_trade_date_count, int((time.perf_counter() - started_at) * 1000),
        )
        return SupplyTopStockReturnTrendResponse(
            period_start_date=period_start_date, period_end_date=period_end_date,
            price_data_end_date=price_data_end_date, last_price_collection_date=last_price_collection_date,
            ranking_basis="UNIQUE_STOCK_SUPPLY_DAYS",
            limit=normalized_limit, trade_dates=trade_dates, price_readiness=readiness, stocks=items,
        )

    def refresh_supply_top_stock_prices(
        self,
        payload: SupplyTopStockPriceCollectRequest,
    ) -> SupplyTopStockPriceCollectResponse:
        if not self._supply_price_collection_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="TOP20 가격 갱신이 이미 실행 중입니다.",
            )
        started_at = time.perf_counter()
        try:
            try:
                period_start = date.fromisoformat(payload.period_start_date)
                period_end = date.fromisoformat(payload.period_end_date)
                if period_start > period_end:
                    raise ValueError
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="올바른 가격 조회 기간을 입력해 주세요.",
                ) from exc

            before = self.get_supply_top_stock_return_trend(
                period_start_date=payload.period_start_date,
                period_end_date=payload.period_end_date,
                limit=payload.limit,
            )
            target_ids = [item.stock_id for item in before.stocks]
            collection_date = date.fromisoformat(now_kst()[:10])
            initial_collect_start = collection_date - timedelta(days=30)
            logger.info(
                "[SUPPLY TOP20 PRICE REFRESH] graph_period=%s~%s collection_date=%s top_stock_count=%s mode=incremental",
                period_start, period_end, collection_date, len(target_ids),
            )
            raw_results = StockPriceService(self.db).refresh_price_ranges_only(
                stock_ids=target_ids,
                end_date=collection_date,
                initial_lookback_days=30,
                source="kiwoom_rest",
                mode="supply_top20_incremental_refresh",
            ) if target_ids else []

            after = self.get_supply_top_stock_return_trend(
                period_start_date=payload.period_start_date,
                period_end_date=payload.period_end_date,
                limit=payload.limit,
            )
            before_by_id = {item.stock_id: item for item in before.stocks}
            after_by_id = {item.stock_id: item for item in after.stocks}
            results: list[SupplyTopStockPriceCollectItem] = []
            for raw in raw_results:
                stock_id = int(raw["stock_id"])
                before_item = before_by_id[stock_id]
                after_item = after_by_id.get(stock_id)
                results.append(SupplyTopStockPriceCollectItem(
                    stock_id=stock_id,
                    stock_code=str(raw.get("stock_code") or ""),
                    stock_name=str(raw.get("stock_name") or ""),
                    status="SUCCESS" if raw.get("status") == "SUCCESS" else "FAILED",
                    collection_mode=str(raw.get("collection_mode") or "INITIAL"),
                    collect_start_date=str(raw.get("collect_start_date") or initial_collect_start.isoformat()),
                    collect_end_date=str(raw.get("collect_end_date") or collection_date.isoformat()),
                    pages_fetched=int(raw.get("pages_fetched") or 0),
                    collected_count=int(raw.get("collected_count") or 0),
                    saved_count=int(raw.get("saved_count") or 0),
                    price_data_status_before=before_item.price_data_status,
                    price_data_status_after=after_item.price_data_status if after_item else "NO_PRICE_DATA",
                    error_message=str(raw.get("error_message")) if raw.get("error_message") else None,
                ))

            success_count = sum(1 for item in results if item.status == "SUCCESS")
            failed_count = sum(1 for item in results if item.status == "FAILED")
            total_ms = int((time.perf_counter() - started_at) * 1000)
            saved_price_count = sum(item.saved_count for item in results)
            total_pages = sum(item.pages_fetched for item in results)
            collect_start_date = min(
                (item.collect_start_date for item in results),
                default=initial_collect_start.isoformat(),
            )
            logger.info(
                "[SUPPLY TOP20 PRICE REFRESH DONE] target=%s success=%s failed=%s saved=%s pages=%s total_ms=%s",
                len(target_ids), success_count, failed_count, saved_price_count, total_pages, total_ms,
            )
            return SupplyTopStockPriceCollectResponse(
                period_start_date=payload.period_start_date,
                period_end_date=payload.period_end_date,
                collect_start_date=collect_start_date,
                collect_end_date=collection_date.isoformat(),
                last_price_collection_date=after.last_price_collection_date,
                top_stock_count=len(before.stocks),
                target_stock_count=len(target_ids),
                success_count=success_count,
                partial_count=0,
                failed_count=failed_count,
                skipped_count=0,
                saved_price_count=saved_price_count,
                total_api_calls=total_pages,
                total_pages=total_pages,
                total_ms=total_ms,
                before_readiness=before.price_readiness,
                after_readiness=after.price_readiness,
                results=results,
            )
        finally:
            self._supply_price_collection_lock.release()
    def get_monthly_theme_flow_calendar(self, month: str) -> MonthlyThemeFlowCalendarResponse:
        month_start, month_end = self._resolve_month_window(month)
        summary_30d = self._build_monthly_supply_summary_30d()
        aggregation = self._build_supply_theme_aggregation(month_start, month_end)
        records = list(aggregation["records"])

        grouped_records: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
        day_event_ids: dict[str, set[int]] = defaultdict(set)
        day_stock_keys: dict[str, set[str]] = defaultdict(set)
        memo_items_by_date: dict[str, list[MonthlyThemeFlowMemoItem]] = defaultdict(list)
        seen_memos: set[tuple[str, int, str, str]] = set()
        for row in records:
            trade_date = str(row["trade_date"])
            theme_id = int(row["market_theme_id"])
            grouped_records[(trade_date, theme_id)].append(row)
            day_event_ids[trade_date].update(set(row["event_ids"]))
            stock_key = str(row["stock_code"] or row["stock_id"] or row["stock_name"])
            day_stock_keys[trade_date].add(stock_key)
            for memo in row["memos"]:
                memo_key = (trade_date, theme_id, stock_key, str(memo))
                if memo_key in seen_memos:
                    continue
                seen_memos.add(memo_key)
                memo_items_by_date[trade_date].append(
                    MonthlyThemeFlowMemoItem(
                        theme_id=theme_id,
                        theme_name=str(row["theme_name"]),
                        stock_code=str(row["stock_code"]) if row["stock_code"] else None,
                        stock_name=str(row["stock_name"]),
                        memo=str(memo),
                    )
                )

        grouped: dict[str, list[DailyThemeFlowSummaryItem]] = defaultdict(list)
        theme_group_meta: dict[tuple[str, int], dict[str, object]] = {}
        stocks_by_date_theme: dict[tuple[str, int], list[MonthlyThemeFlowStockItem]] = {}
        for (trade_date, theme_id), theme_records in grouped_records.items():
            valid_rates = [float(row["change_rate"]) for row in theme_records if row["change_rate"] is not None]
            theme_group_meta[(trade_date, theme_id)] = {
                "theme_group_id": theme_records[0]["theme_group_id"],
                "theme_group_name": theme_records[0]["theme_group_name"],
            }
            stocks_by_date_theme[(trade_date, theme_id)] = [
                MonthlyThemeFlowStockItem(
                    stock_id=int(row["stock_id"]) if row["stock_id"] is not None else None,
                    stock_code=str(row["stock_code"]) if row["stock_code"] else None,
                    stock_name=str(row["stock_name"]),
                    change_rate=float(row["change_rate"]) if row["change_rate"] is not None else None,
                )
                for row in theme_records
            ]
            grouped[trade_date].append(
                DailyThemeFlowSummaryItem(
                    market_theme_id=theme_id,
                    theme_name=str(theme_records[0]["theme_name"]),
                    stock_count=len(theme_records),
                    event_count=len(theme_records),
                    avg_change_rate=sum(valid_rates) / len(valid_rates) if valid_rates else None,
                    max_change_rate=max(valid_rates) if valid_rates else None,
                    estimated_trading_value_sum=sum(int(row["trading_value"] or 0) for row in theme_records),
                    representative_stocks=[],
                )
            )

        manual_rank_maps = self._load_manual_rank_maps(month_start.isoformat(), month_end.isoformat())
        days: list[MonthlyThemeFlowCalendarDayItem] = []
        cursor = month_start
        while cursor <= month_end:
            key = cursor.isoformat()
            ranked_day = self._apply_rank_overrides(
                trade_date=key,
                items=grouped.get(key, []),
                manual_map=manual_rank_maps.get(key, {}),
            )
            themes = [
                MonthlyThemeFlowCalendarThemeItem(
                    rank=int(item.final_rank or (index + 1)),
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
                for index, item in enumerate(ranked_day)
            ]
            days.append(
                MonthlyThemeFlowCalendarDayItem(
                    trade_date=key,
                    event_count=len(day_event_ids.get(key, set())),
                    related_stock_count=len(day_stock_keys.get(key, set())),
                    themes=themes,
                    memo_items=memo_items_by_date.get(key, []),
                )
            )
            cursor += timedelta(days=1)

        return MonthlyThemeFlowCalendarResponse(
            success=True,
            month=month,
            start_date=month_start.isoformat(),
            end_date=month_end.isoformat(),
            summary_30d=summary_30d,
            diagnostics=aggregation["diagnostics"],
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
        aggregation = self._build_supply_theme_aggregation(month_start, month_end)
        source_records = list(aggregation["records"])

        records: list[dict[str, object]] = []
        for row in source_records:
            current_group_id = int(row["theme_group_id"]) if row["theme_group_id"] is not None else None
            if theme_group_id is not None and current_group_id != theme_group_id:
                continue
            entity_id = (
                current_group_id or int(row["market_theme_id"])
                if normalized_view_mode == "THEME_GROUP"
                else int(row["market_theme_id"])
            )
            entity_name = (
                str(row["theme_group_name"] if current_group_id is not None else row["theme_name"])
                if normalized_view_mode == "THEME_GROUP"
                else str(row["theme_name"])
            )
            records.append({**row, "entity_id": entity_id, "entity_name": entity_name})

        entity_daily: dict[tuple[str, int, str], dict[str, object]] = {}
        child_stats: dict[int, dict[int, dict[str, object]]] = defaultdict(dict)
        related_stats: dict[int, dict[str, str]] = defaultdict(dict)
        entity_meta: dict[int, dict[str, object]] = {}
        for row in records:
            trade_date = str(row["trade_date"])
            entity_id = int(row["entity_id"])
            stock_key = str(row["stock_code"] or row["stock_id"] or row["stock_name"])
            key = (trade_date, entity_id, stock_key)
            bucket = entity_daily.setdefault(
                key,
                {
                    "trade_date": trade_date,
                    "entity_id": entity_id,
                    "entity_name": str(row["entity_name"]),
                    "stock_name": str(row["stock_name"]),
                    "change_rates": [],
                    "trading_values": [],
                },
            )
            if row["change_rate"] is not None:
                bucket["change_rates"].append(float(row["change_rate"]))
            bucket["trading_values"].append(int(row["trading_value"] or 0))
            related_stats[entity_id][str(row["stock_name"])] = max(
                trade_date,
                related_stats[entity_id].get(str(row["stock_name"]), ""),
            )
            entity_meta[entity_id] = {
                "theme_name": str(row["entity_name"]),
                "theme_group_id": entity_id if normalized_view_mode == "THEME_GROUP" else row["theme_group_id"],
                "theme_group_name": str(row["entity_name"] if normalized_view_mode == "THEME_GROUP" else row["theme_group_name"]),
            }
            group_id = current_group_id = int(row["theme_group_id"]) if row["theme_group_id"] is not None else int(row["market_theme_id"])
            child_id = int(row["market_theme_id"])
            child = child_stats[group_id].setdefault(
                child_id,
                {"theme_name": str(row["theme_name"]), "dates_stocks": set(), "stocks": set()},
            )
            child["dates_stocks"].add((trade_date, stock_key))
            child["stocks"].add(stock_key)

        daily_groups: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
        for bucket in entity_daily.values():
            rates = list(bucket["change_rates"])
            daily_groups[(str(bucket["trade_date"]), int(bucket["entity_id"]))].append(
                {
                    **bucket,
                    "change_rate": sum(rates) / len(rates) if rates else None,
                    "trading_value": max(bucket["trading_values"]) if bucket["trading_values"] else 0,
                }
            )

        date_keys: list[str] = []
        cursor = month_start
        while cursor <= month_end:
            date_keys.append(cursor.isoformat())
            cursor += timedelta(days=1)
        by_date: dict[str, list[DailyThemeFlowSummaryItem]] = defaultdict(list)
        for (trade_date, entity_id), daily_records in daily_groups.items():
            valid_rates = [float(row["change_rate"]) for row in daily_records if row["change_rate"] is not None]
            by_date[trade_date].append(
                DailyThemeFlowSummaryItem(
                    market_theme_id=entity_id,
                    theme_name=str(daily_records[0]["entity_name"]),
                    event_count=len(daily_records),
                    stock_count=len(daily_records),
                    avg_change_rate=sum(valid_rates) / len(valid_rates) if valid_rates else None,
                    max_change_rate=max(valid_rates) if valid_rates else None,
                    estimated_trading_value_sum=sum(int(row["trading_value"] or 0) for row in daily_records),
                    representative_stocks=[],
                )
            )

        manual_rank_maps = self._load_manual_rank_maps(month_start.isoformat(), month_end.isoformat())
        day_ranked: dict[str, list[DailyThemeFlowSummaryItem]] = {}
        total_score_map: dict[int, int] = {}
        for key in date_keys:
            ranked = self._apply_rank_overrides(
                trade_date=key,
                items=by_date.get(key, []),
                manual_map=manual_rank_maps.get(key, {}),
            )
            day_ranked[key] = ranked
            for item in ranked:
                total_score_map[item.market_theme_id] = total_score_map.get(item.market_theme_id, 0) + int(item.rank_score or 0)

        sorted_ids = sorted(
            total_score_map,
            key=lambda entity_id: (total_score_map[entity_id], str(entity_meta.get(entity_id, {}).get("theme_name", ""))),
            reverse=True,
        )
        target_ids = sorted_ids[:normalized_limit] if normalized_limit is not None else sorted_ids
        themes: list[MonthlyThemeFlowTrendTheme] = []
        for entity_id in target_ids:
            cumulative = 0
            series: list[MonthlyThemeFlowTrendPoint] = []
            for key in date_keys:
                item = next((candidate for candidate in day_ranked.get(key, []) if candidate.market_theme_id == entity_id), None)
                if item is None:
                    series.append(
                        MonthlyThemeFlowTrendPoint(
                            trade_date=key, value=cumulative, daily_score=0, final_rank=None, rank_basis="auto",
                            stock_count=0, event_count=0, avg_change_rate=None, max_change_rate=None,
                            estimated_trading_value_sum=0,
                        )
                    )
                    continue
                daily_score = int(item.rank_score or 0)
                cumulative += daily_score
                series.append(
                    MonthlyThemeFlowTrendPoint(
                        trade_date=key, value=cumulative, daily_score=daily_score,
                        final_rank=item.final_rank, rank_basis=item.rank_basis,
                        stock_count=item.stock_count, event_count=item.event_count,
                        avg_change_rate=item.avg_change_rate, max_change_rate=item.max_change_rate,
                        estimated_trading_value_sum=item.estimated_trading_value_sum,
                    )
                )
            meta = entity_meta.get(entity_id, {})
            group_id = int(meta["theme_group_id"]) if meta.get("theme_group_id") is not None else None
            children = child_stats.get(group_id or entity_id, {})
            child_names = [
                str(item["theme_name"])
                for item in sorted(
                    children.values(),
                    key=lambda item: (len(item["dates_stocks"]), len(item["stocks"]), str(item["theme_name"])),
                    reverse=True,
                )
            ]
            related_stocks = [
                name for name, _ in sorted(related_stats.get(entity_id, {}).items(), key=lambda item: (item[1], item[0]), reverse=True)
            ]
            themes.append(
                MonthlyThemeFlowTrendTheme(
                    market_theme_id=entity_id,
                    theme_name=str(meta.get("theme_name") or entity_id),
                    view_mode=normalized_view_mode,
                    theme_group_id=group_id,
                    theme_group_name=str(meta.get("theme_group_name") or ""),
                    child_theme_count=len(child_names) if normalized_view_mode == "THEME_GROUP" else 0,
                    top_child_themes=child_names[:3] if normalized_view_mode == "THEME_GROUP" else [],
                    related_stocks=related_stocks[:8],
                    series=series,
                )
            )

        return MonthlyThemeFlowTrendResponse(
            success=True,
            month=month,
            start_date=month_start.isoformat(),
            end_date=month_end.isoformat(),
            diagnostics=aggregation["diagnostics"],
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
    def refresh_market_theme_returns(
        self,
        payload: MarketThemeReturnRefreshRequest,
        *,
        use_saved_prices: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> MarketThemeReturnRefreshResponse:
        total_started_at = time.perf_counter()
        refreshed_at = now_kst()
        return_date = refreshed_at[:10]
        provider: KiwoomRestMarketIndicatorProvider | None = None
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
        stock_return_cache: dict[int, dict[str, object]]
        price_api_call_count = 0
        if use_saved_prices:
            stock_return_cache = self._load_saved_theme_stock_returns(unique_stocks, return_date)
            missing_stock_ids = [
                stock_id
                for stock_id, row in stock_return_cache.items()
                if row.get("data_status") != "success"
            ]
            if missing_stock_ids:
                provider = KiwoomRestMarketIndicatorProvider()
                for stock_id in missing_stock_ids:
                    stock_return_cache[stock_id] = self._fetch_theme_stock_return(
                        provider, unique_stocks[stock_id], return_date
                    )
                price_api_call_count = len(missing_stock_ids)
        else:
            provider = KiwoomRestMarketIndicatorProvider()
            stock_return_cache = {}
            for stock_id, stock in unique_stocks.items():
                stock_return_cache[stock_id] = self._fetch_theme_stock_return(provider, stock, return_date)
            price_api_call_count = len(unique_stocks)
        price_fetch_ms = int((time.perf_counter() - price_started_at) * 1000)

        calc_started_at = time.perf_counter()
        theme_results: list[dict[str, object]] = []
        for theme in themes:
            theme_id = int(theme["theme_id"])
            stocks = links_by_theme.get(theme_id, [])
            stock_results = [dict(stock_return_cache[int(stock["stock_id"])]) for stock in stocks if int(stock["stock_id"]) in stock_return_cache]

            stock_count = len(stocks)
            summary = self._summarize_theme_return_rows(stock_results, connected_stock_count=stock_count)
            success_count = int(summary["success_stock_count"])
            failed_count = int(summary["failed_stock_count"])
            total_stock_count += stock_count
            total_success_count += success_count
            total_failed_count += failed_count

            theme_results.append({
                "theme_id": theme_id,
                "theme_name": str(theme["theme_name"]),
                **summary,
                "stock_results": stock_results,
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
                if progress_callback:
                    progress_callback(len(items), len(themes))
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
            if progress_callback:
                progress_callback(len(items), len(themes))

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

    def get_market_theme_return_recalculation_preview(
        self,
        theme_id: int,
    ) -> MarketThemeReturnRecalculationPreview:
        row = self.db.execute(
            text(
                """
                SELECT t.id AS theme_id, t.theme_name,
                       COUNT(DISTINCT CASE
                           WHEN mts.is_active=1 AND COALESCE(s.is_active, 1)=1 THEN s.id
                       END) AS connected_stock_count,
                       MIN(CASE
                           WHEN mts.is_active=1 AND COALESCE(s.is_active, 1)=1
                                AND p.change_rate IS NOT NULL AND p.trade_date<=:period_to THEN p.trade_date
                       END) AS period_from,
                       MAX(CASE
                           WHEN mts.is_active=1 AND COALESCE(s.is_active, 1)=1
                                AND p.change_rate IS NOT NULL AND p.trade_date<=:period_to THEN p.trade_date
                       END) AS period_to
                FROM market_themes t
                LEFT JOIN market_theme_stocks mts ON mts.theme_id=t.id
                LEFT JOIN stocks s ON s.id=mts.stock_id
                LEFT JOIN stock_daily_prices p ON p.stock_id=s.id
                WHERE t.id=:theme_id
                GROUP BY t.id, t.theme_name
                """
            ),
            {"theme_id": theme_id, "period_to": now_kst()[:10]},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="테마를 찾을 수 없습니다.")
        return MarketThemeReturnRecalculationPreview(
            theme_id=int(row["theme_id"]),
            theme_name=str(row["theme_name"]),
            connected_stock_count=int(row["connected_stock_count"] or 0),
            period_from=str(row["period_from"]) if row["period_from"] else None,
            period_to=str(row["period_to"]) if row["period_to"] else None,
        )

    def recalculate_market_theme_returns(
        self,
        theme_id: int,
    ) -> MarketThemeReturnRecalculationResponse:
        with self._theme_return_recalculation_state_lock:
            if theme_id in self._theme_return_recalculating_ids:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 해당 테마의 등락률을 재계산 중입니다.",
                )
            self._theme_return_recalculating_ids.add(theme_id)

        try:
            preview = self.get_market_theme_return_recalculation_preview(theme_id)
            stocks = self._list_active_theme_return_stocks(theme_id)
            if not stocks:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="현재 활성 연결 종목이 없어 재계산할 수 없습니다.",
                )

            params: dict[str, object] = {"theme_id": theme_id, "period_to": now_kst()[:10]}
            placeholders: list[str] = []
            stock_by_id: dict[int, dict[str, object]] = {}
            for index, stock in enumerate(stocks):
                stock_id = int(stock["stock_id"])
                stock_by_id[stock_id] = stock
                key = f"stock_id_{index}"
                placeholders.append(f":{key}")
                params[key] = stock_id

            price_rows = self.db.execute(
                text(
                    f"""
                    SELECT stock_id, trade_date, change_rate, trading_value, close_price
                    FROM stock_daily_prices
                    WHERE stock_id IN ({', '.join(placeholders)})
                      AND trade_date <= :period_to
                      AND change_rate IS NOT NULL
                    ORDER BY trade_date ASC, stock_id ASC
                    """
                ),
                params,
            ).mappings().all()
            if not price_rows:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="현재 연결 종목의 저장된 일간 등락률 데이터가 없습니다.",
                )

            rows_by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in price_rows:
                stock_id = int(row["stock_id"])
                stock = stock_by_id[stock_id]
                raw_trading_value = self._to_int_or_none(row["trading_value"])
                rows_by_date[str(row["trade_date"])].append({
                    "stock_id": stock_id,
                    "stock_code": normalize_stock_code(str(stock.get("stock_code") or "")),
                    "stock_name": str(stock.get("stock_name") or ""),
                    "change_rate": float(row["change_rate"]),
                    "trading_value": raw_trading_value * 1_000_000 if raw_trading_value is not None else None,
                    "trading_value_100m": round(raw_trading_value / 100.0, 4) if raw_trading_value is not None else None,
                    "current_price": self._to_abs_int(row["close_price"]),
                    "data_status": "success",
                    "error_message": None,
                })

            recalculated_at = now_kst()
            period_from = min(rows_by_date)
            period_to = max(rows_by_date)
            existing_rows = self.db.execute(
                text(
                    """
                    SELECT id, return_date
                    FROM market_theme_daily_returns
                    WHERE theme_id=:theme_id
                      AND return_date BETWEEN :period_from AND :period_to
                    """
                ),
                {"theme_id": theme_id, "period_from": period_from, "period_to": period_to},
            ).mappings().all()
            existing_by_date = {str(row["return_date"]): int(row["id"]) for row in existing_rows}
            valid_dates = set(rows_by_date)
            skipped_dates = sorted(set(existing_by_date) - valid_dates)
            connected_stock_count = len(stocks)

            aggregate_params: list[dict[str, object]] = []
            for return_date, stock_results in rows_by_date.items():
                summary = self._summarize_theme_return_rows(
                    stock_results,
                    connected_stock_count=connected_stock_count,
                )
                aggregate_params.append({
                    "theme_id": theme_id,
                    "return_date": return_date,
                    "avg_change_rate": summary["avg_change_rate"],
                    "stock_count": connected_stock_count,
                    "success_stock_count": summary["success_stock_count"],
                    "failed_stock_count": summary["failed_stock_count"],
                    "rising_stock_count": summary["rising_count"],
                    "falling_stock_count": summary["falling_count"],
                    "flat_stock_count": summary["flat_count"],
                    "total_trading_value": summary["total_trading_value"],
                    "total_trading_value_100m": summary["total_trading_value_100m"],
                    "now": recalculated_at,
                })

            self.db.execute(
                text(
                    """
                    INSERT INTO market_theme_daily_returns
                    (theme_id, return_date, avg_change_rate, stock_count, success_stock_count, failed_stock_count,
                     rising_stock_count, falling_stock_count, flat_stock_count, total_trading_value,
                     total_trading_value_100m, data_source, first_created_at, last_refreshed_at,
                     refresh_count, created_at, updated_at)
                    VALUES
                    (:theme_id, :return_date, :avg_change_rate, :stock_count, :success_stock_count, :failed_stock_count,
                     :rising_stock_count, :falling_stock_count, :flat_stock_count, :total_trading_value,
                     :total_trading_value_100m, 'stored_stock_prices_current_members', :now, :now, 1, :now, :now)
                    ON CONFLICT(theme_id, return_date) DO UPDATE SET
                        avg_change_rate=excluded.avg_change_rate,
                        stock_count=excluded.stock_count,
                        success_stock_count=excluded.success_stock_count,
                        failed_stock_count=excluded.failed_stock_count,
                        rising_stock_count=excluded.rising_stock_count,
                        falling_stock_count=excluded.falling_stock_count,
                        flat_stock_count=excluded.flat_stock_count,
                        total_trading_value=excluded.total_trading_value,
                        total_trading_value_100m=excluded.total_trading_value_100m,
                        data_source=excluded.data_source,
                        last_refreshed_at=excluded.last_refreshed_at,
                        refresh_count=market_theme_daily_returns.refresh_count+1,
                        updated_at=excluded.updated_at
                    """
                ),
                aggregate_params,
            )

            if skipped_dates:
                skipped_params = [
                    {
                        "theme_id": theme_id,
                        "return_date": return_date,
                        "stock_count": connected_stock_count,
                        "now": recalculated_at,
                    }
                    for return_date in skipped_dates
                ]
                self.db.execute(
                    text(
                        """
                        UPDATE market_theme_daily_returns
                        SET avg_change_rate=NULL, stock_count=:stock_count, success_stock_count=0,
                            failed_stock_count=:stock_count, rising_stock_count=0, falling_stock_count=0,
                            flat_stock_count=0, total_trading_value=0, total_trading_value_100m=NULL,
                            data_source='stored_stock_prices_current_members', last_refreshed_at=:now,
                            refresh_count=refresh_count+1, updated_at=:now
                        WHERE theme_id=:theme_id AND return_date=:return_date
                        """
                    ),
                    skipped_params,
                )

            daily_rows = self.db.execute(
                text(
                    """
                    SELECT id, return_date
                    FROM market_theme_daily_returns
                    WHERE theme_id=:theme_id
                      AND return_date BETWEEN :period_from AND :period_to
                      AND avg_change_rate IS NOT NULL
                    """
                ),
                {"theme_id": theme_id, "period_from": period_from, "period_to": period_to},
            ).mappings().all()
            daily_id_by_date = {str(row["return_date"]): int(row["id"]) for row in daily_rows}

            self.db.execute(
                text(
                    """
                    UPDATE market_theme_stock_daily_returns
                    SET data_status='inactive', error_message='not_current_theme_member', updated_at=:now
                    WHERE theme_id=:theme_id
                      AND return_date BETWEEN :period_from AND :period_to
                    """
                ),
                {
                    "theme_id": theme_id,
                    "period_from": period_from,
                    "period_to": period_to,
                    "now": recalculated_at,
                },
            )
            detail_params: list[dict[str, object]] = []
            for return_date, stock_results in rows_by_date.items():
                daily_return_id = daily_id_by_date[return_date]
                for row in stock_results:
                    detail_params.append({
                        "theme_daily_return_id": daily_return_id,
                        "theme_id": theme_id,
                        "stock_id": int(row["stock_id"]),
                        "stock_code": row["stock_code"],
                        "stock_name": row["stock_name"],
                        "return_date": return_date,
                        "change_rate": row["change_rate"],
                        "trading_value": row["trading_value"],
                        "trading_value_100m": row["trading_value_100m"],
                        "current_price": row["current_price"],
                        "now": recalculated_at,
                    })
            self.db.execute(
                text(
                    """
                    INSERT INTO market_theme_stock_daily_returns
                    (theme_daily_return_id, theme_id, stock_id, stock_code, stock_name, return_date,
                     change_rate, trading_value, trading_value_100m, current_price, data_status,
                     error_message, created_at, updated_at)
                    VALUES
                    (:theme_daily_return_id, :theme_id, :stock_id, :stock_code, :stock_name, :return_date,
                     :change_rate, :trading_value, :trading_value_100m, :current_price, 'success',
                     NULL, :now, :now)
                    ON CONFLICT(theme_id, stock_id, return_date) DO UPDATE SET
                        theme_daily_return_id=excluded.theme_daily_return_id,
                        stock_code=excluded.stock_code,
                        stock_name=excluded.stock_name,
                        change_rate=excluded.change_rate,
                        trading_value=excluded.trading_value,
                        trading_value_100m=excluded.trading_value_100m,
                        current_price=excluded.current_price,
                        data_status='success', error_message=NULL, updated_at=excluded.updated_at
                    """
                ),
                detail_params,
            )
            self.db.commit()
            inserted_count = sum(1 for return_date in valid_dates if return_date not in existing_by_date)
            updated_count = len(valid_dates) - inserted_count
            return MarketThemeReturnRecalculationResponse(
                success=True,
                theme_id=preview.theme_id,
                theme_name=preview.theme_name,
                connected_stock_count=connected_stock_count,
                period_from=period_from,
                period_to=period_to,
                processed_date_count=len(valid_dates),
                inserted_count=inserted_count,
                updated_count=updated_count,
                skipped_date_count=len(skipped_dates),
                recalculated_at=recalculated_at,
            )
        except Exception:
            self.db.rollback()
            raise
        finally:
            with self._theme_return_recalculation_state_lock:
                self._theme_return_recalculating_ids.discard(theme_id)

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
            linked_stocks = self._list_active_theme_return_stocks(theme_id)
            return MarketThemeLatestReturnResponse(
                theme_id=theme_id,
                theme_name=str(theme["theme_name"]),
                theme_group_name=theme["theme_group_name"],
                stock_count=len(linked_stocks),
                stocks=[
                    MarketThemeReturnStockItem(
                        **stock,
                        data_status="missing",
                    )
                    for stock in linked_stocks
                ],
            )

        stock_rows = self.db.execute(
            text(
                """
                SELECT s.id AS stock_id, s.stock_code, s.stock_name, mts.stock_memo,
                       returns.trading_value_100m, returns.change_rate, returns.current_price,
                       COALESCE(returns.data_status, 'missing') AS data_status, returns.error_message
                FROM market_theme_stocks mts
                JOIN stocks s ON s.id=mts.stock_id AND COALESCE(s.is_active, 1)=1
                LEFT JOIN market_theme_stock_daily_returns returns
                  ON returns.theme_daily_return_id=:daily_return_id
                 AND returns.stock_id=mts.stock_id
                 AND COALESCE(returns.data_status, 'missing')<>'inactive'
                WHERE mts.theme_id=:theme_id AND COALESCE(mts.is_active, 1)=1
                ORDER BY returns.data_status='success' DESC, COALESCE(returns.trading_value_100m, 0) DESC, s.stock_name ASC
                """
            ),
            {"daily_return_id": int(latest["id"]), "theme_id": theme_id},
        ).mappings().all()
        flow_summary, stock_flow_summaries = MarketThemeFlowAnalysisService(self.db).get_daily_context(
            theme_id, str(latest["return_date"])
        )
        stock_items = []
        for row in stock_rows:
            payload = dict(row)
            payload["flow_summary"] = stock_flow_summaries.get(int(row["stock_id"]))
            stock_items.append(MarketThemeReturnStockItem(**payload))
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
            flow_summary=flow_summary,
            stocks=stock_items,
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
        sort_by: str = "CURRENT_STRENGTH",
    ) -> MarketThemeMonthlyReturnResponse:
        try:
            end = date.fromisoformat(end_date)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date는 YYYY-MM-DD 형식이어야 합니다.")
        normalized_sort = str(sort_by or "CURRENT_STRENGTH").upper()
        if normalized_sort not in {"CURRENT_STRENGTH", "ROLLING_30D_RETURN"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sort_by는 CURRENT_STRENGTH 또는 ROLLING_30D_RETURN이어야 합니다.")
        normalized_days = max(1, min(int(days or 30), 120))
        start = end - timedelta(days=normalized_days - 1)
        calc_start = start - timedelta(days=59)
        params: dict[str, object] = {
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
                ORDER BY t.is_supply_theme DESC, COALESCE(p.theme_name, '미지정') ASC,
                         t.sort_order ASC, t.theme_name ASC, d.return_date ASC
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
                "observations": [],
            })
            if row["return_date"] and row["avg_change_rate"] is not None:
                item["observations"].append({
                    "return_date": str(row["return_date"]),
                    "avg_change_rate": float(row["avg_change_rate"]),
                    "total_trading_value_100m": row["total_trading_value_100m"],
                    "rising_stock_count": int(row["rising_stock_count"] or 0),
                    "falling_stock_count": int(row["falling_stock_count"] or 0),
                    "flat_stock_count": int(row["flat_stock_count"] or 0),
                })

        candidates: list[dict[str, object]] = []
        for item in grouped.values():
            observations = sorted(item["observations"], key=lambda row: str(row["return_date"]))
            rate_by_date = {
                date.fromisoformat(str(row["return_date"])): float(row["avg_change_rate"])
                for row in observations
            }
            rolling_by_date: dict[date, float] = {}
            for observation_date in rate_by_date:
                window_start = observation_date - timedelta(days=29)
                rolling_by_date[observation_date] = round(sum(
                    rate for rate_date, rate in rate_by_date.items()
                    if window_start <= rate_date <= observation_date
                ), 4)

            display_observations = [
                row for row in observations
                if start <= date.fromisoformat(str(row["return_date"])) <= end
            ]
            daily_returns = [
                MarketThemeMonthlyReturnDailyItem(
                    return_date=str(row["return_date"]),
                    avg_change_rate=float(row["avg_change_rate"]),
                    rolling_30d_change_rate=rolling_by_date.get(date.fromisoformat(str(row["return_date"]))),
                    total_trading_value_100m=row["total_trading_value_100m"],
                    rising_stock_count=int(row["rising_stock_count"]),
                    falling_stock_count=int(row["falling_stock_count"]),
                    flat_stock_count=int(row["flat_stock_count"]),
                )
                for row in display_observations
            ]
            display_rates = [float(row["avg_change_rate"]) for row in display_observations]
            compound: float | None = None
            if display_rates:
                accumulator = 1.0
                for rate in display_rates:
                    accumulator *= 1 + (rate / 100)
                compound = round((accumulator - 1) * 100, 4)
            sum_return = round(sum(display_rates), 4) if display_rates else None
            trading_value = round(sum(float(row["total_trading_value_100m"] or 0) for row in display_observations), 4)
            continuous_rising = 0
            for row in reversed(display_observations):
                if float(row["avg_change_rate"]) > 0:
                    continuous_rising += 1
                else:
                    break

            recent_observations = observations[-10:]
            observed_days = len(recent_observations)
            positive_days = sum(1 for row in recent_observations if float(row["avg_change_rate"]) > 0)
            weighted_return: float | None = None
            persistence: float | None = None
            recent_5d: float | None = None
            previous_5d: float | None = None
            momentum_delta: float | None = None
            last_impulse_date: str | None = None
            days_since_impulse: int | None = None
            freshness: float | None = None
            if observed_days >= 5:
                weights = list(range(1, observed_days + 1))
                weighted_return = round(sum(float(row["avg_change_rate"]) * weight for row, weight in zip(recent_observations, weights)) / sum(weights), 4)
                persistence = round((positive_days / observed_days) * 100, 2)
                recent_5d = round(sum(float(row["avg_change_rate"]) for row in recent_observations[-5:]), 4)
                previous_rows = recent_observations[-10:-5]
                previous_5d = round(sum(float(row["avg_change_rate"]) for row in previous_rows), 4)
                momentum_delta = round(recent_5d - previous_5d, 4)
                impulse_window = observations[-30:]
                for index in range(len(impulse_window) - 1, -1, -1):
                    if float(impulse_window[index]["avg_change_rate"]) >= 3:
                        last_impulse_date = str(impulse_window[index]["return_date"])
                        days_since_impulse = len(impulse_window) - 1 - index
                        break
                freshness = float(max(0, 100 - (days_since_impulse * 10))) if days_since_impulse is not None else 0.0

            latest_observation_date = max(rate_by_date) if rate_by_date else None
            rolling_30d = rolling_by_date.get(latest_observation_date) if latest_observation_date else None
            display_rolling_values = [
                value for rolling_date, value in rolling_by_date.items()
                if start <= rolling_date <= end
            ]
            rolling_peak = round(max(display_rolling_values), 4) if display_rolling_values else rolling_30d
            rolling_peak_gap = round(rolling_30d - rolling_peak, 4) if rolling_30d is not None and rolling_peak is not None else None
            candidates.append({
                **item,
                "daily_returns": daily_returns,
                "monthly_compound_return": compound,
                "monthly_sum_return": sum_return,
                "period_compound_return": compound,
                "period_sum_return": sum_return,
                "total_trading_value_100m": trading_value,
                "rising_days": sum(1 for rate in display_rates if rate > 0),
                "falling_days": sum(1 for rate in display_rates if rate < 0),
                "flat_days": sum(1 for rate in display_rates if rate == 0),
                "data_days": len(display_rates),
                "continuous_rising_days": continuous_rising,
                "rolling_30d_change_rate": rolling_30d,
                "weighted_return_10d": weighted_return,
                "positive_days_10d": positive_days,
                "observed_days_10d": observed_days,
                "persistence_10d": persistence,
                "recent_5d_return": recent_5d,
                "previous_5d_return": previous_5d,
                "momentum_delta": momentum_delta,
                "last_positive_impulse_date": last_impulse_date,
                "days_since_positive_impulse": days_since_impulse,
                "freshness_score": freshness,
                "rolling_30d_peak": rolling_peak,
                "rolling_30d_peak_gap": rolling_peak_gap,
            })

        def percentile_scores(field: str) -> dict[int, float]:
            values = [(int(row["theme_id"]), float(row[field])) for row in candidates if row.get(field) is not None]
            if not values:
                return {}
            ordered = sorted(value for _, value in values)
            if len(ordered) == 1:
                return {values[0][0]: 100.0}
            scores: dict[int, float] = {}
            for theme_id, value in values:
                lower = sum(1 for candidate in ordered if candidate < value)
                equal = sum(1 for candidate in ordered if candidate == value)
                average_index = lower + ((equal - 1) / 2)
                scores[theme_id] = round((average_index / (len(ordered) - 1)) * 100, 2)
            return scores

        weighted_scores = percentile_scores("weighted_return_10d")
        momentum_scores = percentile_scores("momentum_delta")
        for row in candidates:
            theme_id = int(row["theme_id"])
            weighted_score = weighted_scores.get(theme_id)
            momentum_score = momentum_scores.get(theme_id)
            persistence = row.get("persistence_10d")
            recent_5d = row.get("recent_5d_return")
            momentum_delta = row.get("momentum_delta")
            rolling_30d = row.get("rolling_30d_change_rate")
            peak_gap = row.get("rolling_30d_peak_gap")
            stale_penalty = 0.0
            if rolling_30d is not None and float(rolling_30d) > 0 and recent_5d is not None and float(recent_5d) < 0:
                stale_penalty += 5
            if persistence is not None and float(persistence) < 40:
                stale_penalty += 5
            if momentum_delta is not None and float(momentum_delta) < 0:
                stale_penalty += 5
            if peak_gap is not None and float(peak_gap) <= -8:
                stale_penalty += 5
            score: float | None = None
            status_code = "INSUFFICIENT"
            status_name = "데이터 부족"
            if weighted_score is not None and momentum_score is not None and persistence is not None:
                raw_score = weighted_score * 0.45 + float(persistence) * 0.25 + momentum_score * 0.20 + float(row.get("freshness_score") or 0) * 0.10 - stale_penalty
                score = round(min(100, max(0, raw_score)), 2)
                if score < 30 and float(recent_5d or 0) < 0 and float(persistence) < 40:
                    status_code, status_name = "FADING", "소멸"
                elif float(rolling_30d or 0) > 0 and (float(recent_5d or 0) < 0 or float(momentum_delta or 0) < 0 or float(persistence) < 50):
                    status_code, status_name = "SLOWDOWN", "둔화"
                elif float(recent_5d or 0) > 0 and float(momentum_delta or 0) > 0 and float(row.get("previous_5d_return") or 0) <= 0:
                    status_code, status_name = "IGNITION", "점화"
                elif score >= 60 and float(recent_5d or 0) >= 0 and float(persistence) >= 60:
                    status_code, status_name = "PERSISTENT", "지속"
                else:
                    status_code, status_name = "NEUTRAL", "중립"
            row.update({
                "weighted_return_score": weighted_score,
                "momentum_score": momentum_score,
                "stale_penalty": stale_penalty,
                "theme_strength_score": score,
                "strength_status_code": status_code,
                "strength_status_name": status_name,
            })
            logger.debug(
                "[theme-strength] reference_date=%s theme_id=%s theme_name=%s weighted_return_10d=%s weighted_return_score=%s persistence_10d=%s recent_5d_return=%s previous_5d_return=%s momentum_delta=%s momentum_score=%s freshness_score=%s stale_penalty=%s final_score=%s status=%s",
                end.isoformat(), theme_id, row["theme_name"], row.get("weighted_return_10d"), weighted_score,
                persistence, recent_5d, row.get("previous_5d_return"), momentum_delta, momentum_score,
                row.get("freshness_score"), stale_penalty, score, status_code,
            )

        def assign_rank(value_field: str, rank_field: str) -> None:
            ranked = sorted(
                [row for row in candidates if row.get(value_field) is not None],
                key=lambda row: (-float(row[value_field]), str(row["theme_name"])),
            )
            previous_value: float | None = None
            previous_rank = 0
            for index, row in enumerate(ranked, start=1):
                value = float(row[value_field])
                rank = previous_rank if previous_value is not None and value == previous_value else index
                row[rank_field] = rank
                previous_value, previous_rank = value, rank

        assign_rank("theme_strength_score", "current_strength_rank")
        assign_rank("rolling_30d_change_rate", "rolling_30d_rank")
        assign_rank("persistence_10d", "persistence_rank")
        theme_items = [MarketThemeMonthlyReturnThemeItem(**row) for row in candidates]

        def to_top(theme: MarketThemeMonthlyReturnThemeItem | None) -> MarketThemeMonthlyReturnSummaryTopItem | None:
            if theme is None:
                return None
            continuous_rising = next((int(row.get("continuous_rising_days") or 0) for row in candidates if int(row["theme_id"]) == theme.theme_id), 0)
            return MarketThemeMonthlyReturnSummaryTopItem(
                theme_id=theme.theme_id,
                theme_name=theme.theme_name,
                monthly_compound_return=theme.monthly_compound_return,
                period_compound_return=theme.period_compound_return,
                total_trading_value_100m=theme.total_trading_value_100m,
                continuous_rising_days=continuous_rising,
                rolling_30d_change_rate=theme.rolling_30d_change_rate,
                theme_strength_score=theme.theme_strength_score,
                persistence_10d=theme.persistence_10d,
                strength_status_code=theme.strength_status_code,
                strength_status_name=theme.strength_status_name,
            )

        with_rolling = [theme for theme in theme_items if theme.rolling_30d_change_rate is not None]
        with_strength = [theme for theme in theme_items if theme.theme_strength_score is not None]
        with_persistence = [theme for theme in theme_items if theme.persistence_10d is not None]
        current_top = max(with_strength, key=lambda theme: theme.theme_strength_score or 0) if with_strength else None
        rolling_top = max(with_rolling, key=lambda theme: theme.rolling_30d_change_rate or 0) if with_rolling else None
        trading_top = max(theme_items, key=lambda theme: theme.total_trading_value_100m or 0) if theme_items else None
        persistence_top = max(with_persistence, key=lambda theme: theme.persistence_10d or 0) if with_persistence else None
        with_return = [theme for theme in theme_items if theme.monthly_compound_return is not None]
        continuous_candidates = [theme for theme in theme_items if next((int(row.get("continuous_rising_days") or 0) for row in candidates if int(row["theme_id"]) == theme.theme_id), 0) > 0]
        top_continuous = max(continuous_candidates, key=lambda theme: next((int(row.get("continuous_rising_days") or 0) for row in candidates if int(row["theme_id"]) == theme.theme_id), 0)) if continuous_candidates else None
        summary = MarketThemeMonthlyReturnSummary(
            top_rising_theme=to_top(max(with_return, key=lambda theme: theme.monthly_compound_return or 0) if with_return else None),
            top_falling_theme=to_top(min(with_return, key=lambda theme: theme.monthly_compound_return or 0) if with_return else None),
            top_trading_value_theme=to_top(trading_top),
            rising_day_theme=to_top(max(theme_items, key=lambda theme: theme.rising_days) if theme_items else None),
            top_continuous_rising_theme=to_top(top_continuous),
            current_strength_top=to_top(current_top),
            rolling_30d_top=to_top(rolling_top),
            trading_value_top=to_top(trading_top),
            persistence_top=to_top(persistence_top),
        )

        if normalized_sort == "ROLLING_30D_RETURN":
            theme_items.sort(key=lambda theme: (theme.rolling_30d_change_rate is None, -(theme.rolling_30d_change_rate or 0), theme.theme_name))
        else:
            theme_items.sort(key=lambda theme: (theme.theme_strength_score is None, -(theme.theme_strength_score or 0), theme.theme_name))
        if limit and limit > 0:
            theme_items = theme_items[:limit]
        from backend.app.services.market_theme_observation_service import MarketThemeObservationService
        observation_cutoff = self.db.execute(text(
            "SELECT MAX(return_date) FROM market_theme_daily_returns WHERE return_date<=:end_date"
        ), {"end_date": end.isoformat()}).scalar()
        prediction = MarketThemeObservationService(self.db).prediction_for_cutoff(str(observation_cutoff)) if observation_cutoff else None
        return MarketThemeMonthlyReturnResponse(
            month=end.isoformat()[:7],
            end_date=end.isoformat(),
            days=normalized_days,
            active_only=active_only,
            display_start_date=start.isoformat(),
            display_end_date=end.isoformat(),
            sort_by=normalized_sort,
            themes=theme_items,
            summary=summary,
            prediction=prediction,
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
            # The flow heatmap can have a valid investor-flow cell even when the
            # legacy theme-return snapshot was not saved for that theme/date.
            # Build a transient drawer payload from the current active links and
            # already-saved daily price/flow rows instead of reporting no stocks.
            fallback_rows = self.db.execute(
                text(
                    """
                    SELECT s.id AS stock_id, s.stock_code, s.stock_name, mts.stock_memo,
                           CASE WHEN p.trading_value IS NULL THEN NULL ELSE p.trading_value / 100.0 END AS trading_value_100m,
                           p.change_rate, CAST(p.close_price AS INTEGER) AS current_price,
                           CASE WHEN p.stock_id IS NULL THEN 'missing' ELSE 'success' END AS data_status,
                           NULL AS error_message
                    FROM market_theme_stocks mts
                    JOIN stocks s ON s.id=mts.stock_id AND COALESCE(s.is_active, 1)=1
                    LEFT JOIN stock_daily_prices p
                      ON p.stock_id=mts.stock_id AND p.trade_date=:return_date
                    WHERE mts.theme_id=:theme_id AND COALESCE(mts.is_active, 1)=1
                    ORDER BY p.stock_id IS NOT NULL DESC, COALESCE(p.trading_value, 0) DESC, s.stock_name ASC
                    """
                ),
                {"theme_id": theme_id, "return_date": return_date},
            ).mappings().all()
            flow_summary, stock_flow_summaries = MarketThemeFlowAnalysisService(self.db).get_daily_context(
                theme_id, return_date
            )
            stock_items: list[MarketThemeReturnStockItem] = []
            change_rates: list[float] = []
            total_trading_value_100m = 0.0
            trading_value_seen = False
            success_stock_count = rising_stock_count = falling_stock_count = flat_stock_count = 0
            for row in fallback_rows:
                payload = dict(row)
                payload["flow_summary"] = stock_flow_summaries.get(int(row["stock_id"]))
                stock_items.append(MarketThemeReturnStockItem(**payload))
                if row["data_status"] == "success":
                    success_stock_count += 1
                if row["change_rate"] is not None:
                    rate = float(row["change_rate"])
                    change_rates.append(rate)
                    rising_stock_count += int(rate > 0)
                    falling_stock_count += int(rate < 0)
                    flat_stock_count += int(rate == 0)
                if row["trading_value_100m"] is not None:
                    total_trading_value_100m += float(row["trading_value_100m"])
                    trading_value_seen = True
            return MarketThemeLatestReturnResponse(
                theme_id=theme_id,
                theme_name=str(theme["theme_name"]),
                theme_group_name=theme["theme_group_name"],
                return_date=return_date,
                avg_change_rate=round(sum(change_rates) / len(change_rates), 4) if change_rates else None,
                stock_count=len(fallback_rows),
                success_stock_count=success_stock_count,
                failed_stock_count=0,
                rising_stock_count=rising_stock_count,
                falling_stock_count=falling_stock_count,
                flat_stock_count=flat_stock_count,
                total_trading_value_100m=round(total_trading_value_100m, 4) if trading_value_seen else None,
                flow_summary=flow_summary,
                stocks=stock_items,
            )
        stock_rows = self.db.execute(
            text(
                """
                SELECT returns.stock_id, returns.stock_code, returns.stock_name, mts.stock_memo,
                       returns.trading_value_100m, returns.change_rate, returns.current_price,
                       returns.data_status, returns.error_message
                FROM market_theme_stock_daily_returns returns
                LEFT JOIN market_theme_stocks mts
                  ON mts.theme_id=:theme_id AND mts.stock_id=returns.stock_id
                WHERE returns.theme_daily_return_id=:daily_return_id
                  AND COALESCE(data_status, 'missing')<>'inactive'
                ORDER BY data_status='success' DESC, COALESCE(trading_value, 0) DESC, stock_name ASC
                """
            ),
            {"daily_return_id": int(daily["id"]), "theme_id": theme_id},
        ).mappings().all()
        flow_summary, stock_flow_summaries = MarketThemeFlowAnalysisService(self.db).get_daily_context(
            theme_id, str(daily["return_date"])
        )
        stock_items = []
        for row in stock_rows:
            payload = dict(row)
            payload["flow_summary"] = stock_flow_summaries.get(int(row["stock_id"]))
            stock_items.append(MarketThemeReturnStockItem(**payload))
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
            flow_summary=flow_summary,
            stocks=stock_items,
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
                    s.market,
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
                SELECT s.id AS stock_id, s.stock_code, s.stock_name, mts.stock_memo
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

    @staticmethod
    def _summarize_theme_return_rows(
        stock_results: list[dict[str, object]],
        *,
        connected_stock_count: int,
    ) -> dict[str, object]:
        success_results = [
            row
            for row in stock_results
            if row.get("data_status") == "success" and row.get("change_rate") is not None
        ]
        change_rates = [float(row["change_rate"]) for row in success_results]
        total_trading_value = sum(int(row.get("trading_value") or 0) for row in success_results)
        return {
            "stock_count": connected_stock_count,
            "success_stock_count": len(success_results),
            "failed_stock_count": max(0, connected_stock_count - len(success_results)),
            "avg_change_rate": round(sum(change_rates) / len(change_rates), 4) if change_rates else None,
            "total_trading_value": total_trading_value,
            "total_trading_value_100m": round(total_trading_value / 100_000_000, 4) if total_trading_value else 0.0,
            "rising_count": sum(1 for rate in change_rates if rate > 0),
            "falling_count": sum(1 for rate in change_rates if rate < 0),
            "flat_count": sum(1 for rate in change_rates if rate == 0),
        }

    def _load_saved_theme_stock_returns(
        self,
        stocks: dict[int, dict[str, object]],
        return_date: str,
    ) -> dict[int, dict[str, object]]:
        if not stocks:
            return {}
        params: dict[str, object] = {"return_date": return_date}
        placeholders: list[str] = []
        for index, stock_id in enumerate(stocks):
            key = f"stock_id_{index}"
            placeholders.append(f":{key}")
            params[key] = stock_id
        rows = self.db.execute(
            text(
                f"""
                SELECT stock_id, change_rate, trading_value, close_price
                FROM stock_daily_prices
                WHERE trade_date=:return_date
                  AND stock_id IN ({", ".join(placeholders)})
                """
            ),
            params,
        ).mappings().all()
        rows_by_stock = {int(row["stock_id"]): row for row in rows}
        results: dict[int, dict[str, object]] = {}
        for stock_id, stock in stocks.items():
            stock_code = normalize_stock_code(str(stock.get("stock_code") or ""))
            saved = rows_by_stock.get(stock_id)
            raw_trading_value = self._to_int_or_none(saved.get("trading_value")) if saved else None
            trading_value = raw_trading_value * 1_000_000 if raw_trading_value is not None else None
            change_rate = float(saved["change_rate"]) if saved and saved.get("change_rate") is not None else None
            results[stock_id] = {
                "stock_id": stock_id,
                "stock_code": stock_code,
                "stock_name": str(stock.get("stock_name") or stock_code),
                "change_rate": change_rate,
                "trading_value": trading_value,
                "trading_value_100m": round(raw_trading_value / 100.0, 4) if raw_trading_value is not None else None,
                "current_price": self._to_abs_int(saved.get("close_price")) if saved else None,
                "data_status": "success" if saved and change_rate is not None else "missing",
                "error_message": None if saved and change_rate is not None else "saved_price_missing",
            }
        return results

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
