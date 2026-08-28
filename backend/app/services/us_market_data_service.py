from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean, median
from threading import Lock

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.providers.market_data.us_daily_price_provider import (
    UsDailyPrice,
    UsHistoricalPricePartialError,
    normalize_and_validate_us_daily_price,
)
from backend.app.providers.market_data.yfinance_us_daily_price_provider import YFinanceUsDailyPriceProvider
from backend.app.schemas.us_market_theme_schema import (
    UsMarketRefreshRequest,
    UsMarketRefreshResponse,
    UsThemeDashboardRankItem,
    UsThemeDashboardSummaryResponse,
    UsThemeReturnDetailResponse,
    UsThemeReturnItem,
    UsThemeReturnListResponse,
    UsThemeReturnRecalculateRequest,
    UsThemeReturnRecalculateResponse,
    UsThemeTreemapItem,
    UsThemeTreemapResponse,
    UsThemeTrendItem,
    UsThemeTrendPoint,
    UsThemeTrendResponse,
)
from backend.app.schemas.us_stock_schema import (
    UsPriceCollectionFailure,
    UsPriceCollectionRequest,
    UsPriceCollectionResponse,
    UsStockDailyPriceResponse,
    UsStockPriceListResponse,
)
from backend.app.services.realtime_theme_service import calculate_theme_strength, calculate_trimmed_mean


logger = logging.getLogger(__name__)
_refresh_lock = Lock()
_YFINANCE_ORIGINAL_FETCH_HISTORY = YFinanceUsDailyPriceProvider.fetch_history


class UsMarketDataService:
    def __init__(self, db: Session, provider: object | None = None) -> None:
        self.db = db
        self.provider = provider or YFinanceUsDailyPriceProvider()
        self._last_recalculation: UsThemeReturnRecalculateResponse | None = None

    def list_prices(self, stock_id: int, *, start_date: str | None, end_date: str | None) -> UsStockPriceListResponse:
        stock = self.db.execute(text("SELECT id, symbol FROM us_stocks WHERE id=:id"), {"id": stock_id}).mappings().first()
        if not stock:
            raise HTTPException(status_code=404, detail="미국 종목을 찾을 수 없습니다.")
        filters = ["us_stock_id=:stock_id"]
        params: dict[str, object] = {"stock_id": stock_id}
        if start_date:
            filters.append("trade_date>=:start_date")
            params["start_date"] = start_date
        if end_date:
            filters.append("trade_date<=:end_date")
            params["end_date"] = end_date
        rows = self.db.execute(text(f"SELECT trade_date,open_price,high_price,low_price,close_price,volume FROM us_stock_daily_prices WHERE {' AND '.join(filters)} ORDER BY trade_date"), params).mappings().all()
        return UsStockPriceListResponse(stock_id=stock_id, symbol=str(stock["symbol"]), items=[UsStockDailyPriceResponse(**row) for row in rows])

    def resolve_historical_collection_targets(self, payload: UsPriceCollectionRequest):
        params: dict[str, object] = {}
        where = ["s.is_active=1"]
        if payload.mode == "MISSING":
            where.append("NOT EXISTS (SELECT 1 FROM us_stock_daily_prices p WHERE p.us_stock_id=s.id)")
        elif payload.mode == "INCREMENTAL" and not payload.stock_ids:
            where.append("EXISTS (SELECT 1 FROM us_stock_daily_prices p WHERE p.us_stock_id=s.id)")
        if payload.stock_ids and payload.mode in {"INCREMENTAL", "SELECTED", "BACKFILL"}:
            stock_ids = payload.stock_ids or []
            placeholders = ",".join(f":stock_{index}" for index, _ in enumerate(stock_ids))
            where.append(f"s.id IN ({placeholders})")
            params.update({f"stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)})
        return self.db.execute(text(f"SELECT s.id,s.symbol,s.exchange,s.historical_price_status FROM us_stocks s WHERE {' AND '.join(where)} ORDER BY s.symbol"), params).mappings().all()

    def _upsert_price_rows(
        self,
        *,
        stock_id: int,
        prices: list[UsDailyPrice],
        timestamp: str,
    ) -> tuple[int, int, int, list[str]]:
        if not prices:
            return 0, 0, 0, []
        normalized_prices = [normalize_and_validate_us_daily_price(row)[0] for row in prices]
        placeholders = ",".join(f":date_{index}" for index, _ in enumerate(normalized_prices))
        params = {"id": stock_id, **{f"date_{index}": row.trade_date for index, row in enumerate(normalized_prices)}}
        existing_rows = self.db.execute(text(f"""
            SELECT trade_date,open_price,high_price,low_price,close_price,volume,source
            FROM us_stock_daily_prices
            WHERE us_stock_id=:id AND trade_date IN ({placeholders})
        """), params).mappings().all()
        existing = {str(row["trade_date"]): row for row in existing_rows}
        source = "YFINANCE" if isinstance(self.provider, YFinanceUsDailyPriceProvider) else "KIWOOM"
        inserted = updated = unchanged = 0
        dates: list[str] = []
        for row in normalized_prices:
            current = existing.get(row.trade_date)
            incoming_values = (
                row.open_price,
                row.high_price,
                row.low_price,
                row.close_price,
                row.volume,
                source,
            )
            if current is not None:
                current_values = (
                    float(current["open_price"]),
                    float(current["high_price"]),
                    float(current["low_price"]),
                    float(current["close_price"]),
                    int(current["volume"]),
                    str(current["source"]),
                )
                if current_values == incoming_values:
                    unchanged += 1
                    continue
            self.db.execute(text("""
                INSERT INTO us_stock_daily_prices
                  (us_stock_id,trade_date,open_price,high_price,low_price,close_price,volume,source,collected_at,created_at,updated_at)
                VALUES (:stock_id,:trade_date,:open_price,:high_price,:low_price,:close_price,:volume,:source,:timestamp,:timestamp,:timestamp)
                ON CONFLICT(us_stock_id,trade_date) DO UPDATE SET
                  open_price=excluded.open_price,high_price=excluded.high_price,low_price=excluded.low_price,
                  close_price=excluded.close_price,volume=excluded.volume,source=excluded.source,
                  collected_at=excluded.collected_at,updated_at=excluded.updated_at
            """), {"stock_id": stock_id, "trade_date": row.trade_date, "open_price": row.open_price, "high_price": row.high_price, "low_price": row.low_price, "close_price": row.close_price, "volume": row.volume, "source": source, "timestamp": timestamp})
            if current is not None:
                updated += 1
            else:
                inserted += 1
            dates.append(row.trade_date)
        return inserted, updated, unchanged, dates

    def _affected_theme_ids(self, stock_ids: list[int]) -> list[int]:
        if not stock_ids:
            return []
        placeholders = ",".join(f":stock_{index}" for index, _ in enumerate(stock_ids))
        params = {f"stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        return [int(value) for value in self.db.scalars(text(f"""
            SELECT DISTINCT mts.theme_id FROM us_theme_stocks mts
            JOIN us_themes t ON t.id=mts.theme_id AND t.active=1
            WHERE mts.active=1 AND mts.us_stock_id IN ({placeholders}) ORDER BY mts.theme_id
        """), params).all()]

    def collect_prices(self, payload: UsPriceCollectionRequest, *, acquire_lock: bool = True, recalculate: bool = True) -> UsPriceCollectionResponse:
        if acquire_lock and not _refresh_lock.acquire(blocking=False):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="미국 가격 또는 테마 갱신이 이미 진행 중입니다.")
        try:
            stocks = self.resolve_historical_collection_targets(payload)
            failures: list[UsPriceCollectionFailure] = []
            inserted_count = updated_count = unchanged_count = success_count = normalized_count = 0
            affected_dates: list[str] = []
            affected_stock_ids: list[int] = []
            today = date.today().isoformat()
            historical_mode = payload.mode != "INCREMENTAL"
            batch_results = None
            batch_failures: dict[str, str] = {}
            if (
                isinstance(self.provider, YFinanceUsDailyPriceProvider)
                and type(self.provider).fetch_history is _YFINANCE_ORIGINAL_FETCH_HISTORY
                and stocks
            ):
                batch = self.provider.fetch_many_history(
                    symbols=[str(stock["symbol"]) for stock in stocks],
                    trading_days=payload.trading_days,
                )
                batch_results = batch.results
                batch_failures = batch.failures
            for stock in stocks:
                stock_id = int(stock["id"])
                symbol = str(stock["symbol"])
                try:
                    latest = self.db.scalar(text("SELECT MAX(trade_date) FROM us_stock_daily_prices WHERE us_stock_id=:id"), {"id": stock_id})
                    overlap_start = None
                    if payload.mode == "INCREMENTAL" and latest:
                        overlap_dates = self.db.scalars(text("""
                            SELECT trade_date FROM us_stock_daily_prices
                            WHERE us_stock_id=:id
                            ORDER BY trade_date DESC
                            LIMIT 2
                        """), {"id": stock_id}).all()
                        overlap_start = min(str(value) for value in overlap_dates)
                    request_count = payload.trading_days
                    if payload.mode == "INCREMENTAL":
                        if latest:
                            calendar_gap = max((date.today() - date.fromisoformat(str(latest))).days, 0)
                            request_count = min(max(math.ceil(calendar_gap * 5 / 7) + 10, 20), payload.trading_days)
                        else:
                            # A user-selected stock without history still needs two closes
                            # so the list can show both the latest close and its return.
                            request_count = 2
                    if batch_results is not None:
                        result = batch_results.get(symbol)
                        if result is None:
                            raise ValueError(batch_failures.get(symbol, "price_history_missing"))
                    else:
                        result = self.provider.fetch_history(symbol=symbol, exchange=str(stock["exchange"]), start_date=today, trading_days=request_count)
                    prices = result.prices[-request_count:]
                    normalized_count += result.normalized_open_boundary_count
                    if payload.mode == "INCREMENTAL" and overlap_start:
                        # Revisit the latest two actual provider trading sessions. This
                        # corrects provisional candles without relying on calendar-day
                        # arithmetic across US weekends, holidays, or the KST date gap.
                        prices = [row for row in prices if row.trade_date >= overlap_start]
                    if historical_mode and not prices:
                        raise ValueError("yfinance에서 과거가격을 찾지 못했습니다.")
                    timestamp = now_kst()
                    inserted, updated, unchanged, dates = self._upsert_price_rows(stock_id=stock_id, prices=prices, timestamp=timestamp)
                    inserted_count += inserted
                    updated_count += updated
                    unchanged_count += unchanged
                    affected_dates.extend(dates)
                    if dates:
                        affected_stock_ids.append(stock_id)
                    if historical_mode:
                        historical_status = "COMPLETE" if len(result.prices) >= payload.trading_days or result.history_exhausted else "PARTIAL"
                    else:
                        historical_status = "PARTIAL" if latest is None else str(stock["historical_price_status"])
                    update_historical_status = historical_mode or latest is None
                    completed_at = timestamp if historical_mode and historical_status == "COMPLETE" else None
                    self.db.execute(text("""
                        UPDATE us_stocks SET last_synced_at=:timestamp, updated_at=:timestamp,
                          historical_price_status=CASE WHEN :update_historical_status=1 THEN :historical_status ELSE historical_price_status END,
                          historical_price_completed_at=CASE WHEN :update_historical_status=1 THEN :completed_at ELSE historical_price_completed_at END
                        WHERE id=:id
                    """), {"timestamp": timestamp, "update_historical_status": int(update_historical_status), "historical_status": historical_status, "completed_at": completed_at, "id": stock_id})
                    self.db.commit()
                    if historical_mode and historical_status == "PARTIAL":
                        failures.append(UsPriceCollectionFailure(stock_id=stock_id, symbol=symbol, reason="공급자 과거 데이터 끝에 도달하기 전에 수집이 중단됐습니다."))
                    else:
                        success_count += 1
                except UsHistoricalPricePartialError as exc:
                    self.db.rollback()
                    timestamp = now_kst()
                    inserted, updated, unchanged, dates = self._upsert_price_rows(stock_id=stock_id, prices=exc.prices, timestamp=timestamp)
                    inserted_count += inserted
                    updated_count += updated
                    unchanged_count += unchanged
                    affected_dates.extend(dates)
                    if dates:
                        affected_stock_ids.append(stock_id)
                    self.db.execute(text("UPDATE us_stocks SET last_synced_at=:timestamp,updated_at=:timestamp,historical_price_status='PARTIAL',historical_price_completed_at=NULL WHERE id=:id"), {"timestamp": timestamp, "id": stock_id})
                    self.db.commit()
                    logger.warning("US historical price collection partially failed stock=%s: %s", symbol, exc)
                    failures.append(UsPriceCollectionFailure(stock_id=stock_id, symbol=symbol, reason=str(exc)[:200]))
                except Exception as exc:
                    self.db.rollback()
                    row_count = int(self.db.scalar(text("SELECT COUNT(*) FROM us_stock_daily_prices WHERE us_stock_id=:id"), {"id": stock_id}) or 0)
                    if historical_mode:
                        self.db.execute(text("UPDATE us_stocks SET historical_price_status=:status,historical_price_completed_at=NULL,updated_at=:timestamp WHERE id=:id"), {"status": "PARTIAL" if row_count else "ERROR", "timestamp": now_kst(), "id": stock_id})
                        self.db.commit()
                    logger.warning("US daily price collection failed stock=%s: %s", symbol, exc)
                    failures.append(UsPriceCollectionFailure(stock_id=stock_id, symbol=symbol, reason=str(exc)[:200]))
            theme_ids = self._affected_theme_ids(sorted(set(affected_stock_ids)))
            recalc_result = None
            if recalculate and affected_dates and theme_ids:
                recalc_result = self.recalculate_returns(UsThemeReturnRecalculateRequest(start_date=min(affected_dates), end_date=max(affected_dates), theme_ids=theme_ids))
            self._last_recalculation = recalc_result
            latest_price_date = self.db.scalar(text("SELECT MAX(trade_date) FROM us_stock_daily_prices"))
            if not stocks:
                message = "과거가격 수집이 필요한 종목이 없습니다." if payload.mode == "MISSING" else "수집 대상 종목이 없습니다."
            else:
                label = "최신 종가 수집" if payload.mode == "INCREMENTAL" else "260일 과거가격 수집"
                message = f"{label} 완료: {success_count}종목 성공, {len(failures)}종목 실패, {inserted_count}건 신규, {updated_count}건 갱신, {unchanged_count}건 동일"
            response = UsPriceCollectionResponse(
                mode=payload.mode,
                requested_stock_count=len(stocks),
                success_stock_count=success_count,
                failed_stock_count=len(failures),
                inserted_count=inserted_count,
                updated_count=updated_count,
                unchanged_count=unchanged_count,
                normalized_open_boundary_count=normalized_count,
                affected_date_from=min(affected_dates) if affected_dates else None,
                affected_date_to=max(affected_dates) if affected_dates else None,
                recalculated_theme_count=recalc_result.processed_theme_count if recalc_result else 0,
                latest_price_date=str(latest_price_date) if latest_price_date else None,
                failures=failures,
                message=message,
            )
            return response
        finally:
            if acquire_lock:
                _refresh_lock.release()

    def recalculate_returns(self, payload: UsThemeReturnRecalculateRequest) -> UsThemeReturnRecalculateResponse:
        theme_params: dict[str, object] = {}
        theme_filter = "WHERE t.active=1"
        if payload.theme_ids:
            placeholders = ",".join(f":theme_{index}" for index, _ in enumerate(payload.theme_ids))
            theme_filter += f" AND t.id IN ({placeholders})"
            theme_params.update({f"theme_{index}": theme_id for index, theme_id in enumerate(payload.theme_ids)})
        themes = self.db.execute(text(f"SELECT t.id,t.name FROM us_themes t {theme_filter} ORDER BY t.id"), theme_params).mappings().all()
        links = self.db.execute(text(f"""
            SELECT mts.theme_id,mts.us_stock_id,mts.role
            FROM us_theme_stocks mts
            JOIN us_themes t ON t.id=mts.theme_id
            JOIN us_stocks s ON s.id=mts.us_stock_id
            {theme_filter} AND mts.active=1 AND s.is_active=1 AND mts.role<>'ETF' AND s.stock_type<>'ETF'
        """), theme_params).mappings().all()
        eligible_ids = sorted({int(row["us_stock_id"]) for row in links})
        returns_by_stock: dict[int, dict[str, float]] = defaultdict(dict)
        if eligible_ids:
            placeholders = ",".join(f":stock_{index}" for index, _ in enumerate(eligible_ids))
            stock_params = {f"stock_{index}": stock_id for index, stock_id in enumerate(eligible_ids)}
            price_rows = self.db.execute(text(f"SELECT us_stock_id,trade_date,close_price FROM us_stock_daily_prices WHERE us_stock_id IN ({placeholders}) ORDER BY us_stock_id,trade_date"), stock_params).mappings().all()
            previous: dict[int, float] = {}
            for row in price_rows:
                stock_id = int(row["us_stock_id"])
                close = float(row["close_price"])
                if stock_id in previous and previous[stock_id] > 0:
                    returns_by_stock[stock_id][str(row["trade_date"])] = (close / previous[stock_id] - 1) * 100
                previous[stock_id] = close
        market_by_date: dict[str, list[float]] = defaultdict(list)
        for values in returns_by_stock.values():
            for trade_date, value in values.items():
                market_by_date[trade_date].append(value)
        market_medians = {trade_date: float(median(values)) for trade_date, values in market_by_date.items()}
        links_by_theme: dict[int, list[int]] = defaultdict(list)
        for row in links:
            links_by_theme[int(row["theme_id"])].append(int(row["us_stock_id"]))
        now = now_kst()
        upserted = skipped = 0
        processed_dates: set[str] = set()
        try:
            for theme in themes:
                theme_id = int(theme["id"])
                candidate_dates = sorted({day for stock_id in links_by_theme.get(theme_id, []) for day in returns_by_stock.get(stock_id, {})})
                for trade_date in candidate_dates:
                    if payload.start_date and trade_date < payload.start_date:
                        continue
                    if payload.end_date and trade_date > payload.end_date:
                        continue
                    values = [returns_by_stock[stock_id][trade_date] for stock_id in links_by_theme.get(theme_id, []) if trade_date in returns_by_stock.get(stock_id, {})]
                    if len(values) < 2:
                        skipped += 1
                        self.db.execute(text("DELETE FROM us_theme_daily_returns WHERE theme_id=:theme_id AND trade_date=:trade_date"), {"theme_id": theme_id, "trade_date": trade_date})
                        continue
                    trimmed = calculate_trimmed_mean(values)
                    strength = calculate_theme_strength(values, market_medians.get(trade_date, 0.0))
                    up_count = sum(1 for value in values if value > 0)
                    down_count = sum(1 for value in values if value < 0)
                    flat_count = len(values) - up_count - down_count
                    self.db.execute(text("""
                        INSERT INTO us_theme_daily_returns
                          (theme_id,trade_date,simple_return,theme_strength,trimmed_mean_return,median_return,breadth_ratio,
                           valid_stock_count,up_count,down_count,flat_count,created_at,updated_at)
                        VALUES (:theme_id,:trade_date,:simple_return,:theme_strength,:trimmed,:median,:breadth,
                                :valid_count,:up_count,:down_count,:flat_count,:now,:now)
                        ON CONFLICT(theme_id,trade_date) DO UPDATE SET
                          simple_return=excluded.simple_return,theme_strength=excluded.theme_strength,
                          trimmed_mean_return=excluded.trimmed_mean_return,median_return=excluded.median_return,
                          breadth_ratio=excluded.breadth_ratio,valid_stock_count=excluded.valid_stock_count,
                          up_count=excluded.up_count,down_count=excluded.down_count,flat_count=excluded.flat_count,
                          updated_at=excluded.updated_at
                    """), {"theme_id": theme_id, "trade_date": trade_date, "simple_return": round(mean(values), 6), "theme_strength": round(float(strength), 6), "trimmed": round(float(trimmed), 6), "median": round(float(median(values)), 6), "breadth": round(up_count / len(values), 6), "valid_count": len(values), "up_count": up_count, "down_count": down_count, "flat_count": flat_count, "now": now})
                    upserted += 1
                    processed_dates.add(trade_date)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return UsThemeReturnRecalculateResponse(processed_theme_count=len(themes), processed_date_count=len(processed_dates), upserted_count=upserted, skipped_count=skipped, date_from=min(processed_dates) if processed_dates else None, date_to=max(processed_dates) if processed_dates else None, message=f"미국 테마등락률 계산 완료: {upserted}건 갱신, {skipped}건 제외")

    @staticmethod
    def _return_item(row) -> UsThemeReturnItem:
        return UsThemeReturnItem(theme_id=int(row["theme_id"]), theme_group_name=str(row["theme_group_name"]), theme_name=str(row["theme_name"]), trade_date=row["trade_date"], simple_return=float(row["simple_return"]) if row["simple_return"] is not None else None, theme_strength=float(row["theme_strength"]) if row["theme_strength"] is not None else None, trimmed_mean_return=float(row["trimmed_mean_return"]) if row["trimmed_mean_return"] is not None else None, median_return=float(row["median_return"]) if row["median_return"] is not None else None, breadth_ratio=float(row["breadth_ratio"]) if row["breadth_ratio"] is not None else None, valid_stock_count=int(row["valid_stock_count"] or 0), up_count=int(row["up_count"] or 0), down_count=int(row["down_count"] or 0), flat_count=int(row["flat_count"] or 0))

    def latest_returns(self) -> UsThemeReturnListResponse:
        latest_date = self.db.scalar(text("SELECT MAX(trade_date) FROM us_theme_daily_returns"))
        rows = self.db.execute(text("""
            SELECT t.id theme_id,g.name theme_group_name,t.name theme_name,r.trade_date,r.simple_return,r.theme_strength,
                   r.trimmed_mean_return,r.median_return,r.breadth_ratio,r.valid_stock_count,r.up_count,r.down_count,r.flat_count
            FROM us_themes t JOIN us_theme_groups g ON g.id=t.theme_group_id
            LEFT JOIN us_theme_daily_returns r ON r.theme_id=t.id AND r.trade_date=:latest_date
            WHERE t.active=1 ORDER BY g.sort_order,t.sort_order,t.name
        """), {"latest_date": latest_date}).mappings().all()
        return UsThemeReturnListResponse(latest_date=str(latest_date) if latest_date else None, items=[self._return_item(row) for row in rows])

    def dashboard_summary(self) -> UsThemeDashboardSummaryResponse:
        """Build both dashboard rankings from the existing durable US aggregates."""
        trend = self.trend(period=30, active=1)
        latest_date = max((point.trade_date for item in trend.items for point in item.points), default=None)
        latest_refreshed_at = self.db.scalar(text("SELECT MAX(updated_at) FROM us_theme_daily_returns"))
        active_theme_count = int(self.db.scalar(text("SELECT COUNT(*) FROM us_themes WHERE active=1")) or 0)
        rows: list[UsThemeDashboardRankItem] = []
        for item in trend.items:
            if not item.points:
                continue
            latest = max(item.points, key=lambda point: point.trade_date)
            recent = sorted(item.points, key=lambda point: point.trade_date)[-10:]
            positive_days = sum(1 for point in recent if point.simple_return > 0)
            observed_days = len(recent)
            rows.append(UsThemeDashboardRankItem(
                theme_id=item.theme_id,
                theme_group_name=item.theme_group_name,
                theme_name=item.theme_name,
                simple_return=latest.simple_return,
                theme_strength=latest.theme_strength,
                rolling_30d_return=latest.rolling_30d_simple_return,
                persistence_rate=round((positive_days / observed_days) * 100, 2) if observed_days else 0,
                positive_days=positive_days,
                observed_days=observed_days,
            ))
        return UsThemeDashboardSummaryResponse(
            latest_date=latest_date,
            latest_refreshed_at=str(latest_refreshed_at) if latest_refreshed_at else None,
            active_theme_count=active_theme_count,
            top_strength=sorted(rows, key=lambda row: (-row.theme_strength, -row.simple_return, row.theme_name))[:6],
            top_persistence=sorted(rows, key=lambda row: (-row.persistence_rate, -row.positive_days, -row.theme_strength, row.theme_name))[:6],
        )

    def treemap(self) -> UsThemeTreemapResponse:
        """Return the latest finalized US theme values with active link counts.

        This is a read-only projection over the existing durable aggregate and
        relationship tables. It deliberately does not recalculate or persist data.
        """
        latest_date = self.db.scalar(text("SELECT MAX(trade_date) FROM us_theme_daily_returns"))
        rows = self.db.execute(text("""
            SELECT t.id theme_id,g.name theme_group_name,t.name theme_name,
                   r.trade_date,r.simple_return,r.theme_strength,r.trimmed_mean_return,
                   r.median_return,r.breadth_ratio,r.valid_stock_count,r.up_count,
                   r.down_count,r.flat_count,COUNT(s.id) linked_stock_count
            FROM us_themes t
            JOIN us_theme_groups g ON g.id=t.theme_group_id
            LEFT JOIN us_theme_daily_returns r
              ON r.theme_id=t.id AND r.trade_date=:latest_date
            LEFT JOIN us_theme_stocks linked
              ON linked.theme_id=t.id AND linked.active=1
            LEFT JOIN us_stocks s
              ON s.id=linked.us_stock_id AND s.is_active=1
            WHERE t.active=1
            GROUP BY t.id,g.name,t.name,r.trade_date,r.simple_return,r.theme_strength,
                     r.trimmed_mean_return,r.median_return,r.breadth_ratio,
                     r.valid_stock_count,r.up_count,r.down_count,r.flat_count
            ORDER BY g.sort_order,t.sort_order,t.name
        """), {"latest_date": latest_date}).mappings().all()
        items = [
            UsThemeTreemapItem(
                **self._return_item(row).model_dump(),
                linked_stock_count=int(row["linked_stock_count"] or 0),
            )
            for row in rows
        ]
        return UsThemeTreemapResponse(
            latest_date=str(latest_date) if latest_date else None,
            active_theme_count=len(items),
            linked_stock_count=sum(item.linked_stock_count for item in items),
            aggregated_stock_count=sum(item.valid_stock_count for item in items),
            items=items,
        )

    def trend(self, *, period: int, end_date: str | None = None, active: int | None = 1) -> UsThemeTrendResponse:
        latest_filter = "WHERE trade_date<=:end_date" if end_date else ""
        latest_params: dict[str, object] = {"end_date": end_date} if end_date else {}
        latest_stored_date = self.db.scalar(text(
            f"SELECT MAX(trade_date) FROM us_theme_daily_returns {latest_filter}"
        ), latest_params)
        if not latest_stored_date:
            return UsThemeTrendResponse(period=period, dates=[], items=[])
        # Keep every calendar date in the requested range. A date without a
        # collected observation remains absent from `points`, allowing the UI
        # to render the verified KRX missing-data marker (`-`) instead of
        # compressing the axis or treating the missing value as zero.
        display_end_date = date.fromisoformat(end_date or str(latest_stored_date))
        dates = [
            (display_end_date - timedelta(days=offset)).isoformat()
            for offset in range(period - 1, -1, -1)
        ]
        active_filter = "AND t.active=:active" if active is not None else ""
        # Keep the verified KRX rule: for every displayed observation date, sum
        # daily theme values in the inclusive 30-calendar-day window ending on it.
        calc_start_date = (date.fromisoformat(dates[0]) - timedelta(days=29)).isoformat()
        params: dict[str, object] = {"start_date": calc_start_date, "end_date": dates[-1]}
        if active is not None:
            params["active"] = active
        rows = self.db.execute(text(f"""
            SELECT r.theme_id,t.theme_group_id,g.name theme_group_name,t.name theme_name,t.active,
                   r.trade_date,r.simple_return,r.theme_strength,r.breadth_ratio,r.valid_stock_count,r.up_count
            FROM us_theme_daily_returns r JOIN us_themes t ON t.id=r.theme_id JOIN us_theme_groups g ON g.id=t.theme_group_id
            WHERE r.trade_date>=:start_date AND r.trade_date<=:end_date {active_filter}
            ORDER BY g.sort_order,t.sort_order,t.name,r.trade_date
        """), params).mappings().all()
        observations: dict[int, list[dict[str, object]]] = defaultdict(list)
        metadata: dict[int, dict[str, object]] = {}
        for row in rows:
            theme_id = int(row["theme_id"])
            metadata.setdefault(theme_id, {"theme_group_id": int(row["theme_group_id"]), "theme_group_name": row["theme_group_name"], "theme_name": row["theme_name"], "active": int(row["active"])})
            observations[theme_id].append(dict(row))
        display_dates = set(dates)
        items: list[UsThemeTrendItem] = []
        for theme_id, theme_rows in observations.items():
            points: list[UsThemeTrendPoint] = []
            for row in theme_rows:
                trade_date = str(row["trade_date"])
                if trade_date not in display_dates:
                    continue
                window_start = date.fromisoformat(trade_date) - timedelta(days=29)
                window_rows = [candidate for candidate in theme_rows if window_start <= date.fromisoformat(str(candidate["trade_date"])) <= date.fromisoformat(trade_date)]
                points.append(UsThemeTrendPoint(
                    trade_date=trade_date,
                    simple_return=float(row["simple_return"]),
                    theme_strength=float(row["theme_strength"]),
                    rolling_30d_simple_return=round(sum(float(candidate["simple_return"]) for candidate in window_rows), 4),
                    rolling_30d_theme_strength=round(sum(float(candidate["theme_strength"]) for candidate in window_rows), 4),
                    rolling_30d_valid_count=len(window_rows),
                    breadth_ratio=float(row["breadth_ratio"]),
                    valid_stock_count=int(row["valid_stock_count"] or 0),
                    up_count=int(row["up_count"] or 0),
                ))
            if points:
                items.append(UsThemeTrendItem(theme_id=theme_id, points=points, **metadata[theme_id]))
        return UsThemeTrendResponse(period=period, dates=dates, items=items)

    def detail(self, *, theme_id: int, trade_date: str | None = None) -> UsThemeReturnDetailResponse:
        theme = self.db.execute(text("""
            SELECT t.id,t.name,t.description,t.active,g.name theme_group_name
            FROM us_themes t JOIN us_theme_groups g ON g.id=t.theme_group_id
            WHERE t.id=:id
        """), {"id": theme_id}).mappings().first()
        if not theme:
            raise HTTPException(status_code=404, detail="미국 테마를 찾을 수 없습니다.")
        resolved_trade_date = trade_date or self.db.scalar(text(
            "SELECT MAX(trade_date) FROM us_theme_daily_returns WHERE theme_id=:theme_id"
        ), {"theme_id": theme_id})
        aggregate_row = self.db.execute(text("""
            SELECT t.id theme_id,g.name theme_group_name,t.name theme_name,r.trade_date,r.simple_return,r.theme_strength,
                   r.trimmed_mean_return,r.median_return,r.breadth_ratio,r.valid_stock_count,r.up_count,r.down_count,r.flat_count
            FROM us_themes t JOIN us_theme_groups g ON g.id=t.theme_group_id
            JOIN us_theme_daily_returns r ON r.theme_id=t.id WHERE t.id=:theme_id AND r.trade_date=:trade_date
        """), {"theme_id": theme_id, "trade_date": resolved_trade_date or ""}).mappings().first()
        rows = self.db.execute(text("""
            WITH previous_prices AS (
                SELECT p.us_stock_id,p.close_price,
                       ROW_NUMBER() OVER (PARTITION BY p.us_stock_id ORDER BY p.trade_date DESC) row_number
                FROM us_stock_daily_prices p
                JOIN us_theme_stocks linked ON linked.us_stock_id=p.us_stock_id
                WHERE linked.theme_id=:theme_id AND linked.active=1 AND p.trade_date<:trade_date
            )
            SELECT mts.us_stock_id,s.symbol,s.name,s.name_ko,s.exchange,s.stock_type,s.naver_code,
                   mts.role,mts.is_representative,mts.sort_order,mts.active,
                   p.close_price,previous.close_price previous_close
            FROM us_theme_stocks mts JOIN us_stocks s ON s.id=mts.us_stock_id
            LEFT JOIN us_stock_daily_prices p ON p.us_stock_id=mts.us_stock_id AND p.trade_date=:trade_date
            LEFT JOIN previous_prices previous ON previous.us_stock_id=mts.us_stock_id AND previous.row_number=1
            WHERE mts.theme_id=:theme_id AND mts.active=1 AND s.is_active=1
            ORDER BY mts.is_representative DESC,
                     CASE mts.role WHEN 'LEADER' THEN 1 WHEN 'CORE' THEN 2 WHEN 'RELATED' THEN 3 WHEN 'ETF' THEN 4 ELSE 5 END,
                     mts.sort_order,s.symbol
        """), {"theme_id": theme_id, "trade_date": resolved_trade_date or ""}).mappings().all()
        stocks = []
        for row in rows:
            close = float(row["close_price"]) if row["close_price"] is not None else None
            previous = float(row["previous_close"]) if row["previous_close"] is not None else None
            rate = (close / previous - 1) * 100 if close is not None and previous else None
            rounded_rate = round(rate, 6) if rate is not None else None
            stocks.append({
                "us_stock_id": int(row["us_stock_id"]), "symbol": row["symbol"], "name": row["name"],
                "name_ko": row["name_ko"], "exchange": row["exchange"], "stock_type": row["stock_type"],
                "naver_code": row["naver_code"], "role": row["role"],
                "is_representative": int(row["is_representative"]), "sort_order": int(row["sort_order"]),
                "active": int(row["active"]), "return_rate": rounded_rate, "daily_return": rounded_rate,
                "close_price": close, "previous_close": previous,
            })
        aggregate = self._return_item(aggregate_row) if aggregate_row else None
        eligible_stock_count = sum(1 for row in rows if row["role"] != "ETF" and row["stock_type"] != "ETF")
        return UsThemeReturnDetailResponse(
            theme_id=theme_id, theme_name=str(theme["name"]), theme_group_name=str(theme["theme_group_name"]),
            description=theme["description"], active=int(theme["active"]),
            trade_date=str(resolved_trade_date) if resolved_trade_date else None,
            simple_return=aggregate.simple_return if aggregate else None,
            theme_strength=aggregate.theme_strength if aggregate else None,
            breadth_ratio=aggregate.breadth_ratio if aggregate else None,
            valid_stock_count=aggregate.valid_stock_count if aggregate else 0,
            eligible_stock_count=eligible_stock_count, linked_stock_count=len(stocks),
            up_count=aggregate.up_count if aggregate else 0, down_count=aggregate.down_count if aggregate else 0,
            flat_count=aggregate.flat_count if aggregate else 0, aggregate=aggregate, stocks=stocks,
        )

    def refresh(self, payload: UsMarketRefreshRequest) -> UsMarketRefreshResponse:
        if not _refresh_lock.acquire(blocking=False):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="미국 가격 또는 테마 갱신이 이미 진행 중입니다.")
        try:
            if payload.mode != "INCREMENTAL" or payload.stock_ids:
                price = self.collect_prices(UsPriceCollectionRequest(**payload.model_dump()), acquire_lock=False, recalculate=True)
                returns = self._last_recalculation or UsThemeReturnRecalculateResponse(processed_theme_count=0, processed_date_count=0, upserted_count=0, skipped_count=0, date_from=None, date_to=None, message="재계산할 연결 테마가 없습니다.")
                return UsMarketRefreshResponse(price=price.model_dump(), returns=returns, message=f"{price.message} · {returns.message}")

            linked_stocks = self.db.execute(text("""
                SELECT DISTINCT s.id,s.historical_price_status
                FROM us_stocks s
                JOIN us_theme_stocks mts ON mts.us_stock_id=s.id AND mts.active=1
                JOIN us_themes t ON t.id=mts.theme_id AND t.active=1
                WHERE s.is_active=1
                ORDER BY s.id
            """)).mappings().all()
            incomplete_ids = [int(row["id"]) for row in linked_stocks if str(row["historical_price_status"]) != "COMPLETE"]
            complete_ids = [int(row["id"]) for row in linked_stocks if str(row["historical_price_status"]) == "COMPLETE"]
            price_results: list[UsPriceCollectionResponse] = []
            if incomplete_ids:
                price_results.append(self.collect_prices(
                    UsPriceCollectionRequest(mode="SELECTED", stock_ids=incomplete_ids, trading_days=payload.trading_days),
                    acquire_lock=False,
                    recalculate=False,
                ))
            if complete_ids:
                price_results.append(self.collect_prices(
                    UsPriceCollectionRequest(mode="INCREMENTAL", stock_ids=complete_ids, trading_days=payload.trading_days),
                    acquire_lock=False,
                    recalculate=False,
                ))

            linked_range = self.db.execute(text("""
                SELECT MIN(p.trade_date) date_from,MAX(p.trade_date) date_to
                FROM us_stock_daily_prices p
                JOIN us_theme_stocks mts ON mts.us_stock_id=p.us_stock_id AND mts.active=1
                JOIN us_themes t ON t.id=mts.theme_id AND t.active=1
                JOIN us_stocks s ON s.id=p.us_stock_id AND s.is_active=1
            """)).mappings().one()
            returns = self.recalculate_returns(UsThemeReturnRecalculateRequest(
                start_date=str(linked_range["date_from"]) if linked_range["date_from"] else None,
                end_date=str(linked_range["date_to"]) if linked_range["date_to"] else None,
            ))
            failures = [failure for result in price_results for failure in result.failures]
            affected_from = [result.affected_date_from for result in price_results if result.affected_date_from]
            affected_to = [result.affected_date_to for result in price_results if result.affected_date_to]
            latest_price_date = self.db.scalar(text("SELECT MAX(trade_date) FROM us_stock_daily_prices"))
            price = UsPriceCollectionResponse(
                mode="INCREMENTAL",
                requested_stock_count=sum(result.requested_stock_count for result in price_results),
                success_stock_count=sum(result.success_stock_count for result in price_results),
                failed_stock_count=len(failures),
                inserted_count=sum(result.inserted_count for result in price_results),
                updated_count=sum(result.updated_count for result in price_results),
                affected_date_from=min(affected_from) if affected_from else None,
                affected_date_to=max(affected_to) if affected_to else None,
                recalculated_theme_count=returns.processed_theme_count,
                latest_price_date=str(latest_price_date) if latest_price_date else None,
                failures=failures,
                message=f"연결 종목 가격 갱신 완료: 과거가격 {len(incomplete_ids)}종목, 최신 종가 {len(complete_ids)}종목",
            )
            message = (
                f"미국 종가·테마 전체 갱신 완료: 연결 종목 {price.requested_stock_count}개 중 "
                f"{price.success_stock_count}개 성공, {price.failed_stock_count}개 실패 · "
                f"활성 테마 {returns.processed_theme_count}개 재계산"
            )
            return UsMarketRefreshResponse(price=price.model_dump(), returns=returns, message=message)
        finally:
            _refresh_lock.release()
