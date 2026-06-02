from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.collectors.market_metrics.krx_open_api_market_metrics_collector import KRXOpenAPIMarketMetricsCollector
from backend.app.collectors.market_metrics.kis_market_metrics_collector import KisMarketMetricsCollector
from backend.app.collectors.market_metrics.marcap_market_metrics_collector import MarcapMarketMetricsCollector
from backend.app.collectors.prices.pykrx_price_collector import normalize_stock_code_for_pykrx
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.stock_market_metric_repository import StockMarketMetricRepository
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository
from backend.app.providers.market_data.kiwoom_rest_market_indicator_provider import KiwoomRestMarketIndicatorProvider


logger = logging.getLogger(__name__)

KRX_AUTHORIZATION_FAILED_MESSAGE = (
    "KRX Open API authorization failed. Check whether this API key is approved for the requested "
    "KRX daily trading information services. Verify service approval for the KOSPI and KOSDAQ daily "
    "trading information APIs in the KRX Open API portal."
)


class StockMarketMetricService:
    SOURCE_PRIORITY = ["kiwoom_rest", "kis_api", "krx_open_api", "data_go_kr", "marcap"]

    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.metric_repo = StockMarketMetricRepository(db)
        self.price_repo = StockPriceRepository(db)
        self.watchlist_repo = WatchlistRepository(db)
        self.run_repo = CollectionRunRepository(db)
        self.collectors = {
            "marcap": MarcapMarketMetricsCollector(),
            "krx_open_api": KRXOpenAPIMarketMetricsCollector(),
            "kis_api": KisMarketMetricsCollector(),
        }
        self.kiwoom_market_provider = KiwoomRestMarketIndicatorProvider()

    def _resolve_metric_with_source(self, stock_id: int, source: str):
        if source == "auto":
            metric, resolved_source = self.metric_repo.get_latest_by_stock_id_with_source_priority(
                stock_id=stock_id,
                source_priority=self.SOURCE_PRIORITY,
            )
            return metric, (resolved_source or "unknown")
        metric = self.metric_repo.get_latest_by_stock_id(stock_id=stock_id, source=source)
        return metric, source

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
        if stale_days < 0:
            return False, "fresh"
        if stale_days == 0:
            return False, "fresh"
        if 1 <= stale_days <= 3:
            return False, "acceptable"
        if 4 <= stale_days <= 20:
            return True, "stale"
        return True, "severely_stale"

    @staticmethod
    def _format_eok_won(value: int | float | None) -> str | None:
        if value is None:
            return None
        amount = float(value)
        eok = amount / 100_000_000
        if abs(eok) >= 100:
            return f"{round(eok):,}억 원"
        rounded = round(eok, 1)
        return f"{rounded:,}억 원"

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
                    "foreign_ownership_ratio": None,
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

    def get_latest(self, stock_id: int, source: str = "auto") -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        metric, resolved_source = self._resolve_metric_with_source(stock_id=stock_id, source=source)
        if not metric:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market metrics not found")
        return self._to_latest_payload(stock=stock, metric=metric, source=resolved_source)

    def get_summary(self, stock_id: int, source: str = "kiwoom_rest") -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        metric = None
        resolved_source = source
        if source == "kiwoom_rest":
            metric, _ = self.metric_repo.get_latest_by_stock_id_with_source_priority(
                stock_id=stock_id,
                source_priority=self.SOURCE_PRIORITY,
            )
            resolved_source = "kiwoom_rest"
        else:
            metric, resolved_source = self._resolve_metric_with_source(stock_id=stock_id, source=source)

        latest_price_trade_date = self.price_repo.get_latest_trade_date(stock_id=stock_id, source="kiwoom_rest")
        latest_price_rows = self.price_repo.list_recent_rows(stock_id=stock_id, source="kiwoom_rest", limit=1)
        latest_price_row = latest_price_rows[0] if latest_price_rows else None

        latest_market_metrics_date = (metric.trade_date if metric else None) or latest_price_trade_date or ""

        metrics_dt = self._parse_date(latest_market_metrics_date)
        price_dt = self._parse_date(latest_price_trade_date)
        stale_days = None if metrics_dt is None or price_dt is None else (price_dt - metrics_dt).days
        is_stale, staleness_level = self._calc_staleness_level(stale_days)

        date_gap_days = stale_days
        date_gap_label = None
        freshness_status = "normal"
        freshness_label = "정상"
        freshness_message = "시장지표 기준일이 가격 기준일과 일치합니다."
        if latest_price_trade_date:
            if stale_days is None:
                freshness_status = "missing"
                freshness_label = "확인 필요"
                freshness_message = "시장지표 기준일과 가격 기준일 비교가 불가능합니다."
                date_gap_label = "비교 불가"
            elif stale_days < 0:
                freshness_status = "normal"
                freshness_label = "정상"
                date_gap_label = f"가격 기준일보다 {abs(stale_days)}일 이후"
                freshness_message = "시장지표 기준일이 가격 기준일보다 최신입니다."
            elif stale_days == 0:
                freshness_status = "normal"
                freshness_label = "정상"
                date_gap_label = "동일"
                freshness_message = "시장지표 기준일이 가격 기준일과 일치합니다."
            elif stale_days <= 3:
                freshness_status = "normal"
                freshness_label = "주의"
                date_gap_label = f"가격 기준일보다 {stale_days}일 이전"
                freshness_message = "시장지표 기준일이 가격 기준일보다 약간 이전입니다."
            elif stale_days <= 10:
                freshness_status = "warning"
                freshness_label = "주의"
                date_gap_label = f"가격 기준일보다 {stale_days}일 이전"
                freshness_message = "시장지표 기준일이 가격 기준일보다 이전입니다. 최신성 확인이 필요합니다."
            else:
                freshness_status = "stale"
                freshness_label = "지연"
                date_gap_label = f"가격 기준일보다 {stale_days}일 이전"
                freshness_message = "시장지표 기준일이 오래되어 현재 판단에 주의가 필요합니다."

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

        trading_value = (metric.trading_value if metric else None) or (latest_price_row.trading_value if latest_price_row else None)
        trading_volume = (metric.trading_volume if metric else None) or (latest_price_row.volume if latest_price_row else None)
        market_cap = metric.market_cap if metric else None
        listed_shares = metric.listed_shares if metric else None
        foreign_ownership_ratio = metric.foreign_ownership_ratio if metric else None
        used_api_ids = ["ka10001", "ka10015", "ka10009", "ka10008"] if metric else []
        source_label = "KIWOOM_REST (ka10001, ka10015, ka10009, ka10008)" if metric else "미수집"

        return {
            "stock_id": stock.id,
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "source": resolved_source,
            "latest_market_metrics_date": latest_market_metrics_date,
            "latest_price_trade_date": latest_price_trade_date,
            "date_gap_days": date_gap_days,
            "date_gap_label": date_gap_label,
            "freshness_status": freshness_status,
            "freshness_label": freshness_label,
            "freshness_message": freshness_message,
            "is_stale": is_stale,
            "stale_days": stale_days,
            "staleness_level": staleness_level,
            "market": (stock.market or (metric.market if metric else None)),
            "trading_value": trading_value,
            "trading_value_display": self._format_eok_won(trading_value),
            "market_cap": market_cap,
            "market_cap_display": self._format_eok_won(market_cap),
            "listed_shares": listed_shares,
            "trading_volume": trading_volume,
            "market_cap_rank": (metric.market_cap_rank if metric else None),
            "trading_value_rank": (metric.trading_value_rank if metric else None),
            "market_trading_value_rank": (metric.market_trading_value_rank if metric else None),
            "trading_value_percentile": (metric.trading_value_percentile if metric else None),
            "market_trading_value_percentile": (metric.market_trading_value_percentile if metric else None),
            "foreign_ownership_ratio": foreign_ownership_ratio,
            "used_api_ids": used_api_ids if resolved_source == "kiwoom_rest" else [],
            "source_label": source_label if resolved_source == "kiwoom_rest" else (resolved_source.upper() if resolved_source else None),
            "unit_notes": {
                "market_cap": "원",
                "trading_value": "원(제공값 기준)",
                "display": "화면 표시는 억 원 단위",
            },
            "data_note": data_note,
        }

    def get_market_overview(self, source: str = "kiwoom_rest") -> dict:
        if source != "kiwoom_rest":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported source: {source}")
        try:
            return self.kiwoom_market_provider.get_market_overview()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="시장 개요 조회에 실패했습니다. Kiwoom REST API 연결 상태와 인증 정보를 확인해 주세요.",
            ) from exc

    def collect_selected(self, stock_ids: list[int], source: str = "kiwoom_rest") -> dict:
        if source not in {"kiwoom_rest", "kis_api"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported source: {source}")
        selected = [sid for sid in stock_ids if isinstance(sid, int)]
        if not selected:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="선택된 종목이 없습니다.")

        run = self.run_repo.create_running("watchlist_selected_market_metrics_collector", f"selected:{','.join(map(str, selected))}")
        active_ids = set(self.watchlist_repo.list_active_stock_ids())
        collector = self.collectors["kis_api"] if source == "kis_api" else None

        success_count = 0
        failed_count = 0
        skipped_count = 0
        saved_total = 0
        results: list[dict] = []

        for stock_id in selected:
            stock = self.stock_repo.get_by_id(stock_id)
            if not stock:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock_id,
                        "stock_code": "",
                        "stock_name": "",
                        "trade_date": None,
                        "source": source,
                        "status": "failed",
                        "error_type": "invalid_symbol",
                        "message": "stock not found",
                        "saved_count": 0,
                    }
                )
                continue
            if stock_id not in active_ids:
                skipped_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "trade_date": None,
                        "source": source,
                        "status": "skipped",
                        "error_type": None,
                        "message": "비활성 관심종목입니다.",
                        "saved_count": 0,
                    }
                )
                continue
            normalized = normalize_stock_code_for_pykrx(stock.stock_code)
            if not normalized:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "trade_date": None,
                        "source": source,
                        "status": "failed",
                        "error_type": "invalid_symbol",
                        "message": "invalid stock code",
                        "saved_count": 0,
                    }
                )
                continue

            try:
                if source == "kiwoom_rest":
                    row = self.kiwoom_market_provider.get_stock_market_metrics(stock_code=normalized, market=stock.market)
                    trade_date = row.get("trade_date")
                    if not trade_date:
                        raise RuntimeError("kiwoom_trade_date_missing")
                    save_row = {
                        "stock_id": stock.id,
                        "trade_date": trade_date,
                        "market": row.get("market") or stock.market,
                        "close_price": row.get("close_price"),
                        "market_cap": row.get("market_cap"),
                        "listed_shares": row.get("listed_shares"),
                        "trading_volume": row.get("trading_volume"),
                        "trading_value": row.get("trading_value"),
                        "market_cap_rank": None,
                        "trading_value_rank": None,
                        "market_trading_value_rank": None,
                        "trading_value_percentile": None,
                        "market_trading_value_percentile": None,
                        "foreign_ownership_ratio": row.get("foreign_ownership_ratio"),
                        "source": source,
                    }
                    item_message = "Kiwoom REST 시장지표 갱신 완료"
                else:
                    row = collector.collect_latest(normalized)
                    save_row = {
                        "stock_id": stock.id,
                        "trade_date": row.trade_date,
                        "market": row.market or stock.market,
                        "close_price": row.close_price,
                        "market_cap": row.market_cap,
                        "listed_shares": row.listed_shares,
                        "trading_volume": row.trading_volume,
                        "trading_value": row.trading_value,
                        "market_cap_rank": None,
                        "trading_value_rank": None,
                        "market_trading_value_rank": None,
                        "trading_value_percentile": None,
                        "market_trading_value_percentile": None,
                        "foreign_ownership_ratio": None,
                        "source": source,
                    }
                    item_message = "시장지표 갱신 완료"
                save_rows = [save_row]
                saved = self.metric_repo.upsert_rows(save_rows)
                success_count += 1
                saved_total += saved
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "trade_date": save_row["trade_date"],
                        "source": source,
                        "status": "success",
                        "error_type": None,
                        "message": item_message,
                        "saved_count": saved,
                    }
                )
            except RuntimeError as exc:
                failed_count += 1
                error_type = str(exc)
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "trade_date": None,
                        "source": source,
                        "status": "failed",
                        "error_type": error_type,
                        "message": f"{source} 수집 실패({error_type})",
                        "saved_count": 0,
                    }
                )
            except Exception:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "trade_date": None,
                        "source": source,
                        "status": "failed",
                        "error_type": "unknown_error",
                        "message": f"{source} 수집 실패(unknown_error)",
                        "saved_count": 0,
                    }
                )

        requested = len(selected)
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
        return {
            "success": failed_count == 0,
            "source": source,
            "requested_count": requested,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "saved_count": saved_total,
            "message": "선택 시장지표 갱신 완료",
            "results": results,
        }
