from __future__ import annotations

from datetime import date
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.providers.market_data.kiwoom_rest_market_indicator_provider import KiwoomRestMarketIndicatorProvider
from backend.app.providers.opendart_financial_provider import OpenDartFinancialProvider
from backend.app.repositories.stock_financial_repository import StockFinancialRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.stock_financial_schema import StockFinancialCollectItem, StockFinancialCollectResponse, StockFinancialDataResponse


ANNUAL_REPORT_CODE = "11011"
QUARTER_REPORT_CODES = {1: "11013", 2: "11012", 3: "11014", 4: "11011"}

ACCOUNT_ALIASES = {
    "revenue": {"매출액", "수익(매출액)", "영업수익", "매출", "ifrs-full_Revenue", "ifrs-full_RevenueFromContractsWithCustomersExcludingAssessedTax"},
    "operating_profit": {"영업이익", "영업이익(손실)", "dart_OperatingIncomeLoss"},
    "net_income": {"당기순이익", "당기순이익(손실)", "연결당기순이익", "ifrs-full_ProfitLoss"},
    "total_assets": {"자산총계", "ifrs-full_Assets"},
    "total_liabilities": {"부채총계", "ifrs-full_Liabilities"},
    "total_equity": {"자본총계", "ifrs-full_Equity"},
    "operating_cash_flow": {"영업활동 현금흐름", "영업활동으로 인한 현금흐름", "ifrs-full_CashFlowsFromUsedInOperatingActivities"},
}


class StockFinancialService:
    def __init__(self, db: Session) -> None:
        self.repo = StockFinancialRepository(db)
        self.stock_repo = StockRepository(db)
        self.provider = KiwoomRestMarketIndicatorProvider()
        self.opendart = OpenDartFinancialProvider()

    def collect_selected(self, stock_ids: list[int]) -> StockFinancialCollectResponse:
        items = []
        for stock_id in list(dict.fromkeys(stock_ids)):
            stock = self.stock_repo.get_by_id(stock_id)
            if not stock:
                items.append(StockFinancialCollectItem(stock_id=stock_id, stock_code="-", status="FAILED", message="종목을 찾을 수 없습니다."))
                continue
            try:
                items.append(self._collect(stock.id, stock.stock_code))
            except Exception as exc:
                items.append(StockFinancialCollectItem(stock_id=stock.id, stock_code=stock.stock_code, status="FAILED", message=str(exc)[:300]))
        self.repo.commit()
        success = sum(x.status == "SUCCESS" for x in items)
        partial = sum(x.status == "PARTIAL" for x in items)
        failed = sum(x.status == "FAILED" for x in items)
        return StockFinancialCollectResponse(status="SUCCESS" if failed == 0 else "PARTIAL", target_count=len(items), success_count=success, partial_count=partial, failed_count=failed, items=items)

    def _collect(self, stock_id: int, stock_code: str) -> StockFinancialCollectItem:
        messages: list[str] = []
        snapshot_saved = self._collect_kiwoom_snapshot(stock_id, stock_code, messages)
        corp_code = self._ensure_corp_code(stock_id, stock_code, messages)
        annual_saved = 0
        quarterly_saved = 0
        shareholder_saved = 0
        if corp_code:
            annual_saved = self._collect_opendart_annual(stock_id, stock_code, corp_code, messages)
            quarterly_saved = self._collect_opendart_quarterly(stock_id, stock_code, corp_code, messages)
            shareholder_saved = self._collect_opendart_shareholders(stock_id, stock_code, corp_code, messages)
        success_parts = [snapshot_saved, annual_saved > 0, quarterly_saved > 0, shareholder_saved > 0]
        status = "SUCCESS" if all(success_parts) else "PARTIAL" if any(success_parts) else "FAILED"
        return StockFinancialCollectItem(
            stock_id=stock_id,
            stock_code=stock_code,
            status=status,
            snapshot_saved=snapshot_saved,
            annual_rows_saved=annual_saved,
            quarterly_rows_saved=quarterly_saved,
            shareholder_rows_saved=shareholder_saved,
            opendart_corp_code_saved=bool(corp_code),
            message=" / ".join(messages[:5]) if messages else None,
        )

    def _collect_kiwoom_snapshot(self, stock_id: int, stock_code: str, messages: list[str]) -> bool:
        try:
            raw = self.provider.get_stock_basic_info(stock_code=stock_code)
        except Exception as exc:
            messages.append(f"ka10001 수집 실패: {str(exc)[:120]}")
            return False
        today = date.today().isoformat()
        now = now_kst()
        financial_keys = ("per", "pbr", "eps", "bps", "roe", "debt_ratio", "reserve_ratio")
        has_snapshot = any(raw.get(k) is not None for k in financial_keys)
        if has_snapshot:
            self.repo.upsert_snapshot({
                "stock_id": stock_id, "stock_code": stock_code, "snapshot_date": today,
                "source_type": "KIWOOM_REAL", "source_method": "kiwoom_rest_ka10001",
                "current_price": raw.get("close_price"), "market_cap": raw.get("market_cap"), "listed_shares": raw.get("listed_shares"),
                "per": raw.get("per"), "pbr": raw.get("pbr"), "eps": raw.get("eps"), "bps": raw.get("bps"), "roe": raw.get("roe"),
                "debt_ratio": raw.get("debt_ratio"), "reserve_ratio": raw.get("reserve_ratio"), "created_at": now, "updated_at": now,
            })
        else:
            messages.append("ka10001 응답에 저장 가능한 재무 스냅샷 필드가 없습니다.")
        return has_snapshot

    def _ensure_corp_code(self, stock_id: int, stock_code: str, messages: list[str]) -> str | None:
        normalized_code = self._normalize_stock_code(stock_code)
        existing = self.repo.get_external_identifier(normalized_code) or self.repo.get_external_identifier(stock_code)
        if existing:
            return str(existing.get("corp_code") or "") or None
        try:
            corp_codes = self.opendart.fetch_corp_codes()
        except Exception as exc:
            messages.append(f"OpenDART corp_code 매핑 실패: {str(exc)[:120]}")
            return None
        match = next((item for item in corp_codes if item.stock_code == normalized_code), None)
        if not match:
            messages.append("OpenDART corp_code 매핑 대상이 없습니다.")
            return None
        now = now_kst()
        self.repo.upsert_external_identifier({
            "stock_id": stock_id, "stock_code": normalized_code, "corp_code": match.corp_code, "corp_name": match.corp_name,
            "source_type": "OPENDART", "source_method": "opendart_corp_code", "mapped_at": now, "created_at": now, "updated_at": now,
        })
        return match.corp_code

    def _collect_opendart_annual(self, stock_id: int, stock_code: str, corp_code: str, messages: list[str]) -> int:
        saved = 0
        for fiscal_year in range(date.today().year - 1, date.today().year - 6, -1):
            try:
                rows = self.opendart.get_financial_statements(corp_code, fiscal_year, ANNUAL_REPORT_CODE)
            except Exception as exc:
                messages.append(f"OpenDART {fiscal_year} 사업보고서 수집 실패: {str(exc)[:90]}")
                continue
            values = self._extract_statement_values(rows)
            if not self._has_statement_core(values):
                continue
            self._save_statement(stock_id, stock_code, "ANNUAL", fiscal_year, 0, str(fiscal_year), f"{fiscal_year}-12-31", values, ANNUAL_REPORT_CODE, "CUMULATIVE", "DIRECT", f"{fiscal_year} 사업보고서")
            saved += 1
        if not saved:
            messages.append("OpenDART 연도별 실적 저장 데이터가 없습니다.")
        return saved

    def _collect_opendart_quarterly(self, stock_id: int, stock_code: str, corp_code: str, messages: list[str]) -> int:
        cumulative: dict[tuple[int, int], dict[str, int | None]] = {}
        current_year = date.today().year
        for fiscal_year in range(current_year - 2, current_year + 1):
            for quarter, report_code in QUARTER_REPORT_CODES.items():
                try:
                    rows = self.opendart.get_financial_statements(corp_code, fiscal_year, report_code)
                except Exception:
                    continue
                values = self._extract_statement_values(rows)
                if self._has_statement_core(values):
                    cumulative[(fiscal_year, quarter)] = values
        saved = 0
        candidates: list[tuple[int, int, dict[str, int | None], str]] = []
        for fiscal_year in range(current_year - 2, current_year + 1):
            for quarter in (1, 2, 3, 4):
                current = cumulative.get((fiscal_year, quarter))
                if not current:
                    continue
                if quarter == 1:
                    candidates.append((fiscal_year, quarter, current, "DIRECT"))
                else:
                    previous = cumulative.get((fiscal_year, quarter - 1))
                    diff = self._diff_statement_values(current, previous)
                    if self._has_statement_core(diff):
                        candidates.append((fiscal_year, quarter, diff, "DART_CUMULATIVE_DIFF"))
        for fiscal_year, quarter, values, method in candidates[-8:]:
            label = f"{fiscal_year}Q{quarter}"
            self._save_statement(stock_id, stock_code, "QUARTERLY", fiscal_year, quarter, label, self._quarter_end_date(fiscal_year, quarter), values, QUARTER_REPORT_CODES[quarter], "QUARTER_ONLY", method, label)
            saved += 1
        if not saved:
            messages.append("OpenDART 분기별 실적 저장 데이터가 없습니다.")
        return saved

    def _collect_opendart_shareholders(self, stock_id: int, stock_code: str, corp_code: str, messages: list[str]) -> int:
        saved = 0
        now = now_kst()
        for fiscal_year in range(date.today().year - 1, date.today().year - 4, -1):
            try:
                rows = self.opendart.get_largest_shareholder_status(corp_code, fiscal_year, ANNUAL_REPORT_CODE)
            except Exception as exc:
                messages.append(f"OpenDART 최대주주 수집 실패: {str(exc)[:90]}")
                break
            snapshot = self._extract_largest_shareholder(rows)
            if not snapshot:
                continue
            self.repo.upsert_shareholder_snapshot({
                "stock_id": stock_id, "stock_code": stock_code, "snapshot_date": snapshot.get("snapshot_date") or f"{fiscal_year}-12-31",
                "source_type": "OPENDART", "source_method": "opendart_hyslr_sttus", "report_code": ANNUAL_REPORT_CODE,
                "receipt_no": snapshot.get("receipt_no"), "largest_shareholder_name": snapshot.get("name"),
                "largest_shareholder_shares": snapshot.get("shares"), "largest_shareholder_ratio": snapshot.get("ratio"),
                "major_shareholder_name": None, "major_shareholder_shares": None, "major_shareholder_ratio": None,
                "ownership_change_flag": None, "notes": "OpenDART 최대주주 현황", "created_at": now, "updated_at": now,
            })
            saved += 1
            break
        try:
            reports = self.opendart.get_major_stock_reports(corp_code)
        except Exception:
            reports = []
        for row in reports[:10]:
            report_date = self._date_text(row.get("rcept_dt") or row.get("rcept_dt"))
            if not report_date:
                continue
            self.repo.upsert_shareholder_change({
                "stock_id": stock_id, "stock_code": stock_code, "report_date": report_date,
                "source_type": "OPENDART", "source_method": "opendart_majorstock", "report_type": row.get("repror") or row.get("report_tp"),
                "receipt_no": row.get("rcept_no"), "reporter_name": row.get("repror") or row.get("corp_name"),
                "shares": self._to_int(row.get("stkqy") or row.get("hold_stock_co")), "ratio": self._to_float(row.get("stkqy_irds")) or self._to_float(row.get("hold_stock_rate")),
                "previous_ratio": None, "change_flag": None, "reason": row.get("rm") or row.get("report_resn"), "created_at": now, "updated_at": now,
            })
            saved += 1
        if not saved:
            messages.append("OpenDART 주주·지분 저장 데이터가 없습니다.")
        return saved

    def _save_statement(self, stock_id: int, stock_code: str, statement_type: str, fiscal_year: int, fiscal_quarter: int, period_label: str, period_end_date: str, values: dict[str, int | None], report_code: str, value_type: str, calculation_method: str, source_period_label: str) -> None:
        now = now_kst()
        self.repo.upsert_statement({
            "stock_id": stock_id, "stock_code": stock_code, "statement_type": statement_type,
            "fiscal_year": fiscal_year, "fiscal_quarter": fiscal_quarter, "period_label": period_label,
            "period_end_date": period_end_date, "source_type": "OPENDART", "source_method": "opendart_fnltt_singl_acnt_all",
            "revenue": values.get("revenue"), "operating_profit": values.get("operating_profit"), "net_income": values.get("net_income"),
            "total_assets": values.get("total_assets"), "total_liabilities": values.get("total_liabilities"), "total_equity": values.get("total_equity"),
            "operating_cash_flow": values.get("operating_cash_flow"), "value_type": value_type, "calculation_method": calculation_method,
            "source_report_code": report_code, "source_period_label": source_period_label, "report_code": report_code,
            "created_at": now, "updated_at": now,
        })

    def _extract_statement_values(self, rows: list[dict[str, Any]]) -> dict[str, int | None]:
        selected_rows = self._prefer_fs_div(rows)
        values: dict[str, int | None] = {key: None for key in ACCOUNT_ALIASES}
        best_scores: dict[str, int] = {key: -1 for key in ACCOUNT_ALIASES}
        for row in selected_rows:
            account_id = str(row.get("account_id") or "").strip()
            account_nm = str(row.get("account_nm") or "").strip()
            amount = self._to_int(row.get("thstrm_amount") or row.get("frmtrm_amount"))
            if amount is None:
                continue
            sj_div = str(row.get("sj_div") or "").strip().upper()
            for key in ACCOUNT_ALIASES:
                score = self._account_match_score(key, account_id, account_nm, sj_div)
                if score > best_scores[key]:
                    values[key] = amount
                    best_scores[key] = score
        return values

    def _account_match_score(self, key: str, account_id: str, account_nm: str, sj_div: str = "") -> int:
        aliases = ACCOUNT_ALIASES.get(key, set())
        if key == "net_income":
            if "\uBE44\uC9C0\uBC30" in account_nm:
                return -1
            if account_nm in {"\uB2F9\uAE30\uC21C\uC774\uC775", "\uB2F9\uAE30\uC21C\uC774\uC775(\uC190\uC2E4)", "\uC5F0\uACB0\uB2F9\uAE30\uC21C\uC774\uC775"}:
                base_score = 120
            elif "\uB2F9\uAE30\uC21C\uC774\uC775" in account_nm and "\uC9C0\uBC30" in account_nm:
                base_score = 110
            elif account_id == "ifrs-full_ProfitLoss":
                base_score = 80
            else:
                return -1
        elif account_nm in aliases:
            base_score = 100
        elif account_id in aliases:
            base_score = 90
        else:
            return -1
        return base_score + self._statement_section_score(key, sj_div)

    def _statement_section_score(self, key: str, sj_div: str) -> int:
        if key in {"revenue", "operating_profit", "net_income"}:
            return 1000 if sj_div == "IS" else 700 if sj_div == "CIS" else 0
        if key in {"total_assets", "total_liabilities", "total_equity"}:
            return 1000 if sj_div == "BS" else 0
        if key == "operating_cash_flow":
            return 1000 if sj_div == "CF" else 0
        return 0

    def _prefer_fs_div(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cfs = [row for row in rows if str(row.get("fs_div") or "").upper() == "CFS"]
        return cfs or [row for row in rows if str(row.get("fs_div") or "").upper() == "OFS"] or rows

    def _has_statement_core(self, values: dict[str, int | None] | None) -> bool:
        if not values:
            return False
        return any(values.get(key) is not None for key in ("revenue", "operating_profit", "net_income", "total_assets", "total_liabilities", "total_equity"))

    def _diff_statement_values(self, current: dict[str, int | None], previous: dict[str, int | None] | None) -> dict[str, int | None]:
        if not previous:
            return {}
        diff: dict[str, int | None] = {}
        flow_keys = {"revenue", "operating_profit", "net_income", "operating_cash_flow"}
        for key in ACCOUNT_ALIASES:
            cur = current.get(key)
            prev = previous.get(key)
            diff[key] = cur - prev if key in flow_keys and cur is not None and prev is not None else (cur if key not in flow_keys else None)
        return diff

    def _extract_largest_shareholder(self, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for row in rows:
            name = row.get("nm") or row.get("holder_nm") or row.get("repror")
            name_text = str(name or "").strip()
            if not name_text or name_text in {"계", "합계", "소계"}:
                continue
            ratio = self._to_float(row.get("trmend_posesn_stock_qota_rt") or row.get("qy_rt") or row.get("bsis_posesn_stock_qota_rt"))
            shares = self._to_int(row.get("trmend_posesn_stock_co") or row.get("qy") or row.get("bsis_posesn_stock_co"))
            if ratio is not None:
                candidates.append({"name": name_text.replace("\n", " "), "ratio": ratio, "shares": shares, "receipt_no": row.get("rcept_no"), "snapshot_date": self._date_text(row.get("stlm_dt"))})
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.get("ratio") or 0)

    def _normalize_stock_code(self, stock_code: str) -> str:
        digits = re.sub(r"\D", "", stock_code or "")
        return digits[-6:].zfill(6) if digits else stock_code

    def _to_int(self, value: Any) -> int | None:
        if value is None:
            return None
        text = str(value).strip().replace(",", "")
        if not text or text in {"-", "--"}:
            return None
        negative = text.startswith("(") and text.endswith(")")
        text = text.strip("()")
        try:
            number = int(float(text))
            return -number if negative else number
        except ValueError:
            return None

    def _to_float(self, value: Any) -> float | None:
        if value is None:
            return None
        text = str(value).strip().replace(",", "").replace("%", "")
        if not text or text in {"-", "--"}:
            return None
        negative = text.startswith("(") and text.endswith(")")
        text = text.strip("()")
        try:
            number = float(text)
            return -number if negative else number
        except ValueError:
            return None

    def _date_text(self, value: Any) -> str | None:
        text = re.sub(r"\D", "", str(value or ""))
        if len(text) != 8:
            return None
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"

    def _quarter_end_date(self, fiscal_year: int, quarter: int) -> str:
        return {1: f"{fiscal_year}-03-31", 2: f"{fiscal_year}-06-30", 3: f"{fiscal_year}-09-30", 4: f"{fiscal_year}-12-31"}[quarter]

    def get_data(self, stock_id: int) -> StockFinancialDataResponse:
        foreign = self.repo.latest_foreign_holding(stock_id) or {}
        shareholder = self.repo.latest_shareholder_snapshot(stock_id) or {}
        return StockFinancialDataResponse(
            stock_id=stock_id,
            financial_snapshot=self.repo.latest_snapshot(stock_id) or {},
            financial_annual_statements=self.repo.list_statements(stock_id, "ANNUAL", 5),
            financial_quarterly_statements=self.repo.list_statements(stock_id, "QUARTERLY", 8),
            shareholder_snapshot={**foreign, **shareholder},
        )
