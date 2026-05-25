from __future__ import annotations

from typing import Any

from backend.app.core import config
from backend.app.repositories.stock_price_repository import StockPriceRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.services.technical_indicator_service import TechnicalIndicatorService
from backend.app.providers.market_data.kiwoom_rest_provider import KiwoomRestMarketDataProvider
from backend.app.schemas.kiwoom_schema import KiwoomPocDailyPriceResponse
from backend.app.utils.stock_code import normalize_stock_code
from sqlalchemy.orm import Session


class KiwoomMarketDataPocService:
    def __init__(self, db: Session | None = None) -> None:
        self.provider = KiwoomRestMarketDataProvider()
        self.db = db
        self.stock_repo = StockRepository(db) if db is not None else None
        self.price_repo = StockPriceRepository(db) if db is not None else None
        self.technical_indicator_service = TechnicalIndicatorService(db) if db is not None else None

    def run_daily_price_poc(
        self,
        *,
        ticker: str,
        mode: str = "recent",
        years: int = 2,
        start_date: str | None = None,
        end_date: str | None = None,
        max_pages: int | None = None,
        repeat_calls: int = 1,
        api_id: str | None = None,
        endpoint: str | None = None,
        save: bool = False,
        calculate_technical: bool = False,
    ) -> KiwoomPocDailyPriceResponse:
        normalized = normalize_stock_code(ticker)
        repeat = max(int(repeat_calls or 1), 1)

        total_elapsed = 0
        repeat_success = 0
        repeat_failed = 0
        last_result: dict[str, Any] | None = None
        error_code = None
        error_message = None

        if mode == "backfill" and not start_date and not end_date:
            # provider 내부에서 years 기준 2년 전 계산
            pass

        for _ in range(repeat):
            try:
                result = self.provider.get_daily_prices(
                    ticker,
                    start_date=start_date,
                    end_date=end_date,
                    years=years if mode == "backfill" else 1,
                    max_pages=max_pages,
                    api_id=api_id,
                    endpoint=endpoint,
                )
                last_result = result
                total_elapsed += int(result.get("elapsed_ms") or 0)
                repeat_success += 1
            except Exception as exc:
                repeat_failed += 1
                error_text = str(exc)
                error_code = error_text.split(":", 1)[0] if error_text else "KIWOOM_UNKNOWN_ERROR"
                error_message = error_text

        if last_result is None:
            return KiwoomPocDailyPriceResponse(
                success=False,
                enabled=config.KIWOOM_REST_ENABLED,
                use_mock=config.KIWOOM_REST_USE_MOCK,
                base_url=config.KIWOOM_REST_MOCK_BASE_URL if config.KIWOOM_REST_USE_MOCK else config.KIWOOM_REST_BASE_URL,
                ticker=ticker,
                normalized_stock_code=normalized,
                repeat_calls=repeat,
                repeat_success=repeat_success,
                repeat_failed=repeat_failed,
                save=save,
                calculate_technical=calculate_technical,
                error_code=error_code,
                error_message=error_message,
            )

        items = last_result.get("items") or []
        sample_items = items[:3]
        first_row = items[0] if items else None
        last_row = items[-1] if items else None
        avg_elapsed = (total_elapsed / repeat_success) if repeat_success > 0 else None
        calls_per_symbol = max(int(last_result.get("api_call_count") or 1), 1)
        rate_limit = max(float(config.KIWOOM_REST_RATE_LIMIT_PER_SECOND or 1), 0.1)
        estimated_50 = round((50 * calls_per_symbol) / rate_limit, 2)
        estimated_100 = round((100 * calls_per_symbol) / rate_limit, 2)
        save_result = self._build_save_result_stub(normalized)

        if self.db is not None and self.stock_repo is not None and self.price_repo is not None:
            save_result = self._prepare_or_save(
                normalized_code=normalized,
                mapped_items=items,
                requested_start_date=last_result.get("requested_start_date"),
                requested_end_date=last_result.get("requested_end_date"),
                save=save,
                calculate_technical=calculate_technical,
            )

        return KiwoomPocDailyPriceResponse(
            success=repeat_success > 0,
            enabled=config.KIWOOM_REST_ENABLED,
            use_mock=config.KIWOOM_REST_USE_MOCK,
            base_url=config.KIWOOM_REST_MOCK_BASE_URL if config.KIWOOM_REST_USE_MOCK else config.KIWOOM_REST_BASE_URL,
            ticker=ticker,
            normalized_stock_code=str(last_result.get("normalized_stock_code") or normalized),
            requested_start_date=last_result.get("requested_start_date"),
            requested_end_date=last_result.get("requested_end_date"),
            actual_min_trade_date=last_result.get("actual_min_trade_date"),
            actual_max_trade_date=last_result.get("actual_max_trade_date"),
            api_id=last_result.get("api_id"),
            api_call_count=int(last_result.get("api_call_count") or 0),
            raw_count=int(last_result.get("raw_count") or 0),
            mapped_count=int(last_result.get("mapped_count") or 0),
            cont_yn_used=bool(last_result.get("cont_yn_used")),
            next_key_used=bool(last_result.get("next_key_used")),
            elapsed_ms=int(last_result.get("elapsed_ms") or 0),
            sample_items=sample_items,
            first_row=first_row,
            last_row=last_row,
            repeat_calls=repeat,
            repeat_success=repeat_success,
            repeat_failed=repeat_failed,
            avg_elapsed_ms=avg_elapsed,
            estimated_50_symbols_seconds=estimated_50,
            estimated_100_symbols_seconds=estimated_100,
            save=save,
            calculate_technical=calculate_technical,
            stock_id=save_result.get("stock_id"),
            stock_name=save_result.get("stock_name"),
            source=save_result.get("source", "kiwoom_rest"),
            existing_price_count_by_source=save_result.get("existing_price_count_by_source", []),
            unique_policy=save_result.get("unique_policy"),
            unique_indexes=save_result.get("unique_indexes", []),
            would_save_count=int(save_result.get("would_save_count") or 0),
            save_blocked_reason=save_result.get("save_blocked_reason"),
            saved_count=int(save_result.get("saved_count") or 0),
            skipped_count=int(save_result.get("skipped_count") or 0),
            technical_saved_count=int(save_result.get("technical_saved_count") or 0),
            error_code=error_code,
            error_message=error_message,
            raw_response_preview=last_result.get("raw_response_preview"),
        )

    @staticmethod
    def _build_save_result_stub(normalized_code: str) -> dict[str, Any]:
        return {
            "stock_id": None,
            "stock_name": None,
            "source": "kiwoom_rest",
            "existing_price_count_by_source": [],
            "unique_policy": "db_unavailable",
            "unique_indexes": [],
            "would_save_count": 0,
            "save_blocked_reason": "DB_SESSION_NOT_PROVIDED",
            "saved_count": 0,
            "skipped_count": 0,
            "technical_saved_count": 0,
        }

    def _prepare_or_save(
        self,
        *,
        normalized_code: str,
        mapped_items: list[dict[str, Any]],
        requested_start_date: str | None,
        requested_end_date: str | None,
        save: bool,
        calculate_technical: bool,
    ) -> dict[str, Any]:
        assert self.stock_repo is not None and self.price_repo is not None
        stock = self.stock_repo.get_by_code(normalized_code)
        if stock is None:
            return {
                "stock_id": None,
                "stock_name": None,
                "source": "kiwoom_rest",
                "existing_price_count_by_source": [],
                "unique_policy": "stock_not_found",
                "unique_indexes": [],
                "would_save_count": 0,
                "save_blocked_reason": f"STOCK_NOT_FOUND:{normalized_code}",
                "saved_count": 0,
                "skipped_count": 0,
                "technical_saved_count": 0,
            }

        unique_info = self.price_repo.get_unique_policy()
        source_summary = self.price_repo.list_source_summary_for_stock(stock.id)
        source = "kiwoom_rest"
        rows_to_save = [
            {
                "trade_date": row.get("trade_date"),
                "open_price": row.get("open_price"),
                "high_price": row.get("high_price"),
                "low_price": row.get("low_price"),
                "close_price": row.get("close_price"),
                "change_price": row.get("change_price"),
                "change_rate": row.get("change_rate"),
                "volume": row.get("volume"),
                "trading_value": row.get("trading_value"),
            }
            for row in mapped_items
            if row.get("trade_date")
        ]
        would_save_count = len(rows_to_save)
        save_blocked_reason = None
        saved_count = 0
        technical_saved_count = 0

        start = requested_start_date or (rows_to_save[0]["trade_date"] if rows_to_save else None)
        end = requested_end_date or (rows_to_save[-1]["trade_date"] if rows_to_save else None)
        if unique_info.get("policy") == "stock_id_trade_date" and start and end:
            cross_source_count = self.price_repo.count_existing_rows_in_window_excluding_source(
                stock_id=stock.id,
                start_date=start,
                end_date=end,
                source=source,
            )
            if cross_source_count > 0:
                save_blocked_reason = (
                    f"SAVE_BLOCKED_UNIQUE_POLICY:{unique_info.get('policy')}:"
                    f"conflict_rows={cross_source_count}"
                )

        if save and save_blocked_reason is None and rows_to_save:
            saved_count = self.price_repo.upsert_daily_rows(stock.id, source, rows_to_save)
            if calculate_technical and self.technical_indicator_service is not None:
                tech = self.technical_indicator_service.calculate_and_save_for_stock(stock.id)
                technical_saved_count = int(tech.get("saved_count") or 0)

        return {
            "stock_id": stock.id,
            "stock_name": stock.stock_name,
            "source": source,
            "existing_price_count_by_source": source_summary,
            "unique_policy": unique_info.get("policy"),
            "unique_indexes": unique_info.get("unique_indexes", []),
            "would_save_count": would_save_count,
            "save_blocked_reason": save_blocked_reason,
            "saved_count": saved_count if save else 0,
            "skipped_count": (would_save_count if save and save_blocked_reason is not None else 0),
            "technical_saved_count": technical_saved_count,
        }
