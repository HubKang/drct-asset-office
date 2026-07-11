from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.collectors.prices.mock_price_collector import MockPriceCollector
from backend.app.collectors.prices.pykrx_price_collector import PykrxPriceCollector
from backend.app.providers.market_data.kiwoom_rest_provider import KiwoomRestMarketDataProvider
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository
from backend.app.schemas.stock_price_schema import StockDailyPriceListItem
from backend.app.services.technical_indicator_service import TechnicalIndicatorService
from backend.app.utils.stock_code_utils import normalize_kr_stock_code


logger = logging.getLogger(__name__)


class StockPriceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.watchlist_repo = WatchlistRepository(db)
        self.price_repo = StockPriceRepository(db)
        self.run_repo = CollectionRunRepository(db)
        self.mock_collector = MockPriceCollector()
        self.pykrx_collector = PykrxPriceCollector()
        self.kiwoom_rest_provider = KiwoomRestMarketDataProvider()
        self.technical_indicator_service = TechnicalIndicatorService(db)

    @staticmethod
    def _validate_selected_stock_ids(stock_ids: list[int]) -> list[int]:
        selected = [sid for sid in stock_ids if isinstance(sid, int)]
        if not selected:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="선택된 종목이 없습니다.")
        return selected

    @staticmethod
    def _calc_sma(values: list[float], idx: int, window: int) -> float | None:
        if idx + 1 < window:
            return None
        sub = values[idx - window + 1 : idx + 1]
        return round(sum(sub) / window, 4)

    @staticmethod
    def _parse_iso_date(raw: str) -> date:
        return datetime.strptime(raw, "%Y-%m-%d").date()

    @staticmethod
    def _truncate_message(value: str, max_len: int = 900) -> str:
        text = (value or "").strip()
        if len(text) <= max_len:
            return text
        return text[:max_len] + "...(truncated)"

    def recalculate_moving_averages(self, stock_id: int) -> None:
        rows = self.price_repo.list_by_stock_asc(stock_id)
        closes = [float(r.close_price) if r.close_price is not None else 0.0 for r in rows]
        for idx, row in enumerate(rows):
            if row.close_price is None:
                self.price_repo.update_moving_averages(row.id, None, None, None, None, None, None)
                continue
            self.price_repo.update_moving_averages(
                row.id,
                self._calc_sma(closes, idx, 5),
                self._calc_sma(closes, idx, 10),
                self._calc_sma(closes, idx, 20),
                self._calc_sma(closes, idx, 60),
                self._calc_sma(closes, idx, 120),
                self._calc_sma(closes, idx, 240),
            )
        self.price_repo.commit()

    def _collect_rows_by_source(
        self,
        stock,
        start_date: date,
        end_date: date,
        source: str,
        *,
        mode: str | None = None,
        stop_at_start_date: bool = True,
    ) -> tuple[str, list[dict], dict[str, object]]:
        if source == "mock":
            rows = self.mock_collector.collect_daily(stock.id, stock.stock_code, start_date, end_date)
            payload = [
                {
                    "trade_date": r.trade_date,
                    "open_price": r.open_price,
                    "high_price": r.high_price,
                    "low_price": r.low_price,
                    "close_price": r.close_price,
                    "change_price": r.change_price,
                    "change_rate": r.change_rate,
                    "volume": r.volume,
                    "trading_value": r.trading_value,
                }
                for r in rows
            ]
            return normalize_kr_stock_code(stock.stock_code), payload, {"pages_fetched": 0, "stop_reason": "mock"}
        if source == "pykrx":
            normalized, rows = self.pykrx_collector.collect_daily(
                stock.stock_code,
                start_date=start_date,
                end_date=end_date,
                adjusted=True,
            )
            payload = [
                {
                    "trade_date": r.trade_date,
                    "open_price": r.open_price,
                    "high_price": r.high_price,
                    "low_price": r.low_price,
                    "close_price": r.close_price,
                    "change_price": r.change_price,
                    "change_rate": r.change_rate,
                    "volume": r.volume,
                    "trading_value": r.trading_value,
                }
                for r in rows
            ]
            return normalized, payload, {"pages_fetched": 0, "stop_reason": "pykrx_single_fetch"}
        if source == "kiwoom_rest":
            response = self.kiwoom_rest_provider.get_daily_prices(
                stock.stock_code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                mode=mode,
                stop_at_start_date=stop_at_start_date,
            )
            payload = [
                {
                    "trade_date": r["trade_date"],
                    "open_price": r.get("open_price"),
                    "high_price": r.get("high_price"),
                    "low_price": r.get("low_price"),
                    "close_price": r.get("close_price"),
                    "change_price": r.get("change_price"),
                    "change_rate": r.get("change_rate"),
                    "volume": r.get("volume"),
                    "trading_value": r.get("trading_value"),
                }
                for r in response.get("items", [])
                if isinstance(r, dict) and r.get("trade_date")
            ]
            normalized = response.get("normalized_stock_code") or normalize_kr_stock_code(stock.stock_code)
            return normalized, payload, {
                "pages_fetched": int(response.get("pages_fetched") or response.get("api_call_count") or 0),
                "stop_reason": response.get("stop_reason"),
                "raw_count": response.get("raw_count"),
                "mapped_count": response.get("mapped_count"),
            }
        if source == "broker_kis":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="broker_kis는 현재 보류 상태입니다. source=pykrx를 사용해 주세요.",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"지원하지 않는 source입니다: {source}")

    def _parse_optional_collect_date(self, raw: str | None, field_name: str) -> date | None:
        if not raw:
            return None
        try:
            return self._parse_iso_date(str(raw)[:10])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invalid {field_name}: expected YYYY-MM-DD",
            ) from exc

    def _resolve_collect_window(
        self,
        stock_id: int,
        source: str,
        period_years: int,
        overlap_days: int,
        force_full_refresh: bool,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[str, date, date, str, str | None]:
        today = date.today()
        if source not in {"kiwoom_rest", "mock", "pykrx"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported source: {source}")

        manual_start = self._parse_optional_collect_date(start_date, "start_date")
        manual_end = self._parse_optional_collect_date(end_date, "end_date")
        if manual_start or manual_end:
            if not manual_start or not manual_end:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date must be provided together",
                )
            if manual_start > manual_end:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date must be earlier than or equal to end_date",
                )
            return "manual_range", manual_start, manual_end, "manual date range collection", None

        safe_period_years = max(1, period_years)
        safe_overlap_days = max(0, overlap_days)
        full_start = today - timedelta(days=safe_period_years * 365)

        if force_full_refresh:
            return "full_refresh", full_start, today, f"full refresh for recent {safe_period_years} years", None

        latest_trade_date = self.price_repo.get_latest_trade_date(stock_id=stock_id, source=source)
        if not latest_trade_date:
            return "initial_backfill", full_start, today, f"initial backfill for recent {safe_period_years} years", None

        latest = self._parse_iso_date(str(latest_trade_date))
        if source == "pykrx":
            if latest < today:
                return "incremental", latest, today, f"incremental collection from {latest_trade_date}", str(latest_trade_date)
            refresh_start = today - timedelta(days=7)
            return "refresh_latest", refresh_start, today, "refresh latest 7 calendar days", str(latest_trade_date)

        incremental_start = latest - timedelta(days=safe_overlap_days)
        return (
            "incremental_overlap",
            incremental_start,
            today,
            f"incremental collection with {safe_overlap_days} calendar-day overlap from {latest_trade_date}",
            str(latest_trade_date),
        )

    def _collect_and_upsert_with_stats(
        self,
        stock,
        source: str,
        start_date: date,
        end_date: date,
        *,
        mode: str | None = None,
        stop_at_start_date: bool = True,
    ) -> dict[str, object]:
        normalized, payload, diagnostics = self._collect_rows_by_source(
            stock,
            start_date,
            end_date,
            source,
            mode=mode,
            stop_at_start_date=stop_at_start_date,
        )
        collected_count = len(payload)
        saved = self.price_repo.upsert_daily_rows(stock.id, source, payload)
        if payload:
            self.price_repo.recalculate_change_rate_for_stock(stock.id, source=source, digits=2)
        if payload:
            self.recalculate_moving_averages(stock.id)
        logger.info(
            "일봉 수집 저장 완료: stock_id=%s stock_code=%s normalized=%s source=%s collected=%s saved=%s start=%s end=%s",
            stock.id,
            stock.stock_code,
            normalized,
            source,
            collected_count,
            saved,
            start_date.isoformat(),
            end_date.isoformat(),
        )
        return {
            "normalized": normalized,
            "collected_count": collected_count,
            "saved_count": saved,
            **diagnostics,
        }

    def _collect_and_upsert(self, stock, source: str, start_date: date, end_date: date) -> tuple[str, int, int]:
        result = self._collect_and_upsert_with_stats(stock, source, start_date, end_date)
        return str(result["normalized"]), int(result["collected_count"] or 0), int(result["saved_count"] or 0)

    def collect_selected_backfill(self, stock_ids: list[int], period_years: int, source: str, overlap_days: int = 7, force_full_refresh: bool = False, start_date: str | None = None, end_date: str | None = None) -> dict:
        selected_ids = self._validate_selected_stock_ids(stock_ids)
        active_ids = set(self.watchlist_repo.list_active_stock_ids())
        selected_stocks = [self.stock_repo.get_by_id(sid) for sid in selected_ids]
        run_codes = [s.stock_code for s in selected_stocks if s]
        run = self.run_repo.create_running("watchlist_selected_price_backfill_collector", f"selected:{','.join(run_codes)}")

        success_count = 0
        failed_count = 0
        skipped_count = 0
        saved_total = 0
        technical_saved_total = 0
        results: list[dict] = []

        for sid in selected_ids:
            stock = self.stock_repo.get_by_id(sid)
            if not stock:
                failed_count += 1
                results.append(
                    {
                        "stock_id": sid,
                        "stock_code": "",
                        "normalized_stock_code": None,
                        "stock_name": "",
                        "status": "failed",
                        "mode": None,
                        "from_date": None,
                        "to_date": None,
                        "collected_count": 0,
                        "saved_count": 0,
                        "source": source,
                        "message": "stock not found",
                    }
                )
                continue

            if sid not in active_ids:
                skipped_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "normalized_stock_code": normalize_kr_stock_code(stock.stock_code),
                        "stock_name": stock.stock_name,
                        "status": "skipped",
                        "mode": None,
                        "from_date": None,
                        "to_date": None,
                        "collected_count": 0,
                        "saved_count": 0,
                        "source": source,
                        "message": "inactive watchlist stock",
                    }
                )
                continue

            mode = None
            from_date = None
            to_date = None
            mode_message = None
            try:
                mode, from_date, to_date, mode_message, latest_trade_date = self._resolve_collect_window(
                    stock.id,
                    source,
                    period_years,
                    overlap_days,
                    force_full_refresh,
                    start_date=start_date,
                    end_date=end_date,
                )
                logger.info(
                    "[PRICE DEBUG] stock_id=%s stock_name=%s stock_code=%s normalized_code=%s mode=%s from_date=%s to_date=%s latest_trade_date=%s overlap_days=%s force_full_refresh=%s",
                    stock.id,
                    stock.stock_name,
                    stock.stock_code,
                    normalize_kr_stock_code(stock.stock_code),
                    mode,
                    from_date.isoformat() if from_date else None,
                    to_date.isoformat() if to_date else None,
                    latest_trade_date,
                    overlap_days,
                    force_full_refresh,
                )
                normalized_code, collected_count, saved_count = self._collect_and_upsert(
                    stock=stock,
                    source=source,
                    start_date=from_date,
                    end_date=to_date,
                )
                logger.info(
                    "[PRICE DEBUG] stock_id=%s normalized_code=%s collected_count=%s saved_count=%s",
                    stock.id,
                    normalized_code,
                    collected_count,
                    saved_count,
                )
                success_count += 1
                saved_total += saved_count
                technical_saved_count = 0
                technical_latest_trade_date = None
                technical_error = None
                try:
                    technical_source_label = "kiwoom_rest" if source == "kiwoom_rest" else "calculated_from_pykrx_prices"
                    technical_result = self.technical_indicator_service.calculate_and_save_for_stock(
                        stock.id,
                        source_label=technical_source_label,
                    )
                    technical_saved_count = int(technical_result["saved_count"])
                    technical_latest_trade_date = technical_result.get("latest_trade_date")
                    technical_saved_total += technical_saved_count
                except Exception as technical_exc:
                    technical_error = str(technical_exc)
                    logger.warning(
                        "technical indicators calculate/save failed: stock_id=%s source=%s error=%s",
                        stock.id,
                        source,
                        technical_error,
                    )

                result_message = "no rows in requested window" if collected_count == 0 else str(mode_message or "")
                if technical_error:
                    result_message = f"{result_message} / technical_warning={technical_error}"
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "normalized_stock_code": normalized_code,
                        "stock_name": stock.stock_name,
                        "status": "success",
                        "mode": mode,
                        "from_date": from_date.isoformat() if from_date else None,
                        "to_date": to_date.isoformat() if to_date else None,
                        "collected_count": collected_count,
                        "saved_count": saved_count,
                        "technical_indicator_saved_count": technical_saved_count,
                        "technical_indicator_latest_trade_date": technical_latest_trade_date,
                        "source": source,
                        "message": self._truncate_message(result_message),
                    }
                )
            except HTTPException as exc:
                error_text = self._truncate_message(f"{type(exc).__name__}: {exc.detail}")
                logger.error("[PRICE DEBUG] error_type=%s error_message=%s", type(exc).__name__, error_text)
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "normalized_stock_code": normalize_kr_stock_code(stock.stock_code),
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "mode": mode,
                        "from_date": from_date.isoformat() if from_date else None,
                        "to_date": to_date.isoformat() if to_date else None,
                        "collected_count": 0,
                        "saved_count": 0,
                        "source": source,
                        "message": error_text,
                    }
                )
            except Exception as exc:
                logger.exception(
                    "price collection failed: stock_id=%s stock_code=%s source=%s",
                    stock.id,
                    stock.stock_code,
                    source,
                )
                error_text = self._truncate_message(f"{type(exc).__name__}: {str(exc)}")
                logger.error("[PRICE DEBUG] error_type=%s error_message=%s", type(exc).__name__, error_text)
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "normalized_stock_code": normalize_kr_stock_code(stock.stock_code),
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "mode": mode,
                        "from_date": from_date.isoformat() if from_date else None,
                        "to_date": to_date.isoformat() if to_date else None,
                        "collected_count": 0,
                        "saved_count": 0,
                        "source": source,
                        "message": error_text,
                    }
                )

        requested = len(selected_ids)
        run_message = (
            f"requested={requested} success={success_count} failed={failed_count} "
            f"skipped={skipped_count} saved={saved_total} technical_saved={technical_saved_total} source={source}"
        )
        failed_items = [
            {
                "stock_id": r.get("stock_id"),
                "stock_code": r.get("stock_code"),
                "normalized_stock_code": r.get("normalized_stock_code"),
                "stock_name": r.get("stock_name"),
                "message": self._truncate_message(str(r.get("message") or ""), max_len=180),
            }
            for r in results
            if r.get("status") == "failed"
        ]
        if failed_items:
            run_message = self._truncate_message(f"{run_message} failed_items={failed_items[:3]}", max_len=1000)

        if failed_count > 0 and success_count == 0:
            self.run_repo.mark_failed(run, run_message)
        elif failed_count > 0:
            self.run_repo.mark_partial(run, run_message)
        else:
            self.run_repo.mark_success(run, run_message)

        logger.info("selected stock price collection done: %s", run_message)

        return {
            "requested_count": requested,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "saved_count": saved_total,
            "technical_indicator_saved_count": technical_saved_total,
            "source": source,
            "message": "selected stock candle collection completed",
            "results": results,
        }

    def calculate_and_save_technical_indicators(self, stock_id: int) -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
        return self.technical_indicator_service.calculate_and_save_for_stock(stock_id=stock_id)

    def calculate_and_save_technical_indicators_for_selected(self, stock_ids: list[int]) -> dict:
        selected_ids = self._validate_selected_stock_ids(stock_ids)
        items: list[dict] = []
        success_count = 0
        failed_count = 0
        saved_total = 0
        for stock_id in selected_ids:
            try:
                result = self.calculate_and_save_technical_indicators(stock_id)
                success_count += 1
                saved_total += int(result["saved_count"])
                items.append({**result, "status": "success"})
            except Exception as exc:
                failed_count += 1
                items.append(
                    {
                        "stock_id": stock_id,
                        "calculated_count": 0,
                        "saved_count": 0,
                        "latest_trade_date": None,
                        "message": str(exc),
                        "status": "failed",
                    }
                )
        return {
            "total_requested": len(selected_ids),
            "success_count": success_count,
            "failed_count": failed_count,
            "saved_count": saved_total,
            "items": items,
            "message": "선택 종목 기술적 지표 재계산이 완료되었습니다.",
        }

    def list_summary(
        self,
        keyword: str | None,
        market: str | None,
        source: str | None,
        scope: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        resolved_scope = (scope or "watchlist").strip().lower()
        if resolved_scope not in {"watchlist", "all"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid scope")
        items = self.price_repo.list_price_summary(
            keyword=keyword,
            market=market,
            source=source,
            scope=resolved_scope,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "limit": limit, "offset": offset}

    @staticmethod
    def _round_float(value: float | None, digits: int = 4) -> float | None:
        if value is None:
            return None
        return round(float(value), digits)

    @staticmethod
    def _calc_change_rate_from_prices(latest_close: float | None, base_close: float | None) -> float | None:
        if latest_close is None or base_close in (None, 0):
            return None
        return round(((float(latest_close) - float(base_close)) / float(base_close)) * 100, 4)

    @staticmethod
    def _calc_avg_volume(rows: list, limit: int = 20) -> float | None:
        volumes = [int(row.volume) for row in rows[:limit] if row.volume is not None]
        if not volumes:
            return None
        return round(sum(volumes) / len(volumes), 4)

    def get_summary(self, stock_id: int, source: str = "kiwoom_rest") -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        summary_window = self.price_repo.get_stock_summary_window(stock_id=stock_id, source=source)
        if not summary_window:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock price summary not found")

        recent_rows = self.price_repo.list_recent_rows(stock_id=stock_id, source=source, limit=252)
        if not recent_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock price summary not found")

        latest_row = recent_rows[0]
        row_5d_ago = recent_rows[5] if len(recent_rows) >= 6 else None

        high_52w = None
        high_52w_date = None
        for row in recent_rows:
            if row.high_price is None:
                continue
            if high_52w is None or float(row.high_price) > high_52w:
                high_52w = float(row.high_price)
                high_52w_date = row.trade_date

        return {
            "stock_id": stock.id,
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "source": source,
            "price_count": int(summary_window["price_count"]),
            "min_trade_date": summary_window["min_trade_date"],
            "max_trade_date": summary_window["max_trade_date"],
            "latest_trade_date": latest_row.trade_date,
            "latest_close_price": self._round_float(latest_row.close_price),
            "latest_ma5": self._round_float(latest_row.ma5),
            "latest_ma20": self._round_float(latest_row.ma20),
            "latest_ma60": self._round_float(latest_row.ma60),
            "recent_5d_change_rate": self._calc_change_rate_from_prices(
                latest_close=latest_row.close_price,
                base_close=None if row_5d_ago is None else row_5d_ago.close_price,
            ),
            "avg_volume_20d": self._calc_avg_volume(recent_rows, limit=20),
            "high_52w": self._round_float(high_52w),
            "high_52w_date": high_52w_date,
            "price_position_vs_52w_high": (
                None
                if high_52w in (None, 0) or latest_row.close_price is None
                else round((float(latest_row.close_price) / high_52w) * 100, 4)
            ),
        }

    def list_daily(
        self,
        stock_id: int,
        start_date: str | None,
        end_date: str | None,
        source: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
        rows = self.price_repo.list_by_stock_with_technical_indicators(
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
            source=source,
            limit=limit,
            offset=offset,
        )
        items = [StockDailyPriceListItem(**row, stock_code=stock.stock_code, stock_name=stock.stock_name) for row in rows]
        return {
            "stock_id": stock.id,
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "items": items,
            "limit": limit,
            "offset": offset,
        }
