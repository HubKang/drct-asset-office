from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.collectors.prices.mock_price_collector import MockPriceCollector
from backend.app.collectors.prices.pykrx_price_collector import (
    PykrxPriceCollector,
    normalize_stock_code_for_pykrx,
)
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository
from backend.app.schemas.stock_price_schema import StockDailyPriceListItem


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

    def _collect_rows_by_source(self, stock, start_date: date, end_date: date, source: str) -> tuple[str, list[dict]]:
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
            return normalize_stock_code_for_pykrx(stock.stock_code), payload
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
            return normalized, payload
        if source == "broker_kis":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="broker_kis는 현재 보류 상태입니다. source=pykrx를 사용해 주세요.",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"지원하지 않는 source입니다: {source}")

    def _resolve_collect_window(self, stock_id: int, source: str, period_years: int) -> tuple[str, date, date, str]:
        today = date.today()
        if source != "pykrx":
            start_date = today - timedelta(days=max(1, period_years) * 365)
            return "initial_backfill", start_date, today, "최근 2년치 수집"

        latest_trade_date = self.price_repo.get_latest_trade_date(stock_id=stock_id, source="pykrx")
        if not latest_trade_date:
            start_date = today - timedelta(days=max(1, period_years) * 365)
            return "initial_backfill", start_date, today, "최초 수집, 최근 2년치 수집"

        latest = self._parse_iso_date(latest_trade_date)
        if latest < today:
            return "incremental", latest, today, f"증분 수집, {latest_trade_date} 이후 데이터 수집"

        refresh_start = today - timedelta(days=7)
        return "refresh_latest", refresh_start, today, "최신 데이터 재조회/당일 갱신"

    def _collect_and_upsert(self, stock, source: str, start_date: date, end_date: date) -> tuple[str, int, int]:
        normalized, payload = self._collect_rows_by_source(stock, start_date, end_date, source)
        collected_count = len(payload)
        saved = self.price_repo.upsert_daily_rows(stock.id, source, payload)
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
        return normalized, collected_count, saved

    def collect_selected_backfill(self, stock_ids: list[int], period_years: int, source: str) -> dict:
        selected_ids = self._validate_selected_stock_ids(stock_ids)
        active_ids = set(self.watchlist_repo.list_active_stock_ids())
        selected_stocks = [self.stock_repo.get_by_id(sid) for sid in selected_ids]
        run_codes = [s.stock_code for s in selected_stocks if s]
        run = self.run_repo.create_running("watchlist_selected_price_backfill_collector", f"selected:{','.join(run_codes)}")

        success_count = 0
        failed_count = 0
        skipped_count = 0
        saved_total = 0
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
                        "normalized_stock_code": normalize_stock_code_for_pykrx(stock.stock_code),
                        "stock_name": stock.stock_name,
                        "status": "skipped",
                        "mode": None,
                        "from_date": None,
                        "to_date": None,
                        "collected_count": 0,
                        "saved_count": 0,
                        "source": source,
                        "message": "비활성 관심종목이어서 건너뜀",
                    }
                )
                continue

            try:
                mode, from_date, to_date, mode_message = self._resolve_collect_window(stock.id, source, period_years)
                logger.info(
                    "일봉 수집 시작: stock_id=%s stock_code=%s source=%s mode=%s from=%s to=%s",
                    stock.id,
                    stock.stock_code,
                    source,
                    mode,
                    from_date.isoformat(),
                    to_date.isoformat(),
                )
                normalized_code, collected_count, saved_count = self._collect_and_upsert(
                    stock=stock,
                    source=source,
                    start_date=from_date,
                    end_date=to_date,
                )
                success_count += 1
                saved_total += saved_count

                result_message = "조회기간 내 신규 거래일 없음" if collected_count == 0 else mode_message
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "normalized_stock_code": normalized_code,
                        "stock_name": stock.stock_name,
                        "status": "success",
                        "mode": mode,
                        "from_date": from_date.isoformat(),
                        "to_date": to_date.isoformat(),
                        "collected_count": collected_count,
                        "saved_count": saved_count,
                        "source": source,
                        "message": result_message,
                    }
                )
            except HTTPException as exc:
                logger.warning(
                    "일봉 수집 실패(HTTP): stock_id=%s stock_code=%s source=%s detail=%s",
                    stock.id,
                    stock.stock_code,
                    source,
                    exc.detail,
                )
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "normalized_stock_code": normalize_stock_code_for_pykrx(stock.stock_code),
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "mode": None,
                        "from_date": None,
                        "to_date": None,
                        "collected_count": 0,
                        "saved_count": 0,
                        "source": source,
                        "message": str(exc.detail),
                    }
                )
            except Exception as exc:
                logger.exception(
                    "일봉 수집 실패: stock_id=%s stock_code=%s source=%s",
                    stock.id,
                    stock.stock_code,
                    source,
                )
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "normalized_stock_code": normalize_stock_code_for_pykrx(stock.stock_code),
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "mode": None,
                        "from_date": None,
                        "to_date": None,
                        "collected_count": 0,
                        "saved_count": 0,
                        "source": source,
                        "message": str(exc),
                    }
                )

        requested = len(selected_ids)
        run_message = (
            f"requested={requested} success={success_count} failed={failed_count} "
            f"skipped={skipped_count} saved={saved_total} source={source}"
        )
        if failed_count > 0 and success_count == 0:
            self.run_repo.mark_failed(run, run_message)
        elif failed_count > 0:
            self.run_repo.mark_partial(run, run_message)
        else:
            self.run_repo.mark_success(run, run_message)

        logger.info("선택 종목 일봉 수집 종료: %s", run_message)

        return {
            "requested_count": requested,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "saved_count": saved_total,
            "source": source,
            "message": "선택 종목 캔들 수집 완료",
            "results": results,
        }

    def list_summary(self, keyword: str | None, market: str | None, source: str | None, limit: int, offset: int) -> dict:
        items = self.price_repo.list_price_summary(
            keyword=keyword,
            market=market,
            source=source,
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

    def get_summary(self, stock_id: int, source: str = "pykrx") -> dict:
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
        rows = self.price_repo.list_by_stock(
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
            source=source,
            limit=limit,
            offset=offset,
        )
        items = [
            StockDailyPriceListItem(
                id=row.id,
                stock_id=row.stock_id,
                stock_code=stock.stock_code,
                stock_name=stock.stock_name,
                trade_date=row.trade_date,
                open_price=row.open_price,
                high_price=row.high_price,
                low_price=row.low_price,
                close_price=row.close_price,
                change_price=row.change_price,
                change_rate=row.change_rate,
                volume=row.volume,
                trading_value=row.trading_value,
                ma5=row.ma5,
                ma10=row.ma10,
                ma20=row.ma20,
                ma60=row.ma60,
                ma120=row.ma120,
                ma240=row.ma240,
                source=row.source,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return {
            "stock_id": stock.id,
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "items": items,
            "limit": limit,
            "offset": offset,
        }
