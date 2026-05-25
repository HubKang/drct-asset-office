from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.clients.kiwoom import KiwoomApiError
from backend.app.core.config import now_kst
from backend.app.providers.market_data.kiwoom_rest_condition_provider import KiwoomRestConditionProvider
from backend.app.schemas.external_kiwoom_schema import (
    DailyThemeFlowStockItem,
    DailyThemeRanksUpdateRequest,
    DailyThemeRanksUpdateResponse,
    DailyThemeFlowStocksResponse,
    DailyThemeFlowSummaryItem,
    DailyThemeFlowSummaryResponse,
    MonthlyThemeFlowCalendarDayItem,
    MonthlyThemeFlowCalendarResponse,
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
                            raw_json=:raw_json
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
                        "raw_json": json.dumps(item.raw, ensure_ascii=False) if item.raw else None,
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
                     :detected_at, :source, :source_api, :raw_json, :created_at)
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
                    "raw_json": json.dumps(item.raw, ensure_ascii=False) if item.raw else None,
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
            rate = rate / 1000.0
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
            condition_seq=str(condition_seq),
            condition_name=payload.condition_name,
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
        trade_date = datetime.now().strftime("%Y-%m-%d")
        saved_count = 0
        updated_count = 0
        unmatched_items: list[str] = []

        for item in payload.items:
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
                {"trade_date": trade_date, "stock_id": stock_id, "condition_seq": payload.condition_seq},
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
                        "detected_at": now,
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
                        "trade_date": trade_date,
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
                        "detected_at": now,
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
                SELECT
                    mt.id AS market_theme_id,
                    mt.theme_name AS theme_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT mte.stock_code) AS stock_count,
                    AVG(mte.change_rate) AS avg_change_rate,
                    MAX(mte.change_rate) AS max_change_rate,
                    SUM(COALESCE(mte.trading_value, 0)) AS estimated_trading_value_sum
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                WHERE mte.trade_date = :trade_date
                  AND mte.detection_source = 'kiwoom_condition'
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
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
                SELECT
                    mt.id AS market_theme_id,
                    mte.stock_name,
                    mte.change_rate,
                    ROW_NUMBER() OVER (
                        PARTITION BY mt.id
                        ORDER BY mte.change_rate DESC, mte.stock_name ASC
                    ) AS rn
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                WHERE mte.trade_date = :trade_date
                  AND mte.detection_source = 'kiwoom_condition'
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
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
        sorted_auto = sorted(
            items,
            key=lambda x: (
                -999999 if x.avg_change_rate is None else -float(x.avg_change_rate),
                -int(x.stock_count),
                -int(x.event_count),
                -int(x.estimated_trading_value_sum),
                str(x.theme_name),
            ),
        )
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
        for item in items:
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
                    rank_score=float(self._rank_score(final_rank)),
                    rank_basis=rank_basis,
                )
            )
        ranked.sort(
            key=lambda x: (
                999999 if x.final_rank is None else int(x.final_rank),
                -float(x.rank_score or 0),
                -999999 if x.avg_change_rate is None else -float(x.avg_change_rate),
                -int(x.stock_count),
                str(x.theme_name),
            )
        )
        return ranked

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
            rank_score = float(self._rank_score(final_rank))

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
                SELECT
                    mte.id AS event_id,
                    mt.id AS market_theme_id,
                    mt.theme_name AS theme_name,
                    mte.stock_code AS stock_code,
                    COALESCE(mte.stock_name, s.stock_name) AS stock_name,
                    mte.change_rate AS change_rate,
                    mte.condition_seq AS condition_seq,
                    mte.condition_name AS condition_name,
                    mte.trading_value AS trading_value
                FROM market_trend_events mte
                JOIN market_trend_event_theme_links l ON l.event_id = mte.id
                JOIN market_themes mt ON mt.id = l.market_theme_id
                LEFT JOIN stocks s ON s.id = mte.stock_id
                WHERE mte.trade_date = :trade_date
                  AND mt.id = :market_theme_id
                  AND mte.detection_source = 'kiwoom_condition'
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
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
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                GROUP BY mte.trade_date, mt.id, mt.theme_name
                ORDER BY mte.trade_date ASC, stock_count DESC, event_count DESC, estimated_trading_value_sum DESC, avg_change_rate DESC, mt.theme_name ASC
                """
            ),
            {"start_date": month_start.isoformat(), "end_date": month_end.isoformat()},
        ).mappings().all()

        grouped: dict[str, list[DailyThemeFlowSummaryItem]] = {}
        for row in rows:
            trade_date = str(row["trade_date"])
            grouped.setdefault(trade_date, []).append(
                DailyThemeFlowSummaryItem(
                    market_theme_id=int(row["market_theme_id"]),
                    theme_name=str(row["theme_name"]),
                    stock_count=int(row["stock_count"] or 0),
                    event_count=int(row["event_count"] or 0),
                    avg_change_rate=float(row["avg_change_rate"]) if row["avg_change_rate"] is not None else None,
                    max_change_rate=float(row["max_change_rate"]) if row["max_change_rate"] is not None else None,
                    estimated_trading_value_sum=int(row["estimated_trading_value_sum"] or 0),
                    representative_stocks=[],
                )
            )

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
                    rank_score=float(item.rank_score),
                    rank_basis=item.rank_basis,
                )
                for idx, item in enumerate(ranked_day)
            ]
            days.append(MonthlyThemeFlowCalendarDayItem(trade_date=key, themes=ranked))
            cursor += timedelta(days=1)

        return MonthlyThemeFlowCalendarResponse(
            success=True,
            month=month,
            start_date=month_start.isoformat(),
            end_date=month_end.isoformat(),
            days=days,
        )

    def get_monthly_theme_flow_trend(self, month: str) -> MonthlyThemeFlowTrendResponse:
        month_start, month_end = self._resolve_month_window(month)
        rows = self.db.execute(
            text(
                """
                SELECT
                    mte.trade_date AS trade_date,
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
                WHERE mte.trade_date BETWEEN :start_date AND :end_date
                  AND mte.detection_source IN ('kiwoom_condition', 'kiwoom_rest')
                  AND COALESCE(mte.is_active, 1) = 1
                  AND COALESCE(l.is_active, 1) = 1
                  AND COALESCE(mt.is_active, 1) = 1
                  AND COALESCE(mte.deleted_at, '') = ''
                  AND COALESCE(l.deleted_at, '') = ''
                GROUP BY mte.trade_date, mt.id, mt.theme_name
                """
            ),
            {"start_date": month_start.isoformat(), "end_date": month_end.isoformat()},
        ).mappings().all()

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
        for key in date_keys:
            ranked = self._apply_rank_overrides(trade_date=key, items=by_date.get(key, []))
            day_ranked[key] = ranked
            for item in ranked:
                score = int(item.rank_score or 0)
                total_score_map[item.market_theme_id] = total_score_map.get(item.market_theme_id, 0) + score
                theme_name_map[item.market_theme_id] = item.theme_name

        sorted_theme_ids = sorted(total_score_map.keys(), key=lambda tid: (total_score_map.get(tid, 0), theme_name_map.get(tid, "")), reverse=True)

        themes: list[MonthlyThemeFlowTrendTheme] = []
        for theme_id in sorted_theme_ids:
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
            themes.append(
                MonthlyThemeFlowTrendTheme(
                    market_theme_id=theme_id,
                    theme_name=theme_name_map.get(theme_id, str(theme_id)),
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
                SELECT id AS event_id, trade_date, stock_code, stock_name, market_type, change_rate,
                       theme_status, condition_seq, condition_name, user_memo, detected_at, updated_at
                FROM market_trend_events
                WHERE detection_source='kiwoom_condition'
                  AND trade_date=:trade_date
                  AND is_active=1
                ORDER BY detected_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"trade_date": trade_date, "limit": limit},
        ).mappings().all()
        return KiwoomMarketEventListResponse(items=[KiwoomMarketEventItemOut(**dict(r)) for r in rows])

    def patch_market_event(self, event_id: int, payload: KiwoomMarketEventPatchRequest) -> KiwoomMarketEventPatchResponse:
        existing = self.db.execute(
            text(
                """
                SELECT id AS event_id, trade_date, stock_code, stock_name, market_type, change_rate,
                       theme_status, condition_seq, condition_name, user_memo, detected_at, updated_at
                FROM market_trend_events
                WHERE id=:event_id
                  AND detection_source='kiwoom_condition'
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
                       theme_status, condition_seq, condition_name, user_memo, detected_at, updated_at
                FROM market_trend_events
                WHERE id=:event_id
                LIMIT 1
                """
            ),
            {"event_id": event_id},
        ).mappings().first()
        return KiwoomMarketEventPatchResponse(success=True, item=KiwoomMarketEventItemOut(**dict(row)))

    def delete_market_event(self, event_id: int) -> KiwoomMarketEventDeleteResponse:
        now = now_kst()
        existing = self.db.execute(
            text("SELECT id FROM market_trend_events WHERE id=:event_id AND detection_source='kiwoom_condition'"),
            {"event_id": event_id},
        ).mappings().first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수급 이벤트 후보를 찾을 수 없습니다.")

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
        self.db.commit()
        return KiwoomMarketEventDeleteResponse(success=True, event_id=event_id)

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
            text("SELECT id FROM market_trend_events WHERE id=:event_id AND is_active=1 AND detection_source='kiwoom_condition'"),
            {"event_id": event_id},
        ).mappings().first()
        if not event_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수급 이벤트 후보를 찾을 수 없습니다.")
        theme_row = self.db.execute(
            text("SELECT id, theme_name FROM market_themes WHERE id=:theme_id AND is_active=1"),
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
        return KiwoomMarketEventThemeLinkAddResponse(success=True, item=KiwoomMarketEventThemeLinkItemOut(**dict(row)))

    def remove_market_event_theme(self, event_id: int, link_id: int) -> KiwoomMarketEventThemeLinkDeleteResponse:
        now = now_kst()
        row = self.db.execute(
            text("SELECT id FROM market_trend_event_theme_links WHERE id=:link_id AND event_id=:event_id AND is_active=1"),
            {"link_id": link_id, "event_id": event_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="테마 연결을 찾을 수 없습니다.")
        self.db.execute(
            text("UPDATE market_trend_event_theme_links SET is_active=0, deleted_at=:deleted_at, updated_at=:updated_at WHERE id=:id"),
            {"id": link_id, "deleted_at": now, "updated_at": now},
        )
        self.db.commit()
        return KiwoomMarketEventThemeLinkDeleteResponse(success=True, link_id=link_id)
