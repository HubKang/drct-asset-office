from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.collectors.prices.mock_price_collector import MockPriceCollector
from backend.app.entities.stock_daily_price import StockDailyPrice
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository


class StockPriceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.watchlist_repo = WatchlistRepository(db)
        self.price_repo = StockPriceRepository(db)
        self.run_repo = CollectionRunRepository(db)
        self.mock_collector = MockPriceCollector()

    def _validate_selected_stock_ids(self, stock_ids: list[int]) -> list[int]:
        selected = [int(sid) for sid in stock_ids if isinstance(sid, int)]
        if not selected:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="선택된 종목이 없습니다.")
        return selected

    def _calc_sma(self, values: list[float], idx: int, window: int) -> float | None:
        if idx + 1 < window:
            return None
        sub = values[idx - window + 1 : idx + 1]
        return round(sum(sub) / window, 4)

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

    def _collect_for_stock(self, stock_id: int, start_date: date, end_date: date, source: str) -> tuple[int, str]:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
        if source != "mock":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only mock source is supported in this stage")

        rows = self.mock_collector.collect_daily(
            stock_id=stock.id,
            stock_code=stock.stock_code,
            start_date=start_date,
            end_date=end_date,
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
        saved = self.price_repo.upsert_daily_rows(stock.id, source, payload)
        self.recalculate_moving_averages(stock.id)
        return saved, stock.stock_code

    def collect_selected_backfill(self, stock_ids: list[int], period_years: int, source: str) -> dict:
        selected_ids = self._validate_selected_stock_ids(stock_ids)
        active_ids = set(self.watchlist_repo.list_active_stock_ids())
        selected_stocks = [self.stock_repo.get_by_id(sid) for sid in selected_ids]
        codes = [s.stock_code for s in selected_stocks if s]
        run = self.run_repo.create_running("watchlist_selected_price_backfill_collector", f"selected:{','.join(codes)}")

        end_date = date.today()
        start_date = end_date - timedelta(days=max(1, period_years) * 365)
        success_count = 0
        failed_count = 0
        saved_total = 0
        results: list[dict] = []

        for sid in selected_ids:
            stock = self.stock_repo.get_by_id(sid)
            if not stock:
                failed_count += 1
                results.append({"stock_id": sid, "stock_code": "", "stock_name": "", "status": "failed", "saved_count": 0, "message": "stock not found"})
                continue
            if sid not in active_ids:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "saved_count": 0,
                        "message": "활성 관심종목이 아닙니다.",
                    }
                )
                continue
            try:
                saved, _ = self._collect_for_stock(stock.id, start_date, end_date, source)
                success_count += 1
                saved_total += saved
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "success",
                        "saved_count": saved,
                        "message": f"{source} backfill",
                    }
                )
            except HTTPException as exc:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "saved_count": 0,
                        "message": str(exc.detail),
                    }
                )

        requested = len(selected_ids)
        msg = f"requested={requested} success={success_count} failed={failed_count} saved={saved_total} source={source}"
        if failed_count > 0 and success_count > 0:
            self.run_repo.mark_partial(run, msg)
        elif failed_count == requested:
            self.run_repo.mark_failed(run, msg)
        else:
            self.run_repo.mark_success(run, msg)
        return {
            "requested_count": requested,
            "success_count": success_count,
            "failed_count": failed_count,
            "saved_count": saved_total,
            "message": "선택 종목 일봉 데이터 수집 완료",
            "results": results,
        }

    def update_selected_recent(self, stock_ids: list[int], source: str) -> dict:
        selected_ids = self._validate_selected_stock_ids(stock_ids)
        active_ids = set(self.watchlist_repo.list_active_stock_ids())
        selected_stocks = [self.stock_repo.get_by_id(sid) for sid in selected_ids]
        codes = [s.stock_code for s in selected_stocks if s]
        run = self.run_repo.create_running("watchlist_selected_price_update_collector", f"selected:{','.join(codes)}")

        end_date = date.today()
        start_date = end_date - timedelta(days=10)
        success_count = 0
        failed_count = 0
        saved_total = 0
        results: list[dict] = []

        for sid in selected_ids:
            stock = self.stock_repo.get_by_id(sid)
            if not stock:
                failed_count += 1
                results.append({"stock_id": sid, "stock_code": "", "stock_name": "", "status": "failed", "saved_count": 0, "message": "stock not found"})
                continue
            if sid not in active_ids:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "saved_count": 0,
                        "message": "활성 관심종목이 아닙니다.",
                    }
                )
                continue
            try:
                saved, _ = self._collect_for_stock(stock.id, start_date, end_date, source)
                success_count += 1
                saved_total += saved
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "success",
                        "saved_count": saved,
                        "message": f"{source} update",
                    }
                )
            except HTTPException as exc:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "saved_count": 0,
                        "message": str(exc.detail),
                    }
                )

        requested = len(selected_ids)
        msg = f"requested={requested} success={success_count} failed={failed_count} saved={saved_total} source={source}"
        if failed_count > 0 and success_count > 0:
            self.run_repo.mark_partial(run, msg)
        elif failed_count == requested:
            self.run_repo.mark_failed(run, msg)
        else:
            self.run_repo.mark_success(run, msg)
        return {
            "requested_count": requested,
            "success_count": success_count,
            "failed_count": failed_count,
            "saved_count": saved_total,
            "message": "선택 종목 일봉 데이터 갱신 완료",
            "results": results,
        }

    def list_daily(self, stock_id: int, start_date: str | None, end_date: str | None, limit: int, offset: int) -> list[StockDailyPrice]:
        return self.price_repo.list_by_stock(stock_id=stock_id, start_date=start_date, end_date=end_date, limit=limit, offset=offset)
