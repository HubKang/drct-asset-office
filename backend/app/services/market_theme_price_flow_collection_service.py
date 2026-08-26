from __future__ import annotations

import time
import uuid
from datetime import date, timedelta
from threading import Lock
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.clients.kiwoom import is_kiwoom_authentication_error, is_kiwoom_global_provider_error
from backend.app.core.config import now_kst
from backend.app.core.database import SessionLocal
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.stock_investor_flow_repository import StockInvestorFlowRepository
from backend.app.schemas.external_kiwoom_schema import (
    MarketThemeCollectionStageSummary,
    MarketThemePriceFlowFailureItem,
    MarketThemePriceFlowRefreshResponse,
    MarketThemeReturnRefreshRequest,
)
from backend.app.schemas.stock_investor_flow_schema import InvestorFlowCollectRequest
from backend.app.services.external_kiwoom_service import ExternalKiwoomService
from backend.app.services.stock_investor_flow_service import StockInvestorFlowService
from backend.app.services.stock_price_service import StockPriceService
from backend.app.services.technical_indicator_service import TechnicalIndicatorService


class MarketThemePriceFlowCollectionService:
    """Prepare shared price/flow data for active theme stocks, then refresh theme returns."""

    _run_lock = Lock()
    COLLECTOR_NAME = "market_theme_price_flow_refresh"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.run_repo = CollectionRunRepository(db)
        self.external_service = ExternalKiwoomService(db)
        self.price_service = StockPriceService(db)
        self.technical_service = TechnicalIndicatorService(db)
        self.flow_service = StockInvestorFlowService(db)
        self.flow_repo = StockInvestorFlowRepository(db)

    @staticmethod
    def _failure(stock: dict[str, object] | None, stage: str, message: str) -> MarketThemePriceFlowFailureItem:
        upper = (message or "").upper()
        if "WINERROR 10013" in upper or "OAUTH2/TOKEN" in upper or "CONNECTION" in upper:
            error_code = "KIWOOM_NETWORK_ERROR"
            user_message = "Kiwoom 서버 연결 또는 네트워크 권한을 확인해 주세요."
        elif "AUTH" in upper or "TOKEN" in upper:
            error_code = "KIWOOM_AUTH_ERROR"
            user_message = "Kiwoom 인증 토큰을 발급받지 못했습니다."
        elif "STOCK NOT FOUND" in upper:
            error_code = "STOCK_NOT_FOUND"
            user_message = "종목 정보를 찾을 수 없습니다."
        else:
            error_code = "COLLECTION_ERROR"
            user_message = "수집 중 오류가 발생했습니다."
        return MarketThemePriceFlowFailureItem(
            stock_id=int(stock["stock_id"]) if stock and stock.get("stock_id") is not None else None,
            stock_code=str(stock.get("stock_code") or "") if stock else None,
            stock_name=str(stock.get("stock_name") or "") if stock else None,
            stage=stage,
            message=(message or "unknown error")[:500],
            error_code=error_code,
            user_message=user_message,
            internal_summary=(message or "unknown error")[:500],
            retryable=error_code != "STOCK_NOT_FOUND",
        )

    @staticmethod
    def _deduplicate_stock_links(link_rows: list[dict[str, object]]) -> dict[int, dict[str, object]]:
        unique_stocks: dict[int, dict[str, object]] = {}
        for row in link_rows:
            stock_id = int(row["stock_id"])
            unique_stocks.setdefault(stock_id, {
                "stock_id": stock_id,
                "stock_code": row.get("stock_code"),
                "stock_name": row.get("stock_name"),
                "market": row.get("market"),
            })
        return unique_stocks

    @staticmethod
    def _stage_summary(results: list[dict[str, object]], *, inserted_key: str, updated_key: str) -> MarketThemeCollectionStageSummary:
        statuses = [str(item.get("status") or "FAILED") for item in results]
        return MarketThemeCollectionStageSummary(
            target_count=len(results),
            attempted_count=sum(1 for item in results if bool(item.get("attempted"))),
            success_count=statuses.count("SUCCESS"),
            up_to_date_count=statuses.count("UP_TO_DATE"),
            no_data_count=statuses.count("NO_DATA"),
            skipped_count=statuses.count("SKIPPED"),
            failed_count=statuses.count("FAILED"),
            inserted_rows=sum(int(item.get(inserted_key) or 0) for item in results),
            updated_rows=sum(int(item.get(updated_key) or 0) for item in results),
        )

    @staticmethod
    def _raise_for_common_provider_failure(price_results: list[dict[str, object]]) -> None:
        failure = next(
            (item for item in price_results if item.get("skip_reason") == "COMMON_PROVIDER_ERROR"),
            None,
        )
        if failure is None:
            return
        provider_error = str(failure.get("error_message") or "Kiwoom provider error")
        MarketThemePriceFlowCollectionService._raise_for_common_provider_error(provider_error)

    @staticmethod
    def _raise_for_common_provider_error(provider_error: BaseException | str) -> None:
        if not is_kiwoom_global_provider_error(provider_error):
            return
        provider_error_text = str(provider_error or "Kiwoom provider error")
        is_auth_error = is_kiwoom_authentication_error(provider_error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "KIWOOM_AUTH_ERROR" if is_auth_error else "KIWOOM_PROVIDER_UNAVAILABLE",
                "message": (
                    "Kiwoom API 인증 실패를 감지하여 첫 오류 이후 전체 갱신 작업을 종료했습니다."
                    if is_auth_error
                    else "Kiwoom 공통 장애를 감지하여 첫 오류 이후 전체 갱신 작업을 종료했습니다."
                ),
                "provider_error": provider_error_text[:500],
            },
        )

    @staticmethod
    def _select_collection_targets(
        unique_stocks: dict[int, dict[str, object]], payload: MarketThemeReturnRefreshRequest
    ) -> dict[int, dict[str, object]]:
        if payload.mode != "PILOT":
            return unique_stocks
        requested_ids = set(payload.pilot_stock_ids)
        requested_codes = {str(code).strip().zfill(6) for code in payload.pilot_stock_codes if str(code).strip()}
        if not requested_ids and not requested_codes and payload.max_stocks is None:
            raise HTTPException(
                status_code=422,
                detail="PILOT 모드에는 pilot_stock_ids, pilot_stock_codes 또는 max_stocks가 필요합니다.",
            )
        available_ids = set(unique_stocks)
        available_codes = {
            str(stock.get("stock_code") or "").strip().zfill(6)
            for stock in unique_stocks.values()
            if stock.get("stock_code")
        }
        if not requested_ids.issubset(available_ids) or not requested_codes.issubset(available_codes):
            raise HTTPException(
                status_code=422,
                detail="요청한 pilot 종목 중 현재 활성 테마에 연결되지 않은 종목이 있습니다.",
            )
        selected = {
            stock_id: stock
            for stock_id, stock in unique_stocks.items()
            if (not requested_ids and not requested_codes)
            or stock_id in requested_ids
            or str(stock.get("stock_code") or "").strip().zfill(6) in requested_codes
        }
        limit = payload.max_stocks or len(selected)
        return dict(list(selected.items())[:limit])

    @staticmethod
    def _resolve_flow_start(
        *,
        end_date: date,
        initial_start: date,
        investor_latest: str | None,
        program_latest: str | None,
        overlap_days: int = 7,
    ) -> date:
        if not investor_latest or not program_latest:
            return initial_start
        latest = min(date.fromisoformat(investor_latest), date.fromisoformat(program_latest))
        return min(latest - timedelta(days=max(0, overlap_days)), end_date)

    def _probe_theme_flow_availability(
        self,
        *,
        stock: dict[str, object],
        expected_trade_date: date,
    ) -> dict[str, object]:
        """Check one established stock before starting the full theme flow sweep.

        The probe is transient and uses the same three requests as the lightweight
        theme profile. Ambiguous or failed probes never suppress normal collection.
        """
        result = self.flow_service.kiwoom_provider.get_investor_flows(
            stock_code=str(stock.get("stock_code") or ""),
            start_date=(expected_trade_date - timedelta(days=7)).isoformat(),
            end_date=expected_trade_date.isoformat(),
            max_rows=1,
            include_trade_breakdown=False,
            include_foreign_holding=False,
        )
        errors = dict(result.get("collection_errors") or {})
        investor_dates: list[str] = []
        program_dates: list[str] = []
        for row in result.get("items") or []:
            if not isinstance(row, dict):
                continue
            flow_date = str(row.get("flow_date") or "")
            if not flow_date:
                continue
            if any(row.get(key) is not None for key in (
                "individual_net_qty", "individual_net_amount",
                "foreign_net_qty", "foreign_net_amount",
                "institution_net_qty", "institution_net_amount",
            )):
                investor_dates.append(flow_date)
            if row.get("program_net_qty") is not None or row.get("program_net_amount") is not None:
                program_dates.append(flow_date)
        investor_latest = max(investor_dates, default=None)
        program_latest = max(program_dates, default=None)
        should_skip = bool(
            not errors
            and investor_latest
            and program_latest
            and date.fromisoformat(investor_latest) < expected_trade_date
            and date.fromisoformat(program_latest) < expected_trade_date
        )
        return {
            "should_skip": should_skip,
            "investor_latest_date": investor_latest,
            "program_latest_date": program_latest,
            "errors": errors,
        }

    def refresh(
        self,
        payload: MarketThemeReturnRefreshRequest,
        progress_callback: Callable[[str, int, int, str], None] | None = None,
    ) -> MarketThemePriceFlowRefreshResponse:
        if not self._run_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="테마 등락률&수급 갱신 작업이 이미 실행 중입니다.",
            )

        started = time.perf_counter()
        run = None
        try:
            run = self.run_repo.create_running(self.COLLECTOR_NAME, "active_theme_stocks")
            refreshed_at = now_kst()
            end_date = date.today()
            themes = self.external_service._list_return_refresh_themes(payload)
            theme_ids = [int(theme["theme_id"]) for theme in themes]
            link_rows = self.external_service._list_active_theme_return_stock_links(theme_ids)
            unique_stocks = self._deduplicate_stock_links(link_rows)
            unique_stocks = self._select_collection_targets(unique_stocks, payload)
            stock_ids = list(unique_stocks)
            failures: list[MarketThemePriceFlowFailureItem] = []
            target_results: dict[int, dict[str, object]] = {
                stock_id: {
                    "stock_id": stock_id,
                    "stock_code": str(stock.get("stock_code") or ""),
                    "stock_name": str(stock.get("stock_name") or ""),
                    "market": str(stock.get("market") or "") or None,
                    "provider": "kiwoom_rest",
                }
                for stock_id, stock in unique_stocks.items()
            }
            if progress_callback:
                progress_callback("TARGETS", len(stock_ids), len(stock_ids), "활성 테마 연결 고유 종목을 확정했습니다.")

            price_results = self.price_service.refresh_theme_stock_price_ranges(
                stock_ids=stock_ids,
                end_date=end_date,
                initial_lookback_months=6,
                overlap_days=7,
                source="kiwoom_rest",
                refresh_current_trade_date=True,
                progress_callback=(
                    (lambda completed, total: progress_callback("PRICE", completed, total, "가격을 수집하고 있습니다."))
                    if progress_callback
                    else None
                ),
            )
            self._raise_for_common_provider_failure(price_results)
            price_stage = self._stage_summary(
                price_results, inserted_key="inserted_count", updated_key="updated_count"
            )
            price_success = price_stage.success_count
            price_failed = price_stage.failed_count
            price_inserted = sum(int(item.get("inserted_count") or 0) for item in price_results)
            price_updated = sum(int(item.get("updated_count") or 0) for item in price_results)
            for item in price_results:
                stock_id = int(item["stock_id"])
                target_results[stock_id].update({
                    "collect_start_date": item.get("collect_start_date"),
                    "collect_end_date": item.get("collect_end_date"),
                    "price_status": item.get("status"),
                    "price_response_rows": int(item.get("collected_count") or 0),
                    "price_inserted_rows": int(item.get("inserted_count") or 0),
                    "price_updated_rows": int(item.get("updated_count") or 0),
                    "latest_price_date": item.get("latest_trade_date"),
                    "skip_reason": item.get("skip_reason"),
                })
                if item["status"] != "SUCCESS":
                    if item["status"] == "FAILED":
                        failure = self._failure(item, "PRICE", str(item.get("error_message") or "price collection failed"))
                        failures.append(failure)
                        target_results[stock_id].update({
                            "error_code": failure.error_code,
                            "error_message": failure.user_message,
                        })

            technical_results: list[dict[str, object]] = []
            technical_saved = 0
            for technical_index, item in enumerate(price_results, start=1):
                stock_id = int(item["stock_id"])
                if item["status"] != "SUCCESS" or (
                    int(item.get("inserted_count") or 0) == 0 and int(item.get("updated_count") or 0) == 0
                ):
                    reason = "PRICE_FAILED" if item["status"] == "FAILED" else "PRICE_NOT_CHANGED"
                    technical_results.append({"stock_id": stock_id, "status": "SKIPPED", "attempted": False})
                    target_results[stock_id].update({"technical_status": "SKIPPED", "skip_reason": reason})
                    if progress_callback:
                        progress_callback(
                            "TECHNICAL", technical_index, len(price_results), "가격 변경 종목의 기술지표를 계산하고 있습니다."
                        )
                    continue
                try:
                    technical_before_count = self.technical_service.repo.count_by_stock(stock_id)
                    result = self.technical_service.calculate_and_save_for_stock(stock_id)
                    saved_count = int(result.get("saved_count") or 0)
                    technical_after_count = self.technical_service.repo.count_by_stock(stock_id)
                    technical_inserted = max(0, technical_after_count - technical_before_count)
                    technical_updated = max(0, saved_count - technical_inserted)
                    technical_saved += saved_count
                    technical_results.append({
                        "stock_id": stock_id, "status": "SUCCESS", "attempted": True,
                        "inserted_count": technical_inserted, "updated_count": technical_updated,
                    })
                    target_results[stock_id]["technical_status"] = "SUCCESS"
                except Exception as exc:  # noqa: BLE001
                    self.db.rollback()
                    technical_results.append({"stock_id": stock_id, "status": "FAILED", "attempted": True})
                    failure = self._failure(unique_stocks.get(stock_id), "TECHNICAL", str(exc))
                    failures.append(failure)
                    target_results[stock_id].update({
                        "technical_status": "FAILED", "error_code": failure.error_code,
                        "error_message": failure.user_message,
                    })
                if progress_callback:
                    progress_callback(
                        "TECHNICAL", technical_index, len(price_results), "가격 변경 종목의 기술지표를 계산하고 있습니다."
                    )
            technical_stage = self._stage_summary(
                technical_results, inserted_key="inserted_count", updated_key="updated_count"
            )
            technical_success = technical_stage.success_count
            technical_failed = technical_stage.failed_count

            initial_flow_start = StockPriceService._subtract_calendar_months(end_date, 6)
            latest_before = self.flow_repo.get_latest_subject_dates(stock_ids)
            expected_trade_date = StockPriceService._latest_expected_weekday(end_date)
            force_intraday_refresh = end_date == expected_trade_date
            investor_results: list[dict[str, object]] = []
            program_results: list[dict[str, object]] = []
            flow_inserted = 0
            flow_updated = 0
            pending_probe_candidates = [] if force_intraday_refresh else [
                stock_id
                for stock_id in stock_ids
                if latest_before.get(stock_id, {}).get("investor_latest_date")
                and latest_before.get(stock_id, {}).get("program_latest_date")
                and not (
                    date.fromisoformat(str(latest_before[stock_id]["investor_latest_date"])) >= expected_trade_date
                    and date.fromisoformat(str(latest_before[stock_id]["program_latest_date"])) >= expected_trade_date
                )
            ]
            flow_probe: dict[str, object] = {"should_skip": False}
            if pending_probe_candidates:
                probe_stock_id = max(
                    pending_probe_candidates,
                    key=lambda value: min(
                        str(latest_before[value]["investor_latest_date"]),
                        str(latest_before[value]["program_latest_date"]),
                    ),
                )
                try:
                    flow_probe = self._probe_theme_flow_availability(
                        stock=unique_stocks[probe_stock_id],
                        expected_trade_date=expected_trade_date,
                    )
                except Exception as exc:  # noqa: BLE001
                    self._raise_for_common_provider_error(exc)
                    flow_probe = {"should_skip": False}
                for probe_error in dict(flow_probe.get("errors") or {}).values():
                    self._raise_for_common_provider_error(str(probe_error))
            for flow_index, stock_id in enumerate(stock_ids, start=1):
                latest = latest_before.get(stock_id, {})
                investor_latest = latest.get("investor_latest_date")
                program_latest = latest.get("program_latest_date")
                investor_current = bool(
                    investor_latest and date.fromisoformat(str(investor_latest)) >= expected_trade_date
                )
                program_current = bool(
                    program_latest and date.fromisoformat(str(program_latest)) >= expected_trade_date
                )
                start_date = (
                    expected_trade_date
                    if force_intraday_refresh and investor_current and program_current
                    else self._resolve_flow_start(
                        end_date=end_date,
                        initial_start=initial_flow_start,
                        investor_latest=str(investor_latest) if investor_latest else None,
                        program_latest=str(program_latest) if program_latest else None,
                    )
                )
                target_results[stock_id].update({
                    "latest_investor_date": investor_latest,
                    "latest_program_date": program_latest,
                    "collect_start_date": target_results[stock_id].get("collect_start_date") or start_date.isoformat(),
                    "collect_end_date": end_date.isoformat(),
                })
                if investor_current and program_current and not force_intraday_refresh:
                    investor_results.append({"stock_id": stock_id, "status": "UP_TO_DATE", "attempted": False})
                    program_results.append({"stock_id": stock_id, "status": "UP_TO_DATE", "attempted": False})
                    target_results[stock_id].update({
                        "investor_status": "UP_TO_DATE", "program_status": "UP_TO_DATE",
                        "skip_reason": "LATEST_EXPECTED_TRADE_DATE_PRESENT",
                    })
                    if progress_callback:
                        progress_callback(
                            "FLOW", flow_index, len(stock_ids), "개인·외국인·기관·프로그램 수급을 확인하고 있습니다."
                        )
                    continue
                if bool(flow_probe.get("should_skip")):
                    investor_status = "UP_TO_DATE" if investor_current else "SKIPPED"
                    program_status = "UP_TO_DATE" if program_current else "SKIPPED"
                    investor_results.append({"stock_id": stock_id, "status": investor_status, "attempted": False})
                    program_results.append({"stock_id": stock_id, "status": program_status, "attempted": False})
                    target_results[stock_id].update({
                        "investor_status": investor_status,
                        "program_status": program_status,
                        "skip_reason": "PROVIDER_EXPECTED_TRADE_DATE_NOT_AVAILABLE",
                    })
                    if progress_callback:
                        progress_callback(
                            "FLOW",
                            flow_index,
                            len(stock_ids),
                            "Provider latest flow date is not available yet.",
                        )
                    continue
                before_dates = self.flow_repo.get_dates_in_window(
                    stock_id, start_date.isoformat(), end_date.isoformat()
                )
                try:
                    response = self.flow_service.collect(InvestorFlowCollectRequest(
                        stock_ids=[stock_id],
                        period="CUSTOM",
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        source="kiwoom",
                        prefer_real_source=True,
                        fallback_to_derived=False,
                        include_trade_breakdown=False,
                        include_foreign_holding=False,
                    ))
                    item = response.items[0]
                    self._raise_for_common_provider_error(item.message or "")
                    after_dates = self.flow_repo.get_dates_in_window(
                        stock_id, start_date.isoformat(), end_date.isoformat()
                    )
                    inserted = len(after_dates - before_dates)
                    updated = max(0, int(item.saved_count or 0) - inserted)
                    flow_inserted += inserted
                    flow_updated += updated
                    investor_subjects = (item.individual_status, item.foreign_status, item.institution_status)
                    if investor_current and not force_intraday_refresh:
                        investor_status = "UP_TO_DATE"
                    elif all(value == "SUCCESS" for value in investor_subjects):
                        investor_status = "SUCCESS"
                    elif all(value == "NO_DATA" for value in investor_subjects):
                        investor_status = "NO_DATA"
                    else:
                        investor_status = "FAILED"
                    if program_current and not force_intraday_refresh:
                        program_status = "UP_TO_DATE"
                    elif item.program_status == "SUCCESS":
                        program_status = "SUCCESS"
                    elif item.program_status == "NO_DATA":
                        program_status = "NO_DATA"
                    else:
                        program_status = "FAILED"
                    investor_results.append({
                        "stock_id": stock_id, "status": investor_status,
                        "attempted": force_intraday_refresh or not investor_current,
                        "inserted_count": inserted, "updated_count": updated,
                    })
                    program_results.append({
                        "stock_id": stock_id, "status": program_status,
                        "attempted": force_intraday_refresh or not program_current,
                        "inserted_count": inserted, "updated_count": updated,
                    })
                    target_results[stock_id].update({
                        "investor_status": investor_status,
                        "program_status": program_status,
                        "flow_response_rows": int(item.collected_days or 0),
                        "flow_inserted_rows": inserted,
                        "flow_updated_rows": updated,
                    })
                    if investor_status == "FAILED":
                        failure = self._failure(unique_stocks.get(stock_id), "INVESTOR_FLOW", item.message or "investor flow incomplete")
                        failures.append(failure)
                        target_results[stock_id].update({"error_code": failure.error_code, "error_message": failure.user_message})
                    if program_status == "FAILED":
                        failure = self._failure(unique_stocks.get(stock_id), "PROGRAM_FLOW", item.message or "program flow incomplete")
                        failures.append(failure)
                        target_results[stock_id].update({"error_code": failure.error_code, "error_message": failure.user_message})
                except HTTPException:
                    raise
                except Exception as exc:  # noqa: BLE001
                    self.db.rollback()
                    self._raise_for_common_provider_error(exc)
                    investor_results.append({"stock_id": stock_id, "status": "FAILED", "attempted": True})
                    program_results.append({"stock_id": stock_id, "status": "FAILED", "attempted": True})
                    failure = self._failure(unique_stocks.get(stock_id), "INVESTOR_FLOW", str(exc))
                    failures.append(failure)
                    target_results[stock_id].update({
                        "investor_status": "FAILED", "program_status": "FAILED",
                        "error_code": failure.error_code, "error_message": failure.user_message,
                    })
                if progress_callback:
                    progress_callback(
                        "FLOW", flow_index, len(stock_ids), "개인·외국인·기관·프로그램 수급을 수집하고 있습니다."
                    )

            investor_stage = self._stage_summary(
                investor_results, inserted_key="inserted_count", updated_key="updated_count"
            )
            program_stage = self._stage_summary(
                program_results, inserted_key="inserted_count", updated_key="updated_count"
            )
            investor_success = investor_stage.success_count
            investor_failed = investor_stage.failed_count
            program_success = program_stage.success_count
            program_failed = program_stage.failed_count

            theme_error: str | None = None
            theme_results: list[dict[str, object]] = []
            if end_date.weekday() >= 5:
                theme_payload = {
                    "success": True,
                    "return_date": expected_trade_date.isoformat(),
                    "refreshed_at": refreshed_at,
                    "theme_count": len(themes),
                    "stock_count": len(link_rows),
                    "success_stock_count": 0,
                    "failed_stock_count": 0,
                    "inserted_count": 0,
                    "updated_count": 0,
                    "theme_stock_link_count": len(link_rows),
                    "unique_stock_count": len(stock_ids),
                    "items": [],
                }
                theme_results = [
                    {"status": "SKIPPED", "attempted": False, "inserted_count": 0, "updated_count": 0}
                    for _ in themes
                ]
                if progress_callback:
                    progress_callback("THEME_RETURN", len(themes), len(themes), "비거래일이므로 최근 거래일 데이터를 유지합니다.")
            else:
                try:
                    if progress_callback:
                        progress_callback("THEME_RETURN", 0, len(themes), "테마등락률을 집계하고 있습니다.")
                    theme_result = self.external_service.refresh_market_theme_returns(
                        payload,
                        use_saved_prices=True,
                        progress_callback=(
                            (lambda completed, total: progress_callback(
                                "THEME_RETURN",
                                completed,
                                total,
                                "테마등락률을 집계하고 있습니다.",
                            ))
                            if progress_callback
                            else None
                        ),
                    )
                    theme_payload = theme_result.model_dump()
                    for item in theme_payload.get("items") or []:
                        action = str(item.get("save_action") or "skipped")
                        theme_results.append({
                            "status": "SUCCESS" if action in {"inserted", "updated"} else "NO_DATA",
                            "attempted": True,
                            "inserted_count": int(action == "inserted"),
                            "updated_count": int(action == "updated"),
                        })
                    if progress_callback:
                        progress_callback("THEME_RETURN", len(themes), len(themes), "테마등락률 집계를 완료했습니다.")
                except Exception as exc:  # noqa: BLE001
                    self.db.rollback()
                    theme_error = str(exc)
                    failures.append(self._failure(None, "THEME_RETURN", theme_error))
                    theme_payload = {
                        "success": False, "return_date": end_date.isoformat(), "refreshed_at": refreshed_at,
                        "theme_count": len(themes), "stock_count": len(link_rows), "success_stock_count": 0,
                        "failed_stock_count": len(link_rows), "inserted_count": 0, "updated_count": 0,
                        "theme_stock_link_count": len(link_rows), "unique_stock_count": len(stock_ids), "items": [],
                    }
                    theme_results = [
                        {"status": "FAILED", "attempted": True, "inserted_count": 0, "updated_count": 0}
                        for _ in themes
                    ]
            theme_return_stage = self._stage_summary(
                theme_results, inserted_key="inserted_count", updated_key="updated_count"
            )

            latest_after = self.flow_repo.get_latest_subject_dates(stock_ids)
            latest_investor = max(
                (str(row["investor_latest_date"]) for row in latest_after.values() if row.get("investor_latest_date")),
                default=None,
            )
            latest_program = max(
                (str(row["program_latest_date"]) for row in latest_after.values() if row.get("program_latest_date")),
                default=None,
            )
            latest_price = max(
                (str(item["latest_trade_date"]) for item in price_results if item.get("latest_trade_date")),
                default=None,
            )
            failed_stage_count = price_failed + technical_failed + investor_failed + program_failed + int(theme_error is not None)
            common_failure = bool(stock_ids) and all(
                stage.failed_count == len(stock_ids) for stage in (price_stage, investor_stage, program_stage)
            )
            job_status = "COMPLETED" if failed_stage_count == 0 else "FAILED" if common_failure else "PARTIAL"
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            message = (
                f"테마 등락률&수급 갱신 {'완료' if job_status == 'COMPLETED' else '실패' if job_status == 'FAILED' else '부분 완료'}\n"
                f"연결 종목 {len(link_rows)}건 · 고유 종목 {len(stock_ids)}개 · "
                f"가격 성공 {price_stage.success_count}·최신 {price_stage.up_to_date_count}·없음 {price_stage.no_data_count}·실패 {price_stage.failed_count} · "
                f"기술지표 성공 {technical_stage.success_count}·생략 {technical_stage.skipped_count}·실패 {technical_stage.failed_count} · "
                f"투자자 성공 {investor_stage.success_count}·최신 {investor_stage.up_to_date_count}·없음 {investor_stage.no_data_count}·실패 {investor_stage.failed_count} · "
                f"프로그램 성공 {program_stage.success_count}·최신 {program_stage.up_to_date_count}·없음 {program_stage.no_data_count}·실패 {program_stage.failed_count} · "
                f"테마등락률 성공 {theme_return_stage.success_count}·생략 {theme_return_stage.skipped_count}·실패 {theme_return_stage.failed_count}"
            )
            run_message = (
                f"status={job_status} links={len(link_rows)} unique={len(stock_ids)} "
                f"price=s{price_stage.success_count},u{price_stage.up_to_date_count},n{price_stage.no_data_count},f{price_stage.failed_count} "
                f"technical=s{technical_stage.success_count},k{technical_stage.skipped_count},f{technical_stage.failed_count} "
                f"investor=s{investor_stage.success_count},u{investor_stage.up_to_date_count},n{investor_stage.no_data_count},f{investor_stage.failed_count} "
                f"program=s{program_stage.success_count},u{program_stage.up_to_date_count},n{program_stage.no_data_count},f{program_stage.failed_count} "
                f"theme=s{theme_return_stage.success_count},k{theme_return_stage.skipped_count},f{theme_return_stage.failed_count} "
                f"elapsed_ms={elapsed_ms}"
            )
            if job_status == "COMPLETED":
                self.run_repo.mark_success(run, run_message)
            elif job_status == "PARTIAL":
                self.run_repo.mark_partial(run, run_message)
            else:
                self.run_repo.mark_failed(run, run_message)

            theme_payload.update({
                "success": job_status != "FAILED",
                "message": message,
                "run_id": run.id,
                "job_status": job_status,
                "price_success_count": price_success,
                "price_failed_count": price_failed,
                "price_inserted_count": price_inserted,
                "price_updated_count": price_updated,
                "technical_success_count": technical_success,
                "technical_failed_count": technical_failed,
                "technical_saved_count": technical_saved,
                "investor_success_count": investor_success,
                "investor_failed_count": investor_failed,
                "program_success_count": program_success,
                "program_failed_count": program_failed,
                "flow_inserted_count": flow_inserted,
                "flow_updated_count": flow_updated,
                "latest_price_date": latest_price,
                "latest_investor_flow_date": latest_investor,
                "latest_program_flow_date": latest_program,
                "unique_stock_count": len(stock_ids),
                "collection_mode": payload.mode,
                "processed_stock_codes": [str(stock.get("stock_code") or "") for stock in unique_stocks.values()],
                "price_stage": price_stage,
                "technical_stage": technical_stage,
                "investor_stage": investor_stage,
                "program_stage": program_stage,
                "theme_return_stage": theme_return_stage,
                "target_results": list(target_results.values()),
                "failure_items": failures,
                "total_ms": elapsed_ms,
            })
            return MarketThemePriceFlowRefreshResponse(**theme_payload)
        except HTTPException as exc:
            if run is not None:
                self.run_repo.mark_failed(run, f"http_error={str(exc.detail)[:800]}")
            raise
        except Exception as exc:
            self.db.rollback()
            if run is not None:
                self.run_repo.mark_failed(run, f"fatal_error={str(exc)[:800]}")
            raise
        finally:
            self._run_lock.release()


class MarketThemePriceFlowJobManager:
    """Small in-process job registry; progress detail is transient and never stored in DB."""

    _lock = Lock()
    _jobs: dict[str, dict[str, Any]] = {}
    _STAGE_LABELS = {
        "PENDING": "작업 준비",
        "TARGETS": "대상 종목 확정",
        "PRICE": "가격 수집",
        "TECHNICAL": "기술지표 계산",
        "FLOW": "투자자·프로그램 수급 수집",
        "THEME_RETURN": "테마등락률 집계",
        "COMPLETED": "작업 완료",
        "FAILED": "작업 실패",
    }

    @classmethod
    def start(cls, payload: MarketThemeReturnRefreshRequest) -> str:
        with cls._lock:
            if any(job["status"] in {"PENDING", "RUNNING"} for job in cls._jobs.values()):
                running_job = next(job for job in cls._jobs.values() if job["status"] in {"PENDING", "RUNNING"})
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "MARKET_THEME_FLOW_JOB_ALREADY_RUNNING",
                        "message": "이미 테마 가격·수급 갱신 작업이 실행 중입니다.",
                        "job_id": running_job["job_id"],
                    },
                )
            completed_ids = [job_id for job_id, job in cls._jobs.items() if job["status"] not in {"PENDING", "RUNNING"}]
            for job_id in completed_ids[:-20]:
                cls._jobs.pop(job_id, None)
            job_id = uuid.uuid4().hex
            requested_at = now_kst()
            cls._jobs[job_id] = {
                "job_id": job_id,
                "status": "PENDING",
                "stage": "PENDING",
                "completed_count": 0,
                "total_count": 0,
                "message": "작업 시작을 기다리고 있습니다.",
                "requested_at": requested_at,
                "started_at": None,
                "finished_at": None,
                "error": None,
                "result": None,
                "payload": payload.model_dump(),
            }
            return job_id

    @classmethod
    def run(cls, job_id: str) -> None:
        with cls._lock:
            job = cls._jobs.get(job_id)
            if not job:
                return
            job["status"] = "RUNNING"
            job["started_at"] = now_kst()
            payload = MarketThemeReturnRefreshRequest(**job.pop("payload"))

        def progress(stage: str, completed: int, total: int, message: str) -> None:
            with cls._lock:
                current = cls._jobs.get(job_id)
                if current:
                    current.update({
                        "stage": stage,
                        "completed_count": completed,
                        "total_count": total,
                        "message": message,
                    })

        db = SessionLocal()
        try:
            result = MarketThemePriceFlowCollectionService(db).refresh(payload, progress_callback=progress)
            from backend.app.services.market_theme_flow_trend_service import invalidate_market_theme_flow_trend_cache
            invalidate_market_theme_flow_trend_cache()
            with cls._lock:
                cls._jobs[job_id].update({
                    "status": result.job_status,
                    "stage": "COMPLETED",
                    "completed_count": result.unique_stock_count,
                    "total_count": result.unique_stock_count,
                    "message": result.message,
                    "finished_at": now_kst(),
                    "result": result.model_dump(),
                })
        except Exception as exc:  # noqa: BLE001
            detail = getattr(exc, "detail", exc)
            error_message = str(detail.get("message") or detail) if isinstance(detail, dict) else str(detail)
            error_message = error_message[:1000]
            with cls._lock:
                if job_id in cls._jobs:
                    cls._jobs[job_id].update({
                        "status": "FAILED",
                        "stage": "FAILED",
                        "message": error_message,
                        "error": error_message,
                        "finished_at": now_kst(),
                    })
        finally:
            db.close()

    @classmethod
    def get(cls, job_id: str) -> dict[str, Any]:
        with cls._lock:
            job = cls._jobs.get(job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "MARKET_THEME_FLOW_JOB_NOT_FOUND",
                        "message": "가격·수급 갱신 작업을 찾을 수 없습니다. 서버가 재시작되었는지 확인해 주세요.",
                        "job_id": job_id,
                    },
                )
            result = job.get("result") or {}
            failures = result.get("failure_items") or []
            def stage_result(prefix: str, stage_key: str) -> dict[str, int]:
                if isinstance(result.get(stage_key), dict):
                    return dict(result[stage_key])
                return {
                    "target_count": int(result.get("unique_stock_count") or 0),
                    "attempted_count": int(result.get("unique_stock_count") or 0),
                    "success_count": int(result.get(f"{prefix}_success_count") or 0),
                    "up_to_date_count": 0,
                    "no_data_count": 0,
                    "skipped_count": 0,
                    "failed_count": int(result.get(f"{prefix}_failed_count") or 0),
                    "inserted_rows": int(result.get(f"{prefix}_inserted_count") or 0),
                    "updated_rows": int(result.get(f"{prefix}_updated_count") or 0),
                }
            stage = str(job["stage"])
            return {
                "job_id": job["job_id"],
                "status": job["status"],
                "stage": job["stage"],
                "completed_count": job["completed_count"],
                "total_count": job["total_count"],
                "current_stage": stage,
                "current_stage_label": cls._STAGE_LABELS.get(stage, stage),
                "completed_stock_count": job["completed_count"],
                "total_stock_count": job["total_count"],
                "failed_stock_count": len({item.get("stock_id") for item in failures if item.get("stock_id") is not None}),
                "price_result": stage_result("price", "price_stage"),
                "technical_indicator_result": stage_result("technical", "technical_stage"),
                "investor_flow_result": stage_result("investor", "investor_stage"),
                "program_flow_result": stage_result("program", "program_stage"),
                "theme_return_result": stage_result("theme_return", "theme_return_stage"),
                "requested_at": job["requested_at"],
                "started_at": job.get("started_at"),
                "finished_at": job.get("finished_at"),
                "error": job.get("error"),
                "failures": failures,
                "message": job.get("message"),
                "result": job.get("result"),
            }
