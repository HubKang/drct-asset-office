from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.providers.market_data.kiwoom_rest_investor_flow_provider import KiwoomInvestorFlowNotConfigured, KiwoomRestInvestorFlowProvider
from backend.app.repositories.stock_investor_flow_repository import StockInvestorFlowRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository
from backend.app.schemas.stock_investor_flow_schema import (
    InvestorFlowChartItem,
    InvestorFlowChartResponse,
    InvestorFlowCollectItem,
    InvestorFlowCollectRequest,
    InvestorFlowCollectResponse,
    InvestorFlowSummary,
)
from backend.app.utils.stock_code_utils import normalize_kr_stock_code


class StockInvestorFlowService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = StockInvestorFlowRepository(db)
        self.stock_repo = StockRepository(db)
        self.watchlist_repo = WatchlistRepository(db)
        self.kiwoom_provider = KiwoomRestInvestorFlowProvider()

    @staticmethod
    def _parse_date(value: str) -> date:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()

    def _resolve_window(self, payload: InvestorFlowCollectRequest) -> tuple[date, date, int]:
        today = date.today()
        period = (payload.period or "RECENT_7D").upper()
        if period == "CUSTOM":
            if not payload.start_date or not payload.end_date:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CUSTOM 기간은 start_date와 end_date가 필요합니다.")
            start = self._parse_date(payload.start_date)
            end = self._parse_date(payload.end_date)
            if start > end:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date는 end_date보다 늦을 수 없습니다.")
            return start, end, (end - start).days + 1
        days = 90 if period == "RECENT_90D" else 30 if period == "RECENT_30D" else 7
        return today - timedelta(days=days - 1), today, days

    def _resolve_targets(self, payload: InvestorFlowCollectRequest) -> list[tuple[int | None, Any]]:
        targets: list[tuple[int | None, Any]] = []
        seen_stock_ids: set[int] = set()
        for watchlist_id in payload.watchlist_ids:
            item = self.watchlist_repo.get_by_id(watchlist_id)
            if not item:
                continue
            stock = self.stock_repo.get_by_id(item.stock_id)
            if stock and stock.id not in seen_stock_ids:
                targets.append((item.id, stock))
                seen_stock_ids.add(stock.id)
        for stock_id in payload.stock_ids:
            stock = self.stock_repo.get_by_id(stock_id)
            if stock and stock.id not in seen_stock_ids:
                targets.append((None, stock))
                seen_stock_ids.add(stock.id)
        if not targets:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="수집할 관심종목 또는 종목이 없습니다.")
        return targets

    def _price_rows(self, stock_id: int, start: date, end: date) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT trade_date, close_price, change_rate, volume, trading_value
                FROM stock_daily_prices
                WHERE stock_id=:stock_id
                  AND trade_date BETWEEN :start_date AND :end_date
                ORDER BY trade_date ASC
                """
            ),
            {"stock_id": stock_id, "start_date": start.isoformat(), "end_date": end.isoformat()},
        ).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    def _build_flow_from_price(self, stock: Any, row: dict[str, Any], source: str, now: str) -> dict[str, Any]:
        volume = self._to_int(row.get("volume")) or 0
        close_price = float(row.get("close_price") or 0)
        change_rate = float(row.get("change_rate") or 0)
        trading_value = self._to_int(row.get("trading_value")) or int(volume * close_price)
        direction = 1 if change_rate >= 0 else -1
        seed = sum(ord(ch) for ch in str(stock.stock_code)) % 17
        foreign_net_qty = direction * max(1, int(volume * (0.035 + seed / 1000)))
        institution_net_qty = (1 if change_rate >= 0.4 else -1 if change_rate <= -0.4 else direction) * max(1, int(volume * (0.025 + seed / 1400)))
        program_net_qty = (1 if change_rate >= 0 else -1) * max(1, int(volume * (0.018 + seed / 1800)))

        def split_qty(net_qty: int) -> tuple[int, int]:
            base = max(abs(net_qty), int(volume * 0.03))
            if net_qty >= 0:
                return base + net_qty, base
            return base, base + abs(net_qty)

        foreign_buy, foreign_sell = split_qty(foreign_net_qty)
        institution_buy, institution_sell = split_qty(institution_net_qty)
        program_buy, program_sell = split_qty(program_net_qty)

        def amount(qty: int | None) -> int | None:
            return None if qty is None else int(qty * close_price)

        return {
            "stock_id": stock.id,
            "stock_code": normalize_kr_stock_code(stock.stock_code),
            "flow_date": str(row.get("trade_date")),
            "foreign_buy_qty": foreign_buy,
            "foreign_sell_qty": foreign_sell,
            "foreign_net_qty": foreign_net_qty,
            "foreign_buy_amount": amount(foreign_buy),
            "foreign_sell_amount": amount(foreign_sell),
            "foreign_net_amount": amount(foreign_net_qty),
            "foreign_holding_qty": None,
            "foreign_holding_ratio": None,
            "institution_buy_qty": institution_buy,
            "institution_sell_qty": institution_sell,
            "institution_net_qty": institution_net_qty,
            "institution_buy_amount": amount(institution_buy),
            "institution_sell_amount": amount(institution_sell),
            "institution_net_amount": amount(institution_net_qty),
            "financial_investment_net_qty": None,
            "insurance_net_qty": None,
            "investment_trust_net_qty": None,
            "bank_net_qty": None,
            "other_finance_net_qty": None,
            "pension_fund_net_qty": None,
            "private_fund_net_qty": None,
            "other_corporation_net_qty": None,
            "program_buy_qty": program_buy,
            "program_sell_qty": program_sell,
            "program_net_qty": program_net_qty,
            "program_buy_amount": amount(program_buy),
            "program_sell_amount": amount(program_sell),
            "program_net_amount": amount(program_net_qty),
            "program_arbitrage_net_qty": None,
            "program_non_arbitrage_net_qty": None,
            "source": source,
            "data_source_type": "DERIVED_PRICE_FLOW",
            "source_method": "derived_price_flow",
            "is_real_investor_flow": 0,
            "collection_status": "DERIVED",
            "raw_json": None,
            "created_at": now,
            "updated_at": now,
        }

    def _row_has_real_payload(self, row: dict[str, Any]) -> bool:
        return any(row.get(key) is not None for key in (
            "foreign_net_qty", "foreign_net_amount",
            "institution_net_qty", "institution_net_amount", "program_net_qty", "program_net_amount",
        ))

    @staticmethod
    def _collection_status(row: dict[str, Any]) -> str:
        subject_count = sum(
            1
            for keys in (
                ("foreign_net_qty", "foreign_net_amount"),
                ("institution_net_qty", "institution_net_amount"),
                ("program_net_qty", "program_net_amount"),
            )
            if any(row.get(key) is not None for key in keys)
        )
        if subject_count >= 3:
            return "SUCCESS"
        if subject_count > 0:
            return "PARTIAL"
        return "NO_DATA"

    def _build_flow_from_kiwoom(self, stock: Any, row: dict[str, Any], now: str, meta: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload.update({
            "stock_id": stock.id,
            "stock_code": normalize_kr_stock_code(stock.stock_code),
            "source": "kiwoom",
            "data_source_type": "KIWOOM_REAL",
            "source_method": "kiwoom_rest_multi_investor_flow",
            "is_real_investor_flow": 1,
            "collection_status": self._collection_status(payload),
            "raw_json": None,
            "created_at": now,
            "updated_at": now,
        })
        return payload

    def _collect_kiwoom_real(self, stock: Any, start: date, end: date, requested_days: int, period: str, now: str) -> tuple[int, str, str, str, str, str]:
        result = self.kiwoom_provider.get_investor_flows(
            stock_code=normalize_kr_stock_code(stock.stock_code),
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            max_rows=max(1, min(requested_days, 120)),
        )
        saved = 0
        meta = {}
        foreign_status = "NOT_COLLECTED"
        institution_status = "NOT_COLLECTED"
        program_status = "NOT_COLLECTED"
        foreign_holding_status = "NOT_COLLECTED"
        raw_items = [row for row in (result.get("items") or []) if isinstance(row, dict)]
        if (period or "").upper() == "CUSTOM":
            items = [row for row in raw_items if start.isoformat() <= str(row.get("flow_date") or "") <= end.isoformat()]
        else:
            items = raw_items[-requested_days:]
        for row in items:
            has_flow_payload = self._row_has_real_payload(row)
            has_holding_payload = row.get("foreign_holding_qty") is not None or row.get("foreign_holding_ratio") is not None
            if has_flow_payload:
                self.repo.upsert_flow(self._build_flow_from_kiwoom(stock, row, now, meta))
                saved += 1
            elif has_holding_payload:
                self.repo.upsert_foreign_holding({
                    "stock_id": stock.id,
                    "stock_code": normalize_kr_stock_code(stock.stock_code),
                    "flow_date": row.get("flow_date"),
                    "foreign_holding_qty": row.get("foreign_holding_qty"),
                    "foreign_holding_ratio": row.get("foreign_holding_ratio"),
                    "created_at": now,
                    "updated_at": now,
                })
                saved += 1
            if row.get("foreign_net_qty") is not None or row.get("foreign_net_amount") is not None:
                foreign_status = "SUCCESS"
            if row.get("institution_net_qty") is not None or row.get("institution_net_amount") is not None:
                institution_status = "SUCCESS"
            if row.get("program_net_qty") is not None or row.get("program_net_amount") is not None:
                program_status = "SUCCESS"
            if has_holding_payload:
                foreign_holding_status = "SUCCESS"
        if not saved:
            raise RuntimeError("KIWOOM_REAL_EMPTY")
        return saved, foreign_status, institution_status, program_status, foreign_holding_status, "Kiwoom ka10059/ka90013/ka10008 investor flow saved"

    def _collect_derived(self, stock: Any, start: date, end: date, now: str) -> int:
        rows = self._price_rows(stock.id, start, end)
        saved = 0
        for row in rows:
            self.repo.upsert_flow(self._build_flow_from_price(stock, row, "derived_price_flow", now))
            saved += 1
        return saved

    def collect(self, payload: InvestorFlowCollectRequest) -> InvestorFlowCollectResponse:
        start, end, requested_days = self._resolve_window(payload)
        targets = self._resolve_targets(payload)
        now = now_kst()
        items: list[InvestorFlowCollectItem] = []
        success_count = 0
        failed_count = 0
        saved_total = 0
        for watchlist_id, stock in targets:
            data_source_type = None
            foreign_status = "NOT_COLLECTED"
            institution_status = "NOT_COLLECTED"
            program_status = "NOT_COLLECTED"
            foreign_holding_status = "NOT_COLLECTED"
            try:
                saved = 0
                message = ""
                real_error: str | None = None
                if payload.prefer_real_source:
                    try:
                        saved, foreign_status, institution_status, program_status, foreign_holding_status, message = self._collect_kiwoom_real(stock, start, end, requested_days, payload.period, now)
                        data_source_type = "KIWOOM_REAL"
                    except KiwoomInvestorFlowNotConfigured as exc:
                        real_error = f"Kiwoom investor flow API not configured: {exc}"
                    except Exception as exc:  # noqa: BLE001
                        real_error = f"Kiwoom investor flow failed: {exc}"
                if saved == 0 and payload.fallback_to_derived:
                    message = (real_error or "No Kiwoom real investor flow rows collected") + "; derived fallback is disabled for investor-flow collection"
                if saved:
                    success_count += 1
                    status_value = "SUCCESS" if data_source_type == "KIWOOM_REAL" else "DERIVED"
                else:
                    failed_count += 1
                    status_value = "ERROR"
                    message = real_error or "No investor flow rows collected"
                saved_total += saved
                items.append(
                    InvestorFlowCollectItem(
                        watchlist_id=watchlist_id,
                        stock_id=stock.id,
                        stock_code=stock.stock_code,
                        stock_name=stock.stock_name,
                        collected_days=saved,
                        saved_count=saved,
                        status=status_value,
                        data_source_type=data_source_type,
                        foreign_status=foreign_status,
                        institution_status=institution_status,
                        program_status=program_status,
                        foreign_holding_status=foreign_holding_status,
                        message=message,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                failed_count += 1
                items.append(
                    InvestorFlowCollectItem(
                        watchlist_id=watchlist_id,
                        stock_id=stock.id,
                        stock_code=stock.stock_code,
                        stock_name=stock.stock_name,
                        status="ERROR",
                        data_source_type=data_source_type,
                        foreign_status=foreign_status,
                        institution_status=institution_status,
                        program_status=program_status,
                        foreign_holding_status=foreign_holding_status,
                        message=str(exc),
                    )
                )
        self.repo.commit()
        status_value = "SUCCESS" if failed_count == 0 else "PARTIAL" if success_count else "ERROR"
        return InvestorFlowCollectResponse(
            status=status_value,
            requested_count=len(targets),
            success_count=success_count,
            failed_count=failed_count,
            saved_count=saved_total,
            items=items,
        )

    @staticmethod
    def _streak(values: list[int | None]) -> int:
        latest_values = [value for value in values if value is not None]
        if not latest_values:
            return 0
        sign = 1 if latest_values[-1] > 0 else -1 if latest_values[-1] < 0 else 0
        if sign == 0:
            return 0
        count = 0
        for value in reversed(latest_values):
            if (value > 0 and sign > 0) or (value < 0 and sign < 0):
                count += 1
            else:
                break
        return count * sign

    def summary_for_stock(self, stock_id: int, days: int = 20) -> InvestorFlowSummary:
        rows = self.repo.list_by_stock(stock_id, limit=max(days, 5), real_only=True, exclude_source_methods=["kiwoom_rest_ka10005"])
        selected_source_type = "KIWOOM_REAL" if rows else None
        last5 = rows[-5:]
        if not rows:
            return InvestorFlowSummary()

        def sum_optional(key: str) -> int | None:
            values = [self._to_int(row.get(key)) for row in last5]
            values = [value for value in values if value is not None]
            return sum(values) if values else None

        return InvestorFlowSummary(
            latest_date=str(rows[-1].get("flow_date")) if rows[-1].get("flow_date") else None,
            foreign_5d_net_qty=sum_optional("foreign_net_qty"),
            institution_5d_net_qty=sum_optional("institution_net_qty"),
            program_5d_net_qty=sum_optional("program_net_qty"),
            foreign_streak=self._streak([self._to_int(row.get("foreign_net_qty")) for row in rows]),
            institution_streak=self._streak([self._to_int(row.get("institution_net_qty")) for row in rows]),
            program_streak=self._streak([self._to_int(row.get("program_net_qty")) for row in rows]),
            selected_source_type=selected_source_type,
            is_real_investor_flow=selected_source_type == "KIWOOM_REAL",
        )

    def chart_for_watchlist(self, watchlist_id: int, days: int = 30) -> InvestorFlowChartResponse:
        watchlist = self.watchlist_repo.get_by_id(watchlist_id)
        if not watchlist:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist not found")
        stock = self.stock_repo.get_by_id(watchlist.stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
        limit = max(1, min(days, 120))
        rows = self.repo.list_by_stock(stock.id, limit=limit, real_only=True, exclude_source_methods=["kiwoom_rest_ka10005"])
        selected_source_type = "KIWOOM_REAL" if rows else None
        fallback_source_type = None
        items = [
            InvestorFlowChartItem(
                date=str(row.get("flow_date")),
                source=str(row.get("source")) if row.get("source") else None,
                data_source_type=str(row.get("data_source_type")) if row.get("data_source_type") else None,
                source_method=str(row.get("source_method")) if row.get("source_method") else None,
                is_real_investor_flow=bool(row.get("is_real_investor_flow")),
                collection_status=str(row.get("collection_status")) if row.get("collection_status") else None,
                foreign_net_qty=self._to_int(row.get("foreign_net_qty")),
                foreign_net_amount=self._to_int(row.get("foreign_net_amount")),
                foreign_holding_qty=self._to_int(row.get("foreign_holding_qty")),
                foreign_holding_ratio=float(row.get("foreign_holding_ratio")) if row.get("foreign_holding_ratio") is not None else None,
                institution_net_qty=self._to_int(row.get("institution_net_qty")),
                institution_net_amount=self._to_int(row.get("institution_net_amount")),
                program_net_qty=self._to_int(row.get("program_net_qty")),
                program_net_amount=self._to_int(row.get("program_net_amount")),
            )
            for row in rows
        ]
        stored_source_methods = sorted({item.source_method for item in items if item.source_method})
        source_method = "kiwoom_rest_multi_investor_flow" if "kiwoom_rest_multi_investor_flow" in stored_source_methods else items[-1].source_method if items else None
        source_methods = ["kiwoom_rest_ka10059", "kiwoom_rest_ka90013"] if source_method == "kiwoom_rest_multi_investor_flow" else stored_source_methods
        if any(item.foreign_holding_qty is not None or item.foreign_holding_ratio is not None for item in items) and "kiwoom_rest_ka10008" not in source_methods:
            source_methods = [*source_methods, "kiwoom_rest_ka10008"]
        amount_available = any(
            value is not None
            for item in items
            for value in (item.foreign_net_amount, item.institution_net_amount, item.program_net_amount)
        )
        available_subjects = {
            "foreign": any(item.foreign_net_qty is not None or item.foreign_net_amount is not None for item in items),
            "institution": any(item.institution_net_qty is not None or item.institution_net_amount is not None for item in items),
            "program": any(item.program_net_qty is not None or item.program_net_amount is not None for item in items),
        }
        has_real_flow_data = selected_source_type == "KIWOOM_REAL" and any(available_subjects.values())
        return InvestorFlowChartResponse(
            watchlist_id=watchlist.id,
            stock_id=stock.id,
            stock_code=stock.stock_code,
            stock_name=stock.stock_name,
            latest_date=items[-1].date if items else None,
            selected_source_type=selected_source_type,
            fallback_source_type=fallback_source_type,
            is_real_investor_flow=selected_source_type == "KIWOOM_REAL",
            source_method=source_method,
            source_methods=source_methods,
            has_real_data=has_real_flow_data,
            amount_available=amount_available,
            available_subjects=available_subjects,
            available_metrics={"foreign_holding_ratio": any(item.foreign_holding_ratio is not None for item in items)},
            data_notice=(
                "Kiwoom ka10059/ka90013 real investor flow data. Foreign and institution are from ka10059; program is from ka90013; foreign holding ratio is from ka10008."
                if selected_source_type == "KIWOOM_REAL"
                else "Real investor flow data is not connected. Derived price-flow data is hidden and not scored."
            ),
            items=items,
        )
