from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any

from backend.app.clients.kiwoom import KiwoomApiError, KiwoomRestClient
from backend.app.core import config
from backend.app.utils.stock_code import normalize_stock_code

logger = logging.getLogger(__name__)


@dataclass
class KiwoomDailyPriceRow:
    trade_date: str
    open_price: int | None
    high_price: int | None
    low_price: int | None
    close_price: int | None
    change_price: int | None
    change_rate: float | None
    volume: int | None
    trading_value: int | None


class KiwoomRestMarketDataProvider:
    def __init__(self) -> None:
        self.client = KiwoomRestClient()

    def get_daily_prices(
        self,
        stock_code: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        years: int = 2,
        max_pages: int | None = None,
        api_id: str | None = None,
        endpoint: str | None = None,
        mode: str | None = None,
        stop_at_start_date: bool = True,
    ) -> dict[str, Any]:
        normalized = normalize_stock_code(stock_code)
        if len(normalized) != 6 or not normalized.isdigit():
            raise RuntimeError(f"INVALID_STOCK_CODE:{stock_code}->{normalized}")

        end_dt = self._parse_date(end_date) if end_date else date.today()
        start_dt = self._parse_date(start_date) if start_date else (end_dt - timedelta(days=365 * max(years, 1)))
        page_limit = max_pages if max_pages is not None else config.KIWOOM_REST_MAX_PAGES
        page_limit = max(int(page_limit), 1)

        api_id = (api_id or config.KIWOOM_REST_DAILY_PRICE_API_ID).strip()
        path = (endpoint or config.KIWOOM_REST_DAILY_PRICE_PATH).strip()
        cont_yn = "N"
        next_key = ""
        raw_items: list[dict[str, Any]] = []
        mapped_items: list[KiwoomDailyPriceRow] = []
        elapsed_total = 0
        api_call_count = 0
        used_cont = False
        used_next_key = False
        last_response_preview: dict[str, Any] | None = None
        response_return_code: str | None = None
        response_return_msg: str | None = None
        top_level_keys: list[str] = []
        list_candidates: list[dict[str, Any]] = []
        first_item_keys: list[str] = []
        page_summaries: list[dict[str, Any]] = []
        stop_reason: str | None = None
        mode_label = mode or "daily_price_collection"

        for page_index in range(1, page_limit + 1):
            body = self._build_request_body(
                api_id=api_id,
                stock_code=normalized,
                start_yyyymmdd=start_dt.strftime("%Y%m%d"),
                end_yyyymmdd=end_dt.strftime("%Y%m%d"),
            )
            response = self.client.post_json(path, api_id=api_id, body=body, cont_yn=cont_yn, next_key=next_key)
            api_call_count += 1
            elapsed_total += response.elapsed_ms
            last_response_preview = response.json_body
            response_return_code = self._to_str_or_none(response.json_body.get("return_code"))
            response_return_msg = self._to_str_or_none(response.json_body.get("return_msg"))
            if not top_level_keys:
                top_level_keys = list(response.json_body.keys())
                list_candidates = self._find_list_candidates(response.json_body)

            extracted = self._extract_rows(response.json_body)
            raw_items.extend(extracted)
            page_rows: list[KiwoomDailyPriceRow] = []
            for row in extracted:
                mapped = self._map_row(row)
                if mapped is not None:
                    mapped_items.append(mapped)
                    page_rows.append(mapped)
            if extracted and not first_item_keys and isinstance(extracted[0], dict):
                first_item_keys = list(extracted[0].keys())

            cont_header = (response.cont_yn or "").upper()
            next_header = (response.next_key or "").strip()
            if cont_header == "Y":
                used_cont = True
            if next_header:
                used_next_key = True

            page_dates = [row.trade_date for row in page_rows]
            newest_date = max(page_dates) if page_dates else None
            oldest_date = min(page_dates) if page_dates else None
            matched_count = sum(1 for row in page_rows if start_dt.isoformat() <= row.trade_date <= end_dt.isoformat())
            stop_after_page = False
            page_stop_reason = ""
            if stop_at_start_date and oldest_date and oldest_date < start_dt.isoformat():
                stop_after_page = True
                page_stop_reason = "oldest_before_requested_start"
                stop_reason = page_stop_reason
            page_summaries.append({
                "page": page_index,
                "rows": len(extracted),
                "newest": newest_date,
                "oldest": oldest_date,
                "matched": matched_count,
                "stop": stop_after_page,
                "reason": page_stop_reason,
            })
            logger.debug(
                "[PRICE PAGE] stock_code=%s mode=%s page=%s rows=%s newest=%s oldest=%s matched=%s stop=%s reason=%s",
                normalized,
                mode_label,
                page_index,
                len(extracted),
                newest_date,
                oldest_date,
                matched_count,
                stop_after_page,
                page_stop_reason or "continue",
            )
            if stop_after_page:
                break
            if cont_header != "Y" or not next_header:
                stop_reason = "no_next_key"
                break
            cont_yn = "Y"
            next_key = next_header
        else:
            stop_reason = "max_pages_reached"

        unique = self._dedup_and_sort(mapped_items)
        unique = [
            row for row in unique
            if start_dt.isoformat() <= row.trade_date <= end_dt.isoformat()
        ]
        actual_min = unique[0].trade_date if unique else None
        actual_max = unique[-1].trade_date if unique else None
        return {
            "provider": "kiwoom_rest",
            "stock_code": stock_code,
            "normalized_stock_code": normalized,
            "api_id": api_id,
            "path": path,
            "requested_start_date": start_dt.isoformat(),
            "requested_end_date": end_dt.isoformat(),
            "actual_min_trade_date": actual_min,
            "actual_max_trade_date": actual_max,
            "raw_count": len(raw_items),
            "mapped_count": len(unique),
            "return_code": response_return_code,
            "return_msg": response_return_msg,
            "api_call_count": api_call_count,
            "pages_fetched": api_call_count,
            "stop_reason": stop_reason,
            "page_summaries": page_summaries,
            "cont_yn_used": used_cont,
            "next_key_used": used_next_key,
            "elapsed_ms": elapsed_total,
            "top_level_keys": top_level_keys,
            "list_candidates": list_candidates,
            "first_item_keys": first_item_keys,
            "first_item_sample": raw_items[0] if raw_items else None,
            "last_item_sample": raw_items[-1] if raw_items else None,
            "items": [x.__dict__ for x in unique],
            "raw_response_preview": last_response_preview or {},
            "request_body_preview": body,
        }

    @staticmethod
    def _to_str_or_none(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    def _build_request_body(self, *, api_id: str, stock_code: str, start_yyyymmdd: str, end_yyyymmdd: str) -> dict[str, Any]:
        api_key = api_id.lower()
        if api_key == "ka10081":
            return {
                "stk_cd": stock_code,
                "base_dt": end_yyyymmdd,
                "upd_stkpc_tp": "1",
            }
        if api_key == "ka10078":
            return {
                "stk_cd": stock_code,
                "qry_dt": end_yyyymmdd,
                "indc_tp": "1",
            }
        # fallback for existing POC default
        return {
            "stk_cd": stock_code,
            "strt_dt": start_yyyymmdd,
            "end_dt": end_yyyymmdd,
        }

    @staticmethod
    def _find_list_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for key, value in payload.items():
            if isinstance(value, list):
                out.append({"key": key, "count": len(value)})
            elif isinstance(value, dict):
                for k2, v2 in value.items():
                    if isinstance(v2, list):
                        out.append({"key": f"{key}.{k2}", "count": len(v2)})
        return out


    @staticmethod
    def _parse_date(value: str) -> date:
        value = value.strip()
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise RuntimeError(f"INVALID_DATE:{value}")

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        raw = str(value).replace(",", "").strip()
        if raw == "":
            return None
        try:
            return int(float(raw))
        except Exception:
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        raw = str(value).replace(",", "").replace("%", "").strip()
        if raw == "":
            return None
        try:
            return float(raw)
        except Exception:
            return None

    @staticmethod
    def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = [
            payload.get("output"),
            payload.get("output1"),
            payload.get("output2"),
            payload.get("items"),
            payload.get("data"),
            payload.get("stk_dt_pole_chart_qry"),
        ]
        for c in candidates:
            if isinstance(c, list):
                return [x for x in c if isinstance(x, dict)]
        for c in candidates:
            if isinstance(c, dict):
                for v in c.values():
                    if isinstance(v, list):
                        return [x for x in v if isinstance(x, dict)]
        return []

    def _map_row(self, row: dict[str, Any]) -> KiwoomDailyPriceRow | None:
        date_keys = ("dt", "date", "trd_dt", "stck_bsop_date", "trade_date")
        open_keys = ("open", "opnprc", "stck_oprc", "open_price", "open_pric")
        high_keys = ("high", "hgprc", "stck_hgpr", "high_price", "high_pric")
        low_keys = ("low", "lwprc", "stck_lwpr", "low_price", "low_pric")
        close_keys = ("close", "clsprc", "stck_clpr", "close_price", "cur_prc")
        volume_keys = ("volume", "acml_vol", "cntg_vol", "volume_qty", "trde_qty")
        trading_value_keys = ("trading_value", "acml_tr_pbmn", "trde_prica")

        trade_date = self._get_first_str(row, date_keys)
        if not trade_date:
            return None
        trade_date = self._normalize_trade_date(trade_date)
        if trade_date is None:
            return None
        return KiwoomDailyPriceRow(
            trade_date=trade_date,
            open_price=self._get_first_int(row, open_keys),
            high_price=self._get_first_int(row, high_keys),
            low_price=self._get_first_int(row, low_keys),
            close_price=self._get_first_int(row, close_keys),
            change_price=self._get_first_int(row, ("change_price", "pred_pre")),
            change_rate=self._get_first_float(row, ("change_rate", "trde_tern_rt")),
            volume=self._get_first_int(row, volume_keys),
            trading_value=self._get_first_int(row, trading_value_keys),
        )

    @staticmethod
    def _get_first_str(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for k in keys:
            if k in row and row[k] is not None:
                s = str(row[k]).strip()
                if s:
                    return s
        return None

    def _get_first_int(self, row: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        for k in keys:
            if k in row:
                n = self._to_int(row.get(k))
                if n is not None:
                    return n
        return None

    def _get_first_float(self, row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for k in keys:
            if k in row:
                n = self._to_float(row.get(k))
                if n is not None:
                    return n
        return None

    @staticmethod
    def _normalize_trade_date(value: str) -> str | None:
        raw = value.strip().replace(".", "").replace("/", "").replace("-", "")
        if len(raw) != 8 or not raw.isdigit():
            return None
        try:
            return datetime.strptime(raw, "%Y%m%d").date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _dedup_and_sort(rows: list[KiwoomDailyPriceRow]) -> list[KiwoomDailyPriceRow]:
        by_date: dict[str, KiwoomDailyPriceRow] = {}
        for row in rows:
            by_date[row.trade_date] = row
        return [by_date[k] for k in sorted(by_date.keys())]
