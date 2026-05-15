from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.collectors.market_metrics.krx_open_api_market_metrics_collector import KRXOpenAPIMarketMetricsCollector
from backend.app.collectors.market_metrics.marcap_market_metrics_collector import MarcapMarketMetricsCollector
from backend.app.collectors.prices.pykrx_price_collector import normalize_stock_code_for_pykrx
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.stock_market_metric_repository import StockMarketMetricRepository
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.stock_repository import StockRepository


logger = logging.getLogger(__name__)

KRX_AUTHORIZATION_FAILED_MESSAGE = (
    "KRX Open API authorization failed. Check whether this API key is approved for the requested "
    "KRX daily trading information services. Verify service approval for the KOSPI and KOSDAQ daily "
    "trading information APIs in the KRX Open API portal."
)


class StockMarketMetricService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.metric_repo = StockMarketMetricRepository(db)
        self.price_repo = StockPriceRepository(db)
        self.run_repo = CollectionRunRepository(db)
        self.collectors = {
            "marcap": MarcapMarketMetricsCollector(),
            "krx_open_api": KRXOpenAPIMarketMetricsCollector(),
        }

    @staticmethod
    def _percentile(rank: int | None, total: int) -> float | None:
        if rank is None or total <= 0:
            return None
        return round(((total - rank + 1) / total) * 100, 4)

    @staticmethod
    def _parse_date(raw: str | None) -> date | None:
        if not raw:
            return None
        return datetime.strptime(raw, "%Y-%m-%d").date()

    @staticmethod
    def _to_latest_payload(stock, metric, source: str) -> dict:
        return {
            "stock_id": stock.id,
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "source": source,
            "trade_date": metric.trade_date,
            "market": metric.market,
            "close_price": metric.close_price,
            "market_cap": metric.market_cap,
            "listed_shares": metric.listed_shares,
            "trading_volume": metric.trading_volume,
            "trading_value": metric.trading_value,
            "market_cap_rank": metric.market_cap_rank,
            "trading_value_rank": metric.trading_value_rank,
            "market_trading_value_rank": metric.market_trading_value_rank,
            "trading_value_percentile": metric.trading_value_percentile,
            "market_trading_value_percentile": metric.market_trading_value_percentile,
        }

    @staticmethod
    def _calc_staleness_level(stale_days: int | None) -> tuple[bool, str]:
        if stale_days is None:
            return False, "unknown"
        if stale_days == 0:
            return False, "fresh"
        if 1 <= stale_days <= 3:
            return False, "acceptable"
        if 4 <= stale_days <= 20:
            return True, "stale"
        return True, "severely_stale"

    def _collect_rows(self, trade_date: str, source: str):
        collector = self.collectors.get(source)
        if not collector:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported source: {source}")

        requested_trade_date = str(date.fromisoformat(trade_date))
        run = self.run_repo.create_running(collector.name, trade_date)

        try:
            collected_rows = collector.collect_daily(trade_date=trade_date)
            return requested_trade_date, run, collected_rows
        except LookupError as exc:
            self.run_repo.mark_failed(run, str(exc))
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except RuntimeError as exc:
            self.run_repo.mark_failed(run, str(exc))
            detail = str(exc)
            if detail == "KRX_OPEN_API_AUTH_KEY is not configured.":
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail) from exc
            if "401" in detail and "Unauthorized" in detail:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=KRX_AUTHORIZATION_FAILED_MESSAGE) from exc
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
        except HTTPException as exc:
            self.run_repo.mark_failed(run, str(exc.detail))
            raise
        except Exception as exc:
            self.run_repo.mark_failed(run, str(exc))
            logger.exception("Market metrics collection failed: trade_date=%s source=%s", trade_date, source)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    def collect_daily(self, trade_date: str, source: str = "marcap") -> dict:
        requested_trade_date, run, collected_rows = self._collect_rows(trade_date=trade_date, source=source)
        requested_count = len(collected_rows)

        stocks = self.stock_repo.list(keyword=None, is_active=None, market=None, security_type=None, limit=10000, offset=0)
        code_to_stock = {
            normalize_stock_code_for_pykrx(stock.stock_code): stock
            for stock in stocks
            if normalize_stock_code_for_pykrx(stock.stock_code)
        }

        valid_value_rows = [row for row in collected_rows if row.trading_value not in (None, 0)]
        valid_value_rows.sort(key=lambda row: row.trading_value, reverse=True)
        overall_rank_map = {row.ticker: idx + 1 for idx, row in enumerate(valid_value_rows)}
        overall_total = len(valid_value_rows)

        market_groups: dict[str, list] = defaultdict(list)
        for row in valid_value_rows:
            market_groups[row.market or "UNKNOWN"].append(row)

        market_rank_map: dict[tuple[str, str], int] = {}
        market_total_map: dict[str, int] = {}
        for market_name, rows in market_groups.items():
            rows.sort(key=lambda row: row.trading_value, reverse=True)
            market_total_map[market_name] = len(rows)
            for idx, row in enumerate(rows):
                market_rank_map[(market_name, row.ticker)] = idx + 1

        matched_count = 0
        skipped_count = 0
        failed_count = 0
        save_rows: list[dict] = []

        for row in collected_rows:
            stock = code_to_stock.get(row.ticker)
            if not stock:
                skipped_count += 1
                continue

            matched_count += 1
            market_name = row.market or "UNKNOWN"
            trading_value_rank = overall_rank_map.get(row.ticker)
            market_trading_value_rank = market_rank_map.get((market_name, row.ticker))
            save_rows.append(
                {
                    "stock_id": stock.id,
                    "trade_date": row.trade_date,
                    "market": row.market,
                    "close_price": row.close_price,
                    "market_cap": row.market_cap,
                    "listed_shares": row.listed_shares,
                    "trading_volume": row.trading_volume,
                    "trading_value": row.trading_value,
                    "market_cap_rank": row.market_cap_rank,
                    "trading_value_rank": trading_value_rank,
                    "market_trading_value_rank": market_trading_value_rank,
                    "trading_value_percentile": self._percentile(trading_value_rank, overall_total),
                    "market_trading_value_percentile": self._percentile(
                        market_trading_value_rank,
                        market_total_map.get(market_name, 0),
                    ),
                    "source": source,
                }
            )

        saved_count = self.metric_repo.upsert_rows(save_rows)
        message = (
            f"Market metrics collection completed. requested={requested_count} matched={matched_count} "
            f"saved={saved_count} skipped={skipped_count} failed={failed_count} source={source}"
        )
        self.run_repo.mark_success(run, message)
        logger.info(message)
        return {
            "trade_date": requested_trade_date,
            "source": source,
            "requested_count": requested_count,
            "matched_count": matched_count,
            "saved_count": saved_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "message": message,
        }

    def get_latest(self, stock_id: int, source: str = "marcap") -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        metric = self.metric_repo.get_latest_by_stock_id(stock_id=stock_id, source=source)
        if not metric:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market metrics not found")
        return self._to_latest_payload(stock=stock, metric=metric, source=source)

    def get_summary(self, stock_id: int, source: str = "marcap") -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        metric = self.metric_repo.get_latest_by_stock_id(stock_id=stock_id, source=source)
        if not metric:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market metrics not found")

        latest_market_metrics_date = metric.trade_date
        latest_price_trade_date = self.price_repo.get_latest_trade_date(stock_id=stock_id, source="pykrx")

        metrics_dt = self._parse_date(latest_market_metrics_date)
        price_dt = self._parse_date(latest_price_trade_date)
        stale_days = None if metrics_dt is None or price_dt is None else (price_dt - metrics_dt).days
        is_stale, staleness_level = self._calc_staleness_level(stale_days)

        if latest_price_trade_date:
            if stale_days and stale_days > 0:
                data_note = (
                    f"Market metrics are based on {latest_market_metrics_date} and are older than the latest "
                    f"price data date {latest_price_trade_date}."
                )
            else:
                data_note = (
                    f"Market metrics are based on {latest_market_metrics_date} and aligned with the latest "
                    f"price data date {latest_price_trade_date}."
                )
        else:
            data_note = f"Market metrics are based on {latest_market_metrics_date}, and no latest price data date is available."

        return {
            "stock_id": stock.id,
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "source": source,
            "latest_market_metrics_date": latest_market_metrics_date,
            "latest_price_trade_date": latest_price_trade_date,
            "is_stale": is_stale,
            "stale_days": stale_days,
            "staleness_level": staleness_level,
            "market": metric.market,
            "trading_value": metric.trading_value,
            "market_cap": metric.market_cap,
            "listed_shares": metric.listed_shares,
            "trading_volume": metric.trading_volume,
            "market_cap_rank": metric.market_cap_rank,
            "trading_value_rank": metric.trading_value_rank,
            "market_trading_value_rank": metric.market_trading_value_rank,
            "trading_value_percentile": metric.trading_value_percentile,
            "market_trading_value_percentile": metric.market_trading_value_percentile,
            "data_note": data_note,
        }
