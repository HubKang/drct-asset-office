from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from statistics import median
from threading import Lock

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.providers.market_data.kiwoom_rest_market_indicator_provider import KiwoomRestMarketIndicatorProvider
from backend.app.schemas.realtime_theme_schema import (
    RealtimeThemeRefreshResponse,
    RealtimeThemeStockItem,
    RealtimeThemeStocksResponse,
    RealtimeThemeTreemapResponse,
)
from backend.app.utils.stock_code import normalize_stock_code


logger = logging.getLogger(__name__)
_refresh_lock = Lock()


def calculate_trimmed_mean(values: list[float]) -> float | None:
    """Return the 20% two-sided trimmed mean for sufficiently large samples."""
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) < 5:
        return sum(ordered) / len(ordered)
    trim_count = math.floor(len(ordered) * 0.20)
    trimmed = ordered[trim_count:len(ordered) - trim_count]
    return sum(trimmed) / len(trimmed)


def calculate_theme_strength(values: list[float], market_median: float) -> float | None:
    """Calculate transient price strength from an existing realtime snapshot."""
    if not values:
        return None
    normalized = [float(value) for value in values]
    trimmed_mean = calculate_trimmed_mean(normalized)
    if trimmed_mean is None:
        return None
    robust_return = 0.6 * trimmed_mean + 0.4 * float(median(normalized))
    if robust_return > 0:
        breadth = sum(1 for value in normalized if value > 0) / len(normalized)
    elif robust_return < 0:
        breadth = sum(1 for value in normalized if value < 0) / len(normalized)
    else:
        breadth = 0.5
    breadth_factor = 0.85 + 0.30 * breadth
    confidence_weight = len(normalized) / (len(normalized) + 2)
    return confidence_weight * (robust_return * breadth_factor) + (1 - confidence_weight) * float(market_median)


class RealtimeThemeService:
    """Maintains only the current intraday theme snapshot.

    Provider payloads and failed samples stay transient. The durable allow-list is
    trade_date, theme_id, stock_id, change_rate, and collected_at. The legacy
    nullable trading_value column is deliberately unused by this feature.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def refresh(self) -> RealtimeThemeRefreshResponse:
        if not _refresh_lock.acquire(blocking=False):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="실시간 테마 수집이 이미 진행 중입니다.")
        started = time.perf_counter()
        try:
            collected_at = now_kst()
            trade_date = collected_at[:10]
            themes, links = self._active_themes_and_links()
            unique_stocks: dict[int, dict[str, object]] = {}
            for link in links:
                unique_stocks.setdefault(int(link["stock_id"]), link)

            provider = KiwoomRestMarketIndicatorProvider()
            quotes: dict[int, float] = {}
            failures: dict[int, str] = {}
            stock_fetch_times_ms: list[int] = []
            price_api_call_count = 0
            kiwoom_started = time.perf_counter()
            for stock_id, stock in unique_stocks.items():
                stock_code = normalize_stock_code(str(stock.get("stock_code") or ""))
                if len(stock_code) != 6:
                    failures[stock_id] = "invalid_stock_code"
                    continue
                try:
                    stock_started = time.perf_counter()
                    price_api_call_count += 1
                    basic = provider.get_stock_basic_info(stock_code=stock_code)
                    rate = self._normalize_change_rate(basic.get("change_rate"))
                    if rate is None:
                        failures[stock_id] = "change_rate_missing"
                    else:
                        quotes[stock_id] = rate
                except Exception as exc:  # individual symbols must not abort a partial refresh
                    failures[stock_id] = str(exc)[:200]
                finally:
                    if 'stock_started' in locals():
                        stock_fetch_times_ms.append(int((time.perf_counter() - stock_started) * 1000))
                        del stock_started
            kiwoom_fetch_ms = int((time.perf_counter() - kiwoom_started) * 1000)

            if unique_stocks and not quotes:
                self.db.rollback()
                sample = next(iter(failures.values()), "provider_error")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Kiwoom 실시간 시세를 한 건도 수집하지 못했습니다. 기존 Snapshot은 유지됩니다. ({sample})",
                )

            # Reconcile the complete active relationship set atomically. Failed
            # symbols are intentionally absent instead of reusing stale values.
            db_started = time.perf_counter()
            self.db.execute(text("DELETE FROM market_theme_realtime_returns WHERE trade_date<>:trade_date"), {"trade_date": trade_date})
            self.db.execute(text("DELETE FROM market_theme_realtime_returns WHERE trade_date=:trade_date"), {"trade_date": trade_date})
            for link in links:
                stock_id = int(link["stock_id"])
                if stock_id not in quotes:
                    continue
                change_rate = quotes[stock_id]
                self.db.execute(
                    text(
                        """
                        INSERT INTO market_theme_realtime_returns
                            (trade_date, theme_id, stock_id, change_rate, collected_at)
                        VALUES (:trade_date, :theme_id, :stock_id, :change_rate, :collected_at)
                        ON CONFLICT(trade_date, theme_id, stock_id) DO UPDATE SET
                            change_rate=excluded.change_rate,
                            collected_at=excluded.collected_at
                        """
                    ),
                    {
                        "trade_date": trade_date,
                        "theme_id": int(link["theme_id"]),
                        "stock_id": stock_id,
                        "change_rate": change_rate,
                        "collected_at": collected_at,
                    },
                )
            self.db.commit()
            db_upsert_ms = int((time.perf_counter() - db_started) * 1000)

            response_started = time.perf_counter()
            snapshot, theme_aggregation_ms = self._get_treemap_with_metrics()
            snapshot_response_ms = int((time.perf_counter() - response_started) * 1000)
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "Realtime theme refresh date=%s themes=%s links=%s unique_stocks=%s success=%s failed=%s api_calls=%s kiwoom_ms=%s db_ms=%s aggregation_ms=%s response_ms=%s duration_ms=%s stock_min_ms=%s stock_avg_ms=%s stock_max_ms=%s",
                trade_date, len(themes), len(links), len(unique_stocks), len(quotes), len(failures), price_api_call_count,
                kiwoom_fetch_ms, db_upsert_ms, theme_aggregation_ms, snapshot_response_ms, duration_ms,
                min(stock_fetch_times_ms) if stock_fetch_times_ms else None,
                round(sum(stock_fetch_times_ms) / len(stock_fetch_times_ms), 2) if stock_fetch_times_ms else None,
                max(stock_fetch_times_ms) if stock_fetch_times_ms else None,
            )
            return RealtimeThemeRefreshResponse(
                **snapshot.model_dump(),
                success=True,
                price_api_call_count=price_api_call_count,
                kiwoom_fetch_ms=kiwoom_fetch_ms,
                db_upsert_ms=db_upsert_ms,
                theme_aggregation_ms=theme_aggregation_ms,
                snapshot_response_ms=snapshot_response_ms,
                stock_fetch_min_ms=min(stock_fetch_times_ms) if stock_fetch_times_ms else None,
                stock_fetch_avg_ms=round(sum(stock_fetch_times_ms) / len(stock_fetch_times_ms), 2) if stock_fetch_times_ms else None,
                stock_fetch_max_ms=max(stock_fetch_times_ms) if stock_fetch_times_ms else None,
                duration_ms=duration_ms,
                message=f"실시간 테마 갱신 완료: 고유 종목 {len(unique_stocks)}개 중 {len(quotes)}개 성공, {len(failures)}개 실패",
            )
        except HTTPException:
            raise
        except Exception:
            self.db.rollback()
            logger.exception("Realtime theme refresh failed")
            raise
        finally:
            _refresh_lock.release()

    def get_treemap(self) -> RealtimeThemeTreemapResponse:
        return self._get_treemap_with_metrics()[0]

    def _get_treemap_with_metrics(self) -> tuple[RealtimeThemeTreemapResponse, int]:
        trade_date = now_kst()[:10]
        themes, links = self._active_themes_and_links()
        by_theme: dict[int, list[dict[str, object]]] = defaultdict(list)
        unique_ids: set[int] = set()
        for link in links:
            by_theme[int(link["theme_id"])].append(link)
            unique_ids.add(int(link["stock_id"]))

        rows = self.db.execute(
            text(
                """
                SELECT r.theme_id, r.stock_id, r.change_rate, r.collected_at
                FROM market_theme_realtime_returns r
                JOIN market_themes t ON t.id=r.theme_id AND t.is_active=1
                JOIN market_theme_stocks mts
                  ON mts.theme_id=r.theme_id AND mts.stock_id=r.stock_id AND mts.is_active=1
                JOIN stocks s ON s.id=r.stock_id AND COALESCE(s.is_active, 1)=1
                WHERE r.trade_date=:trade_date
                """
            ),
            {"trade_date": trade_date},
        ).mappings().all()
        rate_by_link = {(int(row["theme_id"]), int(row["stock_id"])): float(row["change_rate"]) for row in rows}
        rate_by_stock: dict[int, float] = {}
        for row in rows:
            rate_by_stock.setdefault(int(row["stock_id"]), float(row["change_rate"]))
        market_median = float(median(rate_by_stock.values())) if rate_by_stock else 0.0
        valid_ids = {int(row["stock_id"]) for row in rows}
        snapshot_at = max((str(row["collected_at"]) for row in rows), default=None)

        aggregation_started = time.perf_counter()
        items: list[dict[str, object]] = []
        for theme in themes:
            theme_id = int(theme["theme_id"])
            theme_links = by_theme.get(theme_id, [])
            values = [rate_by_link[(theme_id, int(link["stock_id"]))] for link in theme_links if (theme_id, int(link["stock_id"])) in rate_by_link]
            items.append({
                "theme_id": theme_id,
                "theme_name": str(theme["theme_name"]),
                "rank": 0,
                "avg_change_rate": round(sum(values) / len(values), 4) if values else None,
                "theme_strength": round(calculate_theme_strength(values, market_median), 4) if values else None,
                "linked_stock_count": len(theme_links),
                "valid_stock_count": len(values),
            })
        items.sort(key=lambda item: (item["avg_change_rate"] is None, -(float(item["avg_change_rate"]) if item["avg_change_rate"] is not None else 0), str(item["theme_name"])))
        for index, item in enumerate(items, start=1):
            item["rank"] = index
        response = RealtimeThemeTreemapResponse(
            trade_date=trade_date,
            snapshot_at=snapshot_at,
            theme_count=len(themes),
            linked_stock_count=len(links),
            unique_stock_count=len(unique_ids),
            valid_stock_count=len(valid_ids),
            failed_stock_count=max(0, len(unique_ids) - len(valid_ids)) if snapshot_at else 0,
            themes=items,
        )
        return response, int((time.perf_counter() - aggregation_started) * 1000)

    def get_theme_stocks(self, theme_id: int) -> RealtimeThemeStocksResponse:
        trade_date = now_kst()[:10]
        treemap = self.get_treemap()
        theme = next((item for item in treemap.themes if item.theme_id == theme_id), None)
        if theme is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="활성 테마를 찾을 수 없습니다.")
        rows = self.db.execute(
            text(
                """
                SELECT s.id AS stock_id, s.stock_code, s.stock_name,
                       mts.stock_memo AS memo, r.change_rate,
                       r.collected_at
                FROM market_theme_stocks mts
                JOIN stocks s ON s.id=mts.stock_id AND COALESCE(s.is_active, 1)=1
                LEFT JOIN market_theme_realtime_returns r
                  ON r.theme_id=mts.theme_id AND r.stock_id=mts.stock_id AND r.trade_date=:trade_date
                WHERE mts.theme_id=:theme_id AND mts.is_active=1
                ORDER BY (r.change_rate IS NULL), r.change_rate DESC, s.stock_name ASC
                """
            ),
            {"trade_date": trade_date, "theme_id": theme_id},
        ).mappings().all()
        stocks = [RealtimeThemeStockItem(**dict(row)) for row in rows]
        return RealtimeThemeStocksResponse(
            theme_id=theme_id,
            theme_name=theme.theme_name,
            theme_rank=theme.rank,
            theme_change_rate=theme.avg_change_rate,
            trade_date=trade_date,
            snapshot_at=max((item.collected_at for item in stocks if item.collected_at), default=None),
            linked_stock_count=len(stocks),
            valid_stock_count=sum(1 for item in stocks if item.change_rate is not None),
            stocks=stocks,
        )

    def _active_themes_and_links(self) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        themes = [dict(row) for row in self.db.execute(text(
            """
            SELECT id AS theme_id, theme_name
            FROM market_themes
            WHERE is_active=1 AND COALESCE(theme_level, 'THEME')='THEME'
            ORDER BY is_supply_theme DESC, sort_order ASC, theme_name ASC
            """
        )).mappings().all()]
        theme_ids = [int(item["theme_id"]) for item in themes]
        if not theme_ids:
            return themes, []
        params = {f"theme_{index}": theme_id for index, theme_id in enumerate(theme_ids)}
        placeholders = ", ".join(f":theme_{index}" for index in range(len(theme_ids)))
        links = [dict(row) for row in self.db.execute(text(
            f"""
            SELECT mts.theme_id, s.id AS stock_id, s.stock_code, s.stock_name
            FROM market_theme_stocks mts
            JOIN stocks s ON s.id=mts.stock_id
            WHERE mts.theme_id IN ({placeholders})
              AND mts.is_active=1 AND COALESCE(s.is_active, 1)=1
            ORDER BY mts.theme_id ASC, mts.is_primary DESC, s.stock_name ASC
            """
        ), params).mappings().all()]
        return themes, links

    @staticmethod
    def _normalize_change_rate(value: object | None) -> float | None:
        if value in (None, ""):
            return None
        try:
            number = float(str(value).replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            return None
        # ka10001 flu_rt is normally already expressed in percentage points.
        return round(number, 4)
