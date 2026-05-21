from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.schemas.external_kiwoom_schema import (
    DailyThemeFlowStockItem,
    DailyThemeFlowStocksResponse,
    DailyThemeFlowSummaryItem,
    DailyThemeFlowSummaryResponse,
    KiwoomConditionListResponse,
    KiwoomConditionResultListResponse,
    KiwoomConditionResultItemOut,
    KiwoomConditionPreviewRequest,
    KiwoomConditionPreviewResponse,
    KiwoomConditionResultSaveRequest,
    KiwoomConditionResultSaveResponse,
    KiwoomConditionSyncRequest,
    KiwoomConditionSyncResponse,
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
                ORDER BY is_active DESC, updated_at DESC, id DESC
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
        repo_root = Path(__file__).resolve().parents[3]
        script_path = repo_root / "kiwoom-rest-agent" / "run_condition_once.py"
        if not script_path.exists():
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Agent script not found.")

        python_candidates = [
            repo_root / ".venv" / "Scripts" / "python.exe",
            repo_root / ".venv" / "bin" / "python",
        ]
        python_cmd = None
        for candidate in python_candidates:
            if candidate.exists():
                python_cmd = str(candidate)
                break
        if python_cmd is None:
            python_cmd = "python"

        cmd = [
            python_cmd,
            str(script_path),
            "--condition-seq",
            str(condition_seq),
            "--condition-name",
            payload.condition_name or "",
            "--header-mode",
            payload.header_mode,
            "--login-mode",
            payload.login_mode,
            "--search-type",
            payload.search_type,
            "--stex-tp",
            payload.stex_tp,
            "--json-output",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=90,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Condition preview timed out.")

        summary = self._extract_summary_json(proc.stdout)
        if summary is None:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to parse condition preview output.")

        items_raw = summary.get("items") if isinstance(summary.get("items"), list) else []
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

        success = bool(summary.get("success"))
        error_message = None if success else str(summary.get("error") or "Condition preview failed")
        return KiwoomConditionPreviewResponse(
            success=success,
            condition_seq=str(condition_seq),
            condition_name=payload.condition_name,
            item_count=len(items),
            items=items,
            error_message=error_message,
        )

    @staticmethod
    def _extract_summary_json(stdout_text: str) -> dict | None:
        for line in reversed([x.strip() for x in stdout_text.splitlines() if x.strip()]):
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            if isinstance(data, dict) and "success" in data and "condition_seq" in data:
                return data
        return None

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
        return DailyThemeFlowSummaryResponse(success=True, trade_date=trade_date, items=items)

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
